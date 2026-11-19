from __future__ import annotations

from pathlib import Path
import json


DEFAULT_PROFILE = {
    "name": "english_weak",
    "target": "英语薄弱自学者",
    "translation_language": "zh-CN",
    "context_first": True,
    "show_grammar_first": False,
    "max_candidate_words_per_sentence": 3,
    "min_word_length": 4,
    "known_words": [],
}


def load_profile(path: Path | str | None = None) -> dict:
    if path is None:
        return dict(DEFAULT_PROFILE)
    with Path(path).open("r", encoding="utf-8") as handle:
        profile = json.load(handle)
    merged = dict(DEFAULT_PROFILE)
    merged.update(profile)
    return merged
