"""OpenAI-compatible chat-completion provider.

Defaults point at a local Ollama instance (see CONTRACT.md §7). Swapping to
OpenAI/OpenRouter/Groq is configuration only. Message content is never logged
or persisted here.
"""

from __future__ import annotations

import time

from openai import AsyncOpenAI

from app.config import settings
from app.contracts import ChatMessage, LLMResponse


class OpenAICompatibleProvider:
    """Provider adapter for any `/v1/chat/completions` endpoint."""

    name = "openai_compatible"

    def __init__(
        self,
        *,
        client: AsyncOpenAI | None = None,
        model: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: float | None = None,
    ) -> None:
        self.model = model or settings.llm_model
        self._client = client or AsyncOpenAI(
            base_url=base_url or settings.llm_base_url,
            api_key=api_key or settings.llm_api_key,
            timeout=settings.llm_timeout_s if timeout is None else timeout,
            max_retries=0,
        )

    async def complete(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.2,
        max_tokens: int = 512,
    ) -> LLMResponse:
        started = time.perf_counter()
        completion = await self._client.chat.completions.create(
            model=self.model,
            messages=[message.model_dump() for message in messages],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        latency_ms = int((time.perf_counter() - started) * 1000)

        if not completion.choices:
            raise RuntimeError("provider returned no completion choices")

        text = completion.choices[0].message.content or ""
        usage: dict[str, int] = {}
        if completion.usage is not None:
            for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
                value = getattr(completion.usage, key, None)
                if isinstance(value, int):
                    usage[key] = value

        return LLMResponse(
            text=text,
            provider=self.name,
            model=self.model,
            latency_ms=latency_ms,
            usage=usage,
        )
