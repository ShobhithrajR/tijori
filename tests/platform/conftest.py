"""Shared fakes for gateway tests.

Lane 1 is not merged yet, so detection/masking/reinsertion are monkeypatched at
the module boundary. These fakes are test-only; no leaking fallback ships in
the gateway.
"""

from __future__ import annotations

import re
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.audit.repository import AuditRepository
from app.contracts import (
    PLACEHOLDER_SCAN_RE,
    ChatMessage,
    DetectedEntity,
    DetectionResult,
    EntityType,
    LLMResponse,
    MaskingResult,
    ReinsertionResult,
)
from app.main import create_app
from app.pipeline.pipeline import PrivacyPipeline
from privacy import detection, masking, reinsertion
from privacy.vault import PlaceholderVault

SAMPLE_TEXT = (
    "My name is Rahul Sharma. My Aadhaar number is 1234-5678-9012 "
    "and my PAN is ABCDE1234F."
)
PII_ORIGINALS = ("Rahul Sharma", "1234-5678-9012", "ABCDE1234F")

_AADHAAR_RE = re.compile(r"\d{4}[- ]\d{4}[- ]\d{4}")
_PAN_RE = re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")


def fake_detect(text: str, *, language: str = "auto") -> DetectionResult:
    spans: list[tuple[EntityType, int, int, str]] = []

    person_at = text.find("Rahul Sharma")
    if person_at >= 0:
        spans.append((EntityType.PERSON, person_at, person_at + len("Rahul Sharma"), "Rahul Sharma"))

    for entity_type, pattern in ((EntityType.AADHAAR, _AADHAAR_RE), (EntityType.PAN, _PAN_RE)):
        for match in pattern.finditer(text):
            spans.append((entity_type, match.start(), match.end(), match.group(0)))

    spans.sort(key=lambda item: item[1])
    entities = [
        DetectedEntity(
            type=entity_type,
            start=start,
            end=end,
            text=value,
            score=1.0,
            source="fake",
        )
        for entity_type, start, end, value in spans
    ]
    return DetectionResult(text=text, entities=entities, language="en")


def fake_mask(text: str, entities: list[DetectedEntity]) -> MaskingResult:
    vault = PlaceholderVault()
    pieces: list[str] = []
    cursor = 0
    for entity in sorted(entities, key=lambda item: item.start):
        placeholder = vault.add(entity.type, entity.text)
        pieces.append(text[cursor : entity.start])
        pieces.append(placeholder)
        cursor = entity.end
    pieces.append(text[cursor:])
    return MaskingResult(
        sanitized_text="".join(pieces),
        mapping=vault.entries,
        entities=list(entities),
    )


def fake_reinsert(text: str, mapping: list) -> ReinsertionResult:
    originals = {entry.placeholder.casefold(): entry.original for entry in mapping}
    replaced = 0
    unknown: list[str] = []

    def substitute(match: re.Match[str]) -> str:
        nonlocal replaced
        token = match.group(0)
        original = originals.get(token.casefold())
        if original is None:
            unknown.append(token)
            return token
        replaced += 1
        return original

    restored = PLACEHOLDER_SCAN_RE.sub(substitute, text)
    present = {match.group(0).casefold() for match in PLACEHOLDER_SCAN_RE.finditer(text)}
    missing = [
        entry.placeholder
        for entry in mapping
        if entry.placeholder.casefold() not in present
    ]
    return ReinsertionResult(
        text=restored,
        replaced=replaced,
        missing=missing,
        unknown=unknown,
    )


class SpyProvider:
    """Records the exact messages it receives and returns a canned reply."""

    name = "spy"
    model = "spy-model"

    def __init__(
        self,
        reply: str = "Summary: <PERSON_1> holds <AADHAAR_1> and <PAN_1>.",
        error: Exception | None = None,
    ) -> None:
        self.reply = reply
        self.error = error
        self.calls = 0
        self.messages: list[list[ChatMessage]] = []

    async def complete(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.2,
        max_tokens: int = 512,
    ) -> LLMResponse:
        self.calls += 1
        self.messages.append([message.model_copy(deep=True) for message in messages])
        if self.error is not None:
            raise self.error
        return LLMResponse(
            text=self.reply,
            provider=self.name,
            model=self.model,
            latency_ms=1,
        )


@pytest.fixture
def fake_privacy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(detection, "detect", fake_detect)
    monkeypatch.setattr(masking, "mask", fake_mask)
    monkeypatch.setattr(reinsertion, "reinsert", fake_reinsert)


@pytest.fixture
def gateway(
    fake_privacy: None,
    tmp_path,
) -> Iterator[tuple[TestClient, SpyProvider, AuditRepository]]:
    repository = AuditRepository(str(tmp_path / "audit.db"))
    provider = SpyProvider()
    pipeline = PrivacyPipeline(provider=provider, repository=repository)
    with TestClient(create_app(pipeline=pipeline)) as client:
        yield client, provider, repository
