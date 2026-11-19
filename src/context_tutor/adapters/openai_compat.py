from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request


class OpenAICompatibleAdapter:
    """Minimal OpenAI-compatible chat adapter using only the standard library.

    Environment:
      CONTEXT_TUTOR_BASE_URL  default https://api.openai.com/v1
      CONTEXT_TUTOR_API_KEY   required
      CONTEXT_TUTOR_MODEL     default gpt-4o-mini
    """

    name = "openai-compatible"

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout: int = 30,
    ) -> None:
        self.base_url = (base_url or os.environ.get("CONTEXT_TUTOR_BASE_URL", "https://api.openai.com/v1")).rstrip("/")
        self.api_key = api_key or os.environ.get("CONTEXT_TUTOR_API_KEY", "")
        self.model = model or os.environ.get("CONTEXT_TUTOR_MODEL", "gpt-4o-mini")
        self.timeout = timeout

    def _chat(self, prompt: str, temperature: float = 0.2) -> str:
        if not self.api_key:
            raise RuntimeError("CONTEXT_TUTOR_API_KEY is not set")
        payload = {
            "model": self.model,
            "temperature": temperature,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a careful English lexicographer for Chinese learners. Return only valid JSON when asked.",
                },
                {"role": "user", "content": prompt},
            ],
        }
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            raise RuntimeError(f"adapter request failed: {exc}") from exc
        return str(body["choices"][0]["message"]["content"])

    @staticmethod
    def _json_block(text: str) -> dict:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise ValueError("no JSON object in adapter response")
        return json.loads(match.group(0))

    def analyze_word(self, sentence: str, word: str) -> dict:
        prompt = f"""Explain the word "{word}" as used in this sentence, for a Chinese learner whose English is weak.

Sentence: {sentence}

Return JSON with:
- sense_zh: the meaning in THIS sentence only, one short sentence in Chinese
- why_zh: how the sentence context tells you that sense, one sentence in Chinese
- collocations: 0-3 short English collocations that fit this sense
- register_zh: neutral / formal / informal / academic, in Chinese
- example_en: one short new English example using the same sense
- confidence: 0.0-1.0
Do not list dictionary senses that do not fit this sentence."""
        try:
            data = self._json_block(self._chat(prompt))
        except RuntimeError as exc:
            return {
                "sense": f"适配器调用失败：{exc}",
                "why": "",
                "collocations": [],
                "register": "",
                "example": "",
                "confidence": 0.0,
                "status": "draft",
            }
        except (ValueError, KeyError, TypeError):
            return {
                "sense": "适配器返回格式不可解析",
                "why": "",
                "collocations": [],
                "register": "",
                "example": "",
                "confidence": 0.0,
                "status": "draft",
            }
        return {
            "sense": str(data.get("sense_zh", "")).strip(),
            "why": str(data.get("why_zh", "")).strip(),
            "collocations": [str(item) for item in data.get("collocations", [])][:3],
            "register": str(data.get("register_zh", "")).strip(),
            "example": str(data.get("example_en", "")).strip(),
            "confidence": max(0.0, min(1.0, float(data.get("confidence", 0.0)))),
            "status": "draft",
        }

    def translate_sentence(self, sentence: str) -> str | None:
        prompt = f"""Translate this English sentence into natural Chinese for a weak learner.
Keep the sentence structure understandable; do not add commentary.
Return JSON: {{"translation_zh": "..."}}

Sentence: {sentence}"""
        try:
            data = self._json_block(self._chat(prompt, temperature=0.1))
            return str(data.get("translation_zh", "")).strip() or None
        except (RuntimeError, ValueError, KeyError, TypeError):
            return None
