"""LLM provider adapters and factory (lane 2)."""

from __future__ import annotations

from app.config import settings
from app.providers.base import LLMProvider
from app.providers.openai_compatible import OpenAICompatibleProvider

_SUPPORTED = {"openai_compatible", "openai", "ollama"}


def get_provider(name: str | None = None) -> LLMProvider:
    """Return the configured provider.

    The default is OpenAI-compatible and points at Ollama. Adding a provider is
    a factory entry here; no caller changes.
    """

    key = (name or settings.llm_provider).strip().lower()
    if key in _SUPPORTED:
        return OpenAICompatibleProvider()
    raise ValueError(f"unsupported LLM provider: {key!r}")


__all__ = ["LLMProvider", "OpenAICompatibleProvider", "get_provider"]
