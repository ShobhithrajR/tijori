"""Provider adapter and factory tests (no network)."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from app.contracts import ChatMessage
from app.providers import OpenAICompatibleProvider, get_provider


class _FakeCompletions:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="hello"))],
            usage=SimpleNamespace(prompt_tokens=2, completion_tokens=3, total_tokens=5),
        )


class _FakeClient:
    def __init__(self) -> None:
        self.completions = _FakeCompletions()
        self.chat = SimpleNamespace(completions=self.completions)


def test_complete_maps_request_and_response() -> None:
    client = _FakeClient()
    provider = OpenAICompatibleProvider(client=client, model="test-model")
    messages = [
        ChatMessage(role="system", content="be terse"),
        ChatMessage(role="user", content="hi"),
    ]

    response = asyncio.run(
        provider.complete(messages, temperature=0.1, max_tokens=16)
    )

    call = client.completions.calls[0]
    assert call["model"] == "test-model"
    assert call["messages"] == [
        {"role": "system", "content": "be terse"},
        {"role": "user", "content": "hi"},
    ]
    assert call["temperature"] == 0.1
    assert call["max_tokens"] == 16

    assert response.text == "hello"
    assert response.provider == "openai_compatible"
    assert response.model == "test-model"
    assert response.usage == {"prompt_tokens": 2, "completion_tokens": 3, "total_tokens": 5}


def test_factory_returns_openai_compatible_by_default() -> None:
    provider = get_provider("openai_compatible")
    assert isinstance(provider, OpenAICompatibleProvider)
    assert provider.name == "openai_compatible"


def test_factory_rejects_unknown_provider() -> None:
    with pytest.raises(ValueError):
        get_provider("not-a-provider")
