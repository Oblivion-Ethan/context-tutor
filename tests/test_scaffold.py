from __future__ import annotations

import json
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path

from context_tutor.adapters.mock import MockAdapter
from context_tutor.adapters.validate import normalize_analysis
from context_tutor.english.candidates import rank_candidates
from context_tutor.english.segment import split_paragraphs, split_sentences
from context_tutor.library import Library
from context_tutor.web import create_server


class SegmentTests(unittest.TestCase):
    def test_split_paragraphs(self) -> None:
        text = "First paragraph.\n\nSecond paragraph."
        self.assertEqual(split_paragraphs(text), ["First paragraph.", "Second paragraph."])

    def test_split_sentences(self) -> None:
        text = "One. Two? Three!"
        self.assertEqual(split_sentences(text), ["One.", "Two?", "Three!"])

    def test_protects_abbreviations_and_decimals(self) -> None:
        self.assertEqual(
            split_sentences("Mr. Smith went home. He was tired."),
            ["Mr. Smith went home.", "He was tired."],
        )
        self.assertEqual(
            split_sentences("The value is 3.14. Next sentence."),
            ["The value is 3.14.", "Next sentence."],
        )
        self.assertEqual(
            split_sentences('He said, "Go." Then he left.'),
            ['He said, "Go."', "Then he left."],
        )
        self.assertEqual(
            split_sentences("Use e.g. this example. Then stop."),
            ["Use e.g. this example.", "Then stop."],
        )

    def test_candidates_are_bounded(self) -> None:
        words = rank_candidates("Context is not decoration; it is instruction.", max_words=2)
        self.assertLessEqual(len(words), 2)
        self.assertTrue(all(len(word) >= 4 for word in words))


class LibraryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.library = Library(Path(self.temp.name))

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_ingest_and_enrich(self) -> None:
        result = self.library.ingest_text(
            "Many learners read English as a list of isolated words. "
            "Context tells you which sense to use.",
            title="Demo",
            kind="article",
        )
        self.assertGreaterEqual(result["sentences_added"], 2)
        self.assertGreater(self.library.stats()["reviewable_sentences"], 0)

        enrich = self.library.enrich(MockAdapter())
        self.assertGreater(enrich["created"], 0)
        cards = self.library.store.read("contexts")
        self.assertTrue(all(card["status"] == "draft" for card in cards))

    def test_lookup_and_review(self) -> None:
        self.library.ingest_text(
            "Context tells you which sense to use.",
            title="Demo",
            kind="article",
        )
        self.library.enrich(MockAdapter())
        found = self.library.lookup("context")
        self.assertTrue(found["sentences"])
        self.assertTrue(found["contexts"])

        review = self.library.review(limit=1)
        self.assertEqual(len(review), 1)
        self.assertIn("____", review[0]["cloze"])

    def test_export(self) -> None:
        self.library.ingest_text("Context matters.", title="Demo")
        out = Path(self.temp.name) / "export.json"
        self.library.export(out)
        self.assertTrue(out.exists())

    def test_promote_card(self) -> None:
        self.library.ingest_text("Context matters.", title="Demo")
        self.library.enrich(MockAdapter())
        card = self.library.store.read("contexts")[0]
        self.assertTrue(self.library.set_status(card["id"], "reviewed"))
        updated = self.library.store.find("contexts", id=card["id"])[0]
        self.assertEqual(updated["status"], "reviewed")
        self.assertEqual(self.library.stats()["reviewed_context_cards"], 1)

    def test_replace_drafts(self) -> None:
        self.library.ingest_text("Context matters.", title="Demo")
        self.library.enrich(MockAdapter())
        first = self.library.stats()
        self.assertGreater(first["draft_context_cards"], 0)

        self.library.enrich(MockAdapter(), replace_drafts=True)
        second = self.library.stats()
        self.assertGreater(second["retired_context_cards"], 0)
        self.assertGreater(second["draft_context_cards"], 0)

    def test_validation_rejects_bad_payload(self) -> None:
        normalized, errors = normalize_analysis(
            {"sense": "", "confidence": "bad", "status": "weird", "collocations": "x"}
        )
        self.assertIn("missing sense", errors)
        self.assertIn("confidence not numeric", errors)
        self.assertIn("invalid status: weird", errors)
        self.assertEqual(normalized["confidence"], 0.0)
        self.assertEqual(normalized["status"], "draft")

        _, errors = normalize_analysis({"sense": "适配器调用失败：timeout", "confidence": 0})
        self.assertIn("adapter error", errors)


class WebAppTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.library = Library(Path(self.temp.name))
        self.library.ingest_text(
            "Context is not decoration; it is instruction. "
            "A word without context is only a dictionary entry.",
            title="Web Demo",
            kind="article",
        )
        self.library.enrich(MockAdapter())
        self.server = create_server(self.library, host="127.0.0.1", port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temp.cleanup()

    def request(self, path: str, payload: dict | None = None) -> tuple[int, dict]:
        data = None
        headers = {}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(self.base + path, data=data, headers=headers)
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))

    def test_index_and_read_api(self) -> None:
        with urllib.request.urlopen(self.base + "/", timeout=5) as response:
            body = response.read().decode("utf-8")
            self.assertEqual(response.status, 200)
            self.assertIn("text/html", response.headers["Content-Type"])
            self.assertIn("ContextTutor", body)

        status, overview = self.request("/api/overview")
        self.assertEqual(status, 200)
        self.assertEqual(len(overview["sources"]), 1)
        source_id = overview["sources"][0]["id"]

        _, source = self.request(f"/api/source?id={source_id}")
        self.assertEqual(source["source"]["title"], "Web Demo")
        self.assertGreaterEqual(len(source["sentences"]), 2)
        self.assertTrue(any(sentence["context_cards"] for sentence in source["sentences"]))

        _, lookup = self.request("/api/lookup?word=context")
        self.assertEqual(lookup["word"], "context")
        self.assertTrue(lookup["contexts"])
        self.assertTrue(lookup["sentences"])

    def test_status_update_api(self) -> None:
        card = self.library.store.read("contexts")[0]
        status, payload = self.request(
            f"/api/cards/{card['id']}/status", {"status": "reviewed"}
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload["card"]["status"], "reviewed")
        self.assertGreaterEqual(payload["stats"]["reviewed_context_cards"], 1)


if __name__ == "__main__":
    unittest.main()
