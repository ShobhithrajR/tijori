"""Local PII detection (lane 1).

Implement Presidio + India recognizers + GLiNER/spaCy here.
The signature and return type are frozen in CONTRACT.md §3.
"""

from __future__ import annotations

import time

from app.contracts import DetectionResult, DetectedEntity, ENTITY_PRIORITY, EntityType

from privacy.detection import india, ner

_PRIORITY_INDEX: dict[str, int] = {t.value: i for i, t in enumerate(ENTITY_PRIORITY)}


def _priority(type_value: EntityType) -> int:
    try:
        return _PRIORITY_INDEX[type_value.value]
    except (KeyError, ValueError):
        return len(ENTITY_PRIORITY)


def _wins(challenger: DetectedEntity, incumbent: DetectedEntity) -> bool:
    """True when ``challenger`` should replace ``incumbent``."""
    if _priority(challenger.type) != _priority(incumbent.type):
        return _priority(challenger.type) < _priority(incumbent.type)
    challenger_len = challenger.end - challenger.start
    incumbent_len = incumbent.end - incumbent.start
    return challenger_len > incumbent_len


def resolve_overlaps(entities: list[DetectedEntity]) -> list[DetectedEntity]:
    """Deduplicate and resolve overlaps (higher priority wins, longer span wins ties)."""
    unique: dict[tuple[str, int, int], DetectedEntity] = {}
    order: list[tuple[str, int, int]] = []
    for entity in sorted(entities, key=lambda e: (e.start, -(e.end - e.start))):
        key = (entity.type.value, entity.start, entity.end)
        existing = unique.get(key)
        if existing is None:
            unique[key] = entity
            order.append(key)
        elif entity.score > existing.score:
            unique[key] = entity

    accepted: list[DetectedEntity] = []
    for key in order:
        candidate = unique[key]
        overlapping = [a for a in accepted if candidate.start < a.end and a.start < candidate.end]
        if not overlapping:
            accepted.append(candidate)
            continue
        winner = overlapping[0]
        for other in overlapping[1:]:
            if _wins(candidate, other):
                winner = candidate
            elif _wins(other, winner):
                winner = other
        if winner is overlapping[0] and not _wins(candidate, overlapping[0]):
            # The incumbent already holds the overlap; the challenger loses.
            continue
        kept = [a for a in accepted if all(a is not o for o in overlapping)]
        kept.append(winner)
        kept.sort(key=lambda e: e.start)
        accepted = kept
    return accepted


def detect(text: str, *, language: str = "auto") -> DetectionResult:
    """Detect PII spans in ``text`` (Presidio + NER), overlaps resolved."""
    started = time.perf_counter()
    found: list[DetectedEntity] = []

    try:
        for hit in india.recognize(text):
            found.append(
                DetectedEntity(
                    type=hit["type"],
                    start=hit["start"],
                    end=hit["end"],
                    text=text[hit["start"] : hit["end"]],
                    score=hit["score"],
                    source=hit["source"],
                )
            )
    except Exception:
        pass

    try:
        found.extend(ner.entities(text))
    except Exception:
        pass

    resolved = resolve_overlaps(found)
    resolved = sorted(
        (e for e in resolved if e.end > e.start and e.start >= 0 and e.end <= len(text)),
        key=lambda e: e.start,
    )
    duration_ms = int((time.perf_counter() - started) * 1000)
    return DetectionResult(
        text=text,
        entities=resolved,
        language=language or "auto",
        duration_ms=duration_ms,
    )
