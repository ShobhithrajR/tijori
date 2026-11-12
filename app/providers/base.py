"""Pluggable LLM backend contract."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.contracts import ChatMessage, LLMResponse


@runtime_checkable
class LLMProvider(Protocol):
    """Any external or local chat-completion backend.

    Implementations must never log or persist the messages they receive.
    """

    name: str
    model: str

    async def complete(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.2,
        max_tokens: int = 512,
    ) -> LLMResponse: ...
