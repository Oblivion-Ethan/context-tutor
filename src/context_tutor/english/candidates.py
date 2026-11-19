from __future__ import annotations

import re
from collections import Counter


TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z'\-]*")

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "but", "by", "can",
    "could", "did", "do", "does", "for", "from", "had", "has", "have", "he",
    "her", "here", "his", "how", "i", "if", "in", "into", "is", "it", "its",
    "may", "me", "might", "more", "most", "my", "no", "not", "of", "on",
    "or", "our", "out", "she", "should", "so", "some", "than", "that", "the",
    "their", "them", "then", "there", "these", "they", "this", "those", "to",
    "too", "up", "us", "was", "we", "were", "what", "when", "where", "which",
    "who", "why", "will", "with", "would", "you", "your",
}


def tokenize(sentence: str) -> list[str]:
    return TOKEN_RE.findall(sentence)


def rank_candidates(
    sentence: str,
    known_words: set[str] | None = None,
    max_words: int = 3,
    min_length: int = 4,
) -> list[str]:
    """Pick a few likely-useful words without pretending to know the learner."""
    known = {word.lower() for word in (known_words or set())}
    counts = Counter(word for word in tokenize(sentence) if len(word) >= min_length)
    candidates = [
        word
        for word in counts
        if word.lower() not in STOPWORDS and word.lower() not in known
    ]
    candidates.sort(key=lambda word: (-counts[word], -len(word), word.lower()))
    return candidates[:max_words]
