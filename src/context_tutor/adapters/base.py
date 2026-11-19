from __future__ import annotations

from typing import Protocol


class Adapter(Protocol):
    """Minimal contract for an LLM or dictionary adapter.

    The scaffold never invents a sense. If an adapter cannot produce one,
    it must return status="draft" and confidence=0.
    """

    name: str

    def analyze_word(self, sentence: str, word: str) -> dict:
        """Return sense_in_context, why, collocations, register, example."""

    def translate_sentence(self, sentence: str) -> str | None:
        """Return a translation, or None when unavailable."""
