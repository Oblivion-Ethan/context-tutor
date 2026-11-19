from __future__ import annotations

import json
import re
import threading
import webbrowser
from collections import defaultdict
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from .english.candidates import tokenize
from .library import Library


def _word_key(value: str) -> str:
    return re.sub(r"[^a-z'’-]", "", value.lower())


def _read_page() -> str:
    return files("context_tutor").joinpath("web/index.html").read_text(encoding="utf-8")


class TutorWebApp:
    """JSON API over the same local JSONL library the CLI uses."""

    def __init__(self, library: Library) -> None:
        self.library = library
        self.lock = threading.RLock()

    def stats(self) -> dict:
        with self.lock:
            return self.library.stats()

    def overview(self) -> dict:
        with self.lock:
            sources = self.library.store.read("sources")
            sentences = self.library.store.read("sentences")
            contexts = self.library.store.read("contexts")
            by_source_sentences: dict[str, int] = defaultdict(int)
            by_source_cards: dict[str, int] = defaultdict(int)
            by_source_drafts: dict[str, int] = defaultdict(int)
            for sentence in sentences:
                by_source_sentences[sentence.get("source_id", "")] += 1
            for card in contexts:
                if card.get("status") == "retired":
                    continue
                by_source_cards[card.get("source_id", "")] += 1
                if card.get("status") == "draft":
                    by_source_drafts[card.get("source_id", "")] += 1

            return {
                "profile": {
                    "name": self.library.profile.get("name", ""),
                    "target": self.library.profile.get("target", ""),
                },
                "stats": self.library.stats(),
                "sources": [
                    {
                        **source,
                        "sentence_count": by_source_sentences.get(source["id"], 0),
                        "card_count": by_source_cards.get(source["id"], 0),
                        "draft_count": by_source_drafts.get(source["id"], 0),
                    }
                    for source in sources
                ],
            }

    def source_payload(self, source_id: str) -> dict:
        with self.lock:
            source = next(
                (item for item in self.library.store.read("sources") if item["id"] == source_id),
                None,
            )
            if source is None:
                raise KeyError(source_id)
            sentences = [
                item
                for item in self.library.store.read("sentences")
                if item.get("source_id") == source_id
            ]
            cards_by_sentence: dict[str, list[dict]] = defaultdict(list)
            for card in self.library.store.read("contexts"):
                if card.get("status") == "retired":
                    continue
                if card.get("source_id") == source_id:
                    cards_by_sentence[card["sentence_id"]].append(card)
            sentences.sort(
                key=lambda item: (item.get("paragraph_index", 0), item.get("sentence_index", 0))
            )
            return {
                "source": source,
                "sentences": [
                    {**sentence, "context_cards": cards_by_sentence.get(sentence["id"], [])}
                    for sentence in sentences
                ],
                "stats": self.library.stats(),
            }

    def lookup(self, word: str, sentence_id: str = "") -> dict:
        key = _word_key(word)
        if not key:
            return {"word": word, "contexts": [], "sentences": []}
        with self.lock:
            contexts = [
                card
                for card in self.library.store.read("contexts")
                if card.get("status") != "retired"
                and (card.get("lemma") == key or _word_key(card.get("surface", "")) == key)
            ]
            sentences = [
                sentence
                for sentence in self.library.store.read("sentences")
                if key in {_word_key(token) for token in tokenize(sentence.get("text", ""))}
            ]
            if sentence_id:
                contexts.sort(key=lambda card: 0 if card.get("sentence_id") == sentence_id else 1)
                sentences.sort(key=lambda sentence: 0 if sentence.get("id") == sentence_id else 1)
            return {
                "word": key,
                "contexts": contexts[:20],
                "sentences": sentences[:6],
            }

    def review_payload(self, status: str = "draft", limit: int = 100) -> dict:
        if status not in {"draft", "reviewed", "retired"}:
            status = "draft"
        limit = max(1, min(limit, 500))
        with self.lock:
            sentences = {
                sentence["id"]: sentence for sentence in self.library.store.read("sentences")
            }
            sources = {
                source["id"]: source for source in self.library.store.read("sources")
            }
            cards = [
                card
                for card in self.library.store.read("contexts")
                if card.get("status") == status
            ]
            cards.sort(key=lambda card: card.get("created_at", ""), reverse=True)
            items = []
            for card in cards[:limit]:
                sentence = sentences.get(card.get("sentence_id", ""), {})
                source = sources.get(card.get("source_id", ""), {})
                items.append(
                    {
                        **card,
                        "sentence_text": sentence.get("text", ""),
                        "source_title": source.get("title", ""),
                    }
                )
            return {"status": status, "cards": items}

    def set_status(self, card_id: str, status: str) -> dict:
        if status not in {"draft", "reviewed", "retired"}:
            raise ValueError("status must be draft, reviewed or retired")
        with self.lock:
            ok = self.library.set_status(card_id, status)
            if not ok:
                raise KeyError(card_id)
            return {
                "card": next(
                    card
                    for card in self.library.store.read("contexts")
                    if card["id"] == card_id
                ),
                "stats": self.library.stats(),
            }


class TutorRequestHandler(BaseHTTPRequestHandler):
    server_version = "ContextTutor/0.3"

    @property
    def app(self) -> TutorWebApp:
        return self.server.app  # type: ignore[attr-defined]

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        if content_type.startswith("text/html"):
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; img-src 'self' data:; style-src 'unsafe-inline'; script-src 'unsafe-inline'",
            )
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, payload: dict) -> None:
        self._send(
            status,
            json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            "application/json; charset=utf-8",
        )

    def _query(self, name: str, default: str = "") -> str:
        values = parse_qs(urlparse(self.path).query).get(name)
        return values[0] if values else default

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        try:
            if path in {"/", "/index.html"}:
                self._send(HTTPStatus.OK, _read_page().encode("utf-8"), "text/html; charset=utf-8")
                return
            if path == "/api/health":
                self._json(HTTPStatus.OK, {"ok": True})
                return
            if path == "/api/overview":
                self._json(HTTPStatus.OK, self.app.overview())
                return
            if path == "/api/source":
                source_id = self._query("id")
                if not source_id:
                    self._json(HTTPStatus.BAD_REQUEST, {"error": "missing source id"})
                    return
                self._json(HTTPStatus.OK, self.app.source_payload(source_id))
                return
            if path == "/api/lookup":
                word = self._query("word")
                sentence_id = self._query("sentence_id")
                if not word:
                    self._json(HTTPStatus.BAD_REQUEST, {"error": "missing word"})
                    return
                self._json(HTTPStatus.OK, self.app.lookup(word, sentence_id))
                return
            if path == "/api/review":
                status = self._query("status", "draft")
                try:
                    limit = int(self._query("limit", "100"))
                except ValueError:
                    limit = 100
                self._json(HTTPStatus.OK, self.app.review_payload(status, limit))
                return
            self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})
        except BrokenPipeError:
            return
        except KeyError:
            self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})
        except Exception as exc:  # keep the local server alive on bad requests
            self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        match = re.fullmatch(r"/api/cards/([^/]+)/status", path)
        if not match:
            self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > 1_000_000:
                self._json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "body too large"})
                return
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            status = str(payload.get("status", ""))
            result = self.app.set_status(unquote(match.group(1)), status)
            self._json(HTTPStatus.OK, result)
        except KeyError:
            self._json(HTTPStatus.NOT_FOUND, {"error": "card not found"})
        except ValueError as exc:
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid json"})

    def log_message(self, fmt: str, *args) -> None:
        # The reader is a local single-user tool; keep the terminal quiet.
        return


class TutorHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def create_server(library: Library, host: str = "127.0.0.1", port: int = 0) -> TutorHTTPServer:
    server = TutorHTTPServer((host, port), TutorRequestHandler)
    server.app = TutorWebApp(library)  # type: ignore[attr-defined]
    return server


def serve(library: Library, host: str = "127.0.0.1", port: int = 8765, open_browser: bool = True) -> None:
    server = create_server(library, host=host, port=port)
    actual_host, actual_port = server.server_address[:2]
    url = f"http://{actual_host}:{actual_port}/"
    print(f"ContextTutor 已启动：{url}")
    print(f"数据目录：{Path(library.data_dir).resolve()}")
    print("按 Ctrl+C 停止。")
    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")
    finally:
        server.server_close()
