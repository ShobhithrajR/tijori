"""Consistent typed placeholder masking (lane 1).

See CONTRACT.md §2 and §3 for the invariants.
"""

from __future__ import annotations

import time

from app.contracts import DetectedEntity, MaskingResult
from privacy.vault import PlaceholderVault


def _valid_spans(text: str, entities: list[DetectedEntity]) -> list[DetectedEntity]:
    """Keep spans that are inside the text and non-empty (end > start)."""
    kept: list[DetectedEntity] = []
    for entity in sorted(entities, key=lambda e: e.start):
        if entity.start < 0 or entity.end > len(text):
            continue
        if entity.end <= entity.start:
            continue
        kept.append(entity)
    return kept


def mask(text: str, entities: list[DetectedEntity]) -> MaskingResult:
    """Replace detected PII spans with consistent typed placeholders."""
    started = time.perf_counter()

    spans = _valid_spans(text, entities)
    vault = PlaceholderVault()
    assignments: list[tuple[DetectedEntity, str]] = []
    for entity in spans:
        placeholder = vault.add(entity.type, entity.text)
        assignments.append((entity, placeholder))

    sanitized = text
    # Replace right-to-left so earlier offsets stay valid.
    for entity, placeholder in sorted(assignments, key=lambda item: -item[0].start):
        sanitized = sanitized[: entity.start] + placeholder + sanitized[entity.end :]

    duration_ms = int((time.perf_counter() - started) * 1000)
    return MaskingResult(
        sanitized_text=sanitized,
        mapping=list(vault.entries),
        entities=list(spans),
        duration_ms=duration_ms,
    )
