from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from hashlib import sha1


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def stable_id(*parts: str) -> str:
    """Stable short id for records rebuilt from the same content."""
    raw = "|".join(part.strip() for part in parts)
    return sha1(raw.encode("utf-8")).hexdigest()[:16]


@dataclass
class Source:
    id: str
    title: str
    kind: str
    path: str = ""
    author: str = ""
    edition: str = ""
    sha256: str = ""
    created_at: str = field(default_factory=utc_now)
    status: str = "ingested"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SentenceCard:
    id: str
    source_id: str
    text: str
    paragraph_index: int
    sentence_index: int
    main_clause: str
    modifiers: list[str] = field(default_factory=list)
    candidate_words: list[str] = field(default_factory=list)
    translation: str | None = None
    difficulty: str = "unrated"
    status: str = "segmented"
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ContextCard:
    id: str
    source_id: str
    sentence_id: str
    surface: str
    lemma: str
    sense: str
    why: str = ""
    collocations: list[str] = field(default_factory=list)
    register: str = ""
    example: str = ""
    confidence: float = 0.0
    status: str = "draft"
    adapter: str = ""
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict:
        return asdict(self)
