from __future__ import annotations


class MockAdapter:
    """Deterministic placeholder for pipeline tests, not a real sense generator."""

    name = "mock"

    def analyze_word(self, sentence: str, word: str) -> dict:
        return {
            "sense": "（占位）接入真实适配器后生成语境义",
            "why": "mock adapter：仅用于验证入库与数据结构",
            "collocations": [],
            "register": "",
            "example": "",
            "confidence": 0.0,
            "status": "draft",
        }

    def translate_sentence(self, sentence: str) -> str | None:
        return None
