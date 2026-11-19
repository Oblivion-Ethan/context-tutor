from __future__ import annotations

import re


CLAUSE_BREAK_RE = re.compile(
    r"(?i)(?:,\s*(?:which|that|who|whom|whose|where|when)\b|;\s*|\s+(?:because|although|though|while|whereas|but)\s+)"
)


def main_clause(sentence: str) -> str:
    """Return the first clause as a rough main-clause hint, not a parse tree."""
    parts = CLAUSE_BREAK_RE.split(sentence, maxsplit=1)
    return parts[0].strip().rstrip(",") if parts else sentence.strip()


def modifier_hints(sentence: str) -> list[str]:
    """Split off obvious subordinate or contrast clauses for later review."""
    parts = [part.strip() for part in CLAUSE_BREAK_RE.split(sentence) if part.strip()]
    return parts[1:]
