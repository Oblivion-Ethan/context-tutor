from __future__ import annotations

import re


PARAGRAPH_RE = re.compile(r"\n\s*\n")

# Private-use placeholders so protected dots never trigger the splitter.
_DOT = "\ue000"
_ELLIPSIS = "\ue001"

PROTECTED_TERMS = (
    "e.g.",
    "i.e.",
    "Mr.",
    "Mrs.",
    "Ms.",
    "Dr.",
    "Prof.",
    "Sr.",
    "Jr.",
    "St.",
    "vs.",
    "etc.",
    "cf.",
    "al.",
    "Fig.",
    "No.",
)

# Split after terminal punctuation plus optional closing quote, when the next
# token looks like the start of a sentence. This is still rule-based, not a
# full sentence boundary detector.
SPLIT_RE = re.compile(
    r"(?<=[.!?])\s+(?=[\"'“”‘’A-Z0-9])"
    r"|(?<=[.!?][\"'“”‘’])\s+(?=[\"'“”‘’A-Z0-9])"
)


def split_paragraphs(text: str) -> list[str]:
    parts = [part.strip() for part in PARAGRAPH_RE.split(text)]
    return [part for part in parts if part]


def _protect(text: str) -> str:
    text = re.sub(r"\.{3,}", _ELLIPSIS, text)
    for term in PROTECTED_TERMS:
        text = re.sub(re.escape(term), term.replace(".", _DOT), text, flags=re.IGNORECASE)
    text = re.sub(r"(\d)\.(\d)", rf"\1{_DOT}\2", text)
    return text


def _restore(text: str) -> str:
    return text.replace(_DOT, ".").replace(_ELLIPSIS, "...")


def split_sentences(paragraph: str) -> list[str]:
    """Split a paragraph into sentences, protecting common abbreviations.

    Handles titles (Mr., Dr.), Latin abbreviations (e.g., i.e.), decimals,
    ellipses and closing quotes. It does not handle every edge case; a parser
    belongs in a later adapter, not in this rule-based scaffold.
    """
    normalized = re.sub(r"\s*\n\s*", " ", paragraph).strip()
    if not normalized:
        return []
    protected = _protect(normalized)
    parts = [part.strip() for part in SPLIT_RE.split(protected)]
    return [_restore(part) for part in parts if part.strip()]
