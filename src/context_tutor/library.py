from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import json
import re

from .adapters.validate import normalize_analysis
from .config import DEFAULT_PROFILE, load_profile
from .models import ContextCard, SentenceCard, Source, stable_id, utc_now
from .storage import JsonlStore
from .english.candidates import rank_candidates, tokenize
from .english.context import main_clause, modifier_hints
from .english.segment import split_paragraphs, split_sentences


def _difficulty(sentence: str) -> str:
    words = tokenize(sentence)
    if len(words) <= 10:
        return "easy"
    if len(words) <= 18:
        return "medium"
    return "hard"


class Library:
    """Source ledger, sentence cards and context cards in one local folder."""

    def __init__(self, data_dir: Path | str, profile: dict | None = None) -> None:
        self.data_dir = Path(data_dir)
        self.store = JsonlStore(self.data_dir)
        self.profile = dict(DEFAULT_PROFILE)
        if profile:
            self.profile.update(profile)

    def ingest_file(
        self,
        path: Path | str,
        title: str,
        kind: str = "article",
        author: str = "",
        edition: str = "",
        max_words: int | None = None,
    ) -> dict:
        text = Path(path).read_text(encoding="utf-8")
        return self.ingest_text(
            text=text,
            title=title,
            kind=kind,
            author=author,
            edition=edition,
            path=str(path),
            max_words=max_words,
        )

    def ingest_text(
        self,
        text: str,
        title: str,
        kind: str = "article",
        author: str = "",
        edition: str = "",
        path: str = "",
        max_words: int | None = None,
    ) -> dict:
        digest = sha256(text.encode("utf-8")).hexdigest()
        source_id = stable_id(title, kind, digest)
        source = Source(
            id=source_id,
            title=title,
            kind=kind,
            author=author,
            edition=edition,
            path=path,
            sha256=digest,
        )
        self.store.append("sources", source.to_dict())

        max_words = int(
            max_words
            if max_words is not None
            else self.profile.get("max_candidate_words_per_sentence", 3)
        )
        known_words = {str(word).lower() for word in self.profile.get("known_words", [])}
        min_length = int(self.profile.get("min_word_length", 4))
        added = 0

        for paragraph_index, paragraph in enumerate(split_paragraphs(text)):
            for sentence_index, sentence in enumerate(split_sentences(paragraph)):
                sentence_id = stable_id(source_id, str(paragraph_index), str(sentence_index), sentence)
                card = SentenceCard(
                    id=sentence_id,
                    source_id=source_id,
                    text=sentence,
                    paragraph_index=paragraph_index,
                    sentence_index=sentence_index,
                    main_clause=main_clause(sentence),
                    modifiers=modifier_hints(sentence),
                    candidate_words=rank_candidates(
                        sentence,
                        known_words=known_words,
                        max_words=max_words,
                        min_length=min_length,
                    ),
                    difficulty=_difficulty(sentence),
                )
                if self.store.append("sentences", card.to_dict()):
                    added += 1

        return {
            "source_id": source_id,
            "source": source.title,
            "sentences_added": added,
            "sentences_total": self.store.count("sentences"),
        }

    def enrich(self, adapter, limit: int | None = None, replace_drafts: bool = False) -> dict:
        """Create draft context cards. A real adapter must supply the sense."""
        if replace_drafts:
            for record in self.store.read("contexts"):
                if record.get("status") == "draft":
                    self.store.update("contexts", record["id"], status="retired")

        existing = {
            (record["sentence_id"], record["surface"].lower())
            for record in self.store.read("contexts")
            if record.get("status") != "retired"
        }
        created = 0
        rejected = 0
        for sentence in self.store.read("sentences"):
            for word in sentence.get("candidate_words", []):
                key = (sentence["id"], word.lower())
                if key in existing:
                    continue
                result = adapter.analyze_word(sentence["text"], word)
                normalized, errors = normalize_analysis(result)
                if errors:
                    rejected += 1
                    continue
                card = ContextCard(
                    id=stable_id(
                        sentence["id"],
                        word.lower(),
                        normalized["sense"],
                        f"{getattr(adapter, 'name', 'unknown')}:{utc_now()}" if replace_drafts else "",
                    ),
                    source_id=sentence["source_id"],
                    sentence_id=sentence["id"],
                    surface=word,
                    lemma=word.lower(),
                    sense=normalized["sense"],
                    why=normalized["why"],
                    collocations=normalized["collocations"],
                    register=normalized["register"],
                    example=normalized["example"],
                    confidence=normalized["confidence"],
                    status=normalized["status"],
                    adapter=getattr(adapter, "name", "unknown"),
                )
                if self.store.append("contexts", card.to_dict()):
                    created += 1
                    existing.add(key)
                    if limit is not None and created >= limit:
                        return {
                            "created": created,
                            "rejected": rejected,
                            "adapter": card.adapter,
                            "limited": True,
                            "replace_drafts": replace_drafts,
                        }
        return {
            "created": created,
            "rejected": rejected,
            "adapter": getattr(adapter, "name", "unknown"),
            "limited": False,
            "replace_drafts": replace_drafts,
        }

    def set_status(self, card_id: str, status: str) -> bool:
        """Promote or retire a context card after human review."""
        if status not in {"draft", "reviewed", "retired"}:
            raise ValueError(f"invalid status: {status}")
        return self.store.update("contexts", card_id, status=status)

    def lookup(self, word: str, context: str | None = None) -> dict:
        target = word.lower()
        contexts = [
            record
            for record in self.store.read("contexts")
            if record.get("lemma") == target or record.get("surface", "").lower() == target
            if record.get("status") != "retired"
        ]
        sentences = [
            record
            for record in self.store.read("sentences")
            if target in {token.lower() for token in tokenize(record.get("text", ""))}
        ]
        if context:
            sentences = [
                record for record in sentences if context.lower() in record.get("text", "").lower()
            ] or sentences
        return {"contexts": contexts[:5], "sentences": sentences[:5]}

    def review(self, limit: int = 5) -> list[dict]:
        items: list[dict] = []
        for sentence in self.store.read("sentences"):
            words = sentence.get("candidate_words", [])
            if not words:
                continue
            answer = words[0]
            cloze = re.sub(
                rf"\b{re.escape(answer)}\b",
                "____",
                sentence["text"],
                count=1,
                flags=re.IGNORECASE,
            )
            items.append(
                {
                    "sentence_id": sentence["id"],
                    "cloze": cloze,
                    "answer": answer,
                    "source_id": sentence["source_id"],
                    "main_clause": sentence.get("main_clause", ""),
                }
            )
            if len(items) >= limit:
                break
        return items

    def stats(self) -> dict:
        contexts = self.store.read("contexts")
        return {
            "sources": self.store.count("sources"),
            "sentences": self.store.count("sentences"),
            "context_cards": len(contexts),
            "draft_context_cards": sum(1 for card in contexts if card.get("status") == "draft"),
            "reviewed_context_cards": sum(
                1 for card in contexts if card.get("status") == "reviewed"
            ),
            "retired_context_cards": sum(
                1 for card in contexts if card.get("status") == "retired"
            ),
            "reviewable_sentences": sum(
                1 for sentence in self.store.read("sentences") if sentence.get("candidate_words")
            ),
        }

    def export(self, out: Path | str) -> Path:
        out_path = Path(out)
        payload = {
            "exported_at": utc_now(),
            "profile": self.profile,
            "sources": self.store.read("sources"),
            "sentences": self.store.read("sentences"),
            "context_cards": self.store.read("contexts"),
        }
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return out_path
