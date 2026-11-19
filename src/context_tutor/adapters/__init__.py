"""Model adapters. The scaffold works without one; real cards need one."""

from .mock import MockAdapter
from .openai_compat import OpenAICompatibleAdapter


def build_adapter(name: str):
    if name == "mock":
        return MockAdapter()
    if name in {"openai", "openai-compatible"}:
        return OpenAICompatibleAdapter()
    raise ValueError(f"unknown adapter: {name}")


__all__ = ["MockAdapter", "OpenAICompatibleAdapter", "build_adapter"]
