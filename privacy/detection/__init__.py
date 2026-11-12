"""Local PII detection (lane 1).

Implement Presidio + India recognizers + GLiNER/spaCy here.
The signature and return type are frozen in CONTRACT.md §3.
"""

from __future__ import annotations

import time

from app.contracts import DetectionResult, DetectedEntity, ENTITY_PRIORITY, EntityType

from privacy.detection import india, ner, patterns

_PRIORITY_INDEX: dict[str, int] = {t.value: i for i, t in enumerate(ENTITY_PRIORITY)}


class DetectionError(RuntimeError):
    """Raised when both detection backends fail."""


def _priority(type_value: EntityType) -> int:
    try:
        return _PRIORITY_INDEX[type_value.value]
    except (KeyError, ValueError, AttributeError):
        return len(ENTITY_PRIORITY)


def resolve_overlaps(entities: list[DetectedEntity]) -> list[DetectedEntity]:
    """Deduplicate and resolve overlaps deterministically.

    1. Dedupe (type, start, end) keeping highest score.
    2. Rank by ENTITY_PRIORITY ascending, then longer span, then earlier start.
    3. Accept each entity only if it does not overlap an already accepted entity.
    4. Return sorted by start.
    """
    if not entities:
        return []

    # 1. Dedupe (type, start, end) keeping highest score
    deduped: dict[tuple[str, int, int], DetectedEntity] = {}
    for entity in entities:
        key = (
            entity.type.value if hasattr(entity.type, "value") else str(entity.type),
            entity.start,
            entity.end,
        )
        existing = deduped.get(key)
        if existing is None or entity.score > existing.score:
            deduped[key] = entity

    # 2. Rank by ENTITY_PRIORITY ascending, then longer span, then earlier start
    def _rank_key(e: DetectedEntity) -> tuple[int, int, int]:
        return (_priority(e.type), -(e.end - e.start), e.start)

    ranked = sorted(deduped.values(), key=_rank_key)

    # 3. Accept each entity only if it does not overlap an already accepted entity
    accepted: list[DetectedEntity] = []
    for candidate in ranked:
        if not any(candidate.start < a.end and a.start < candidate.end for a in accepted):
            accepted.append(candidate)

    # 4. Return sorted by start
    accepted.sort(key=lambda e: (e.start, e.end))
    return accepted


def detect(text: str, *, language: str = "auto") -> DetectionResult:
    """Detect PII spans in ``text`` (Presidio + NER), overlaps resolved."""
    started = time.perf_counter()
    found: list[DetectedEntity] = []

    presidio_failed = False
    ner_failed = False

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
        presidio_failed = True

    try:
        found.extend(ner.entities(text))
    except Exception:
        ner_failed = True

    if presidio_failed and ner_failed:
        raise DetectionError("Both Presidio and NER detection backends failed.")

    # Supplement with pattern/heuristic extractors (address cues, phone, email, etc.)
    try:
        found.extend(patterns.extract(text))
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
