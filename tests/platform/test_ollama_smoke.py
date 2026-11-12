"""Real Ollama smoke test. Skipped when the endpoint is not reachable."""

from __future__ import annotations

import asyncio

import httpx
import pytest

from app.config import settings
from app.contracts import ChatMessage
from app.providers import OpenAICompatibleProvider


@pytest.mark.slow
def test_real_ollama_completion() -> None:
    if not any(host in settings.llm_base_url for host in ("127.0.0.1", "localhost", "::1")):
        pytest.skip("TIJORI_LLM_BASE_URL is not a local Ollama endpoint")

    models_url = settings.llm_base_url.rstrip("/") + "/models"
    try:
        response = httpx.get(models_url, timeout=2.0)
        response.raise_for_status()
    except (httpx.HTTPError, OSError) as exc:
        pytest.skip(f"Ollama endpoint not reachable at {models_url}: {exc}")

    provider = OpenAICompatibleProvider()
    result = asyncio.run(
        provider.complete(
            [ChatMessage(role="user", content="Reply with the single word OK.")],
            temperature=0.0,
            max_tokens=16,
        )
    )

    assert result.text.strip()
    assert result.provider == "openai_compatible"
    assert result.model == settings.llm_model
