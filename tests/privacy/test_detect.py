"""Public detect API tests: merging, sorting, overlap resolution, robustness."""

from __future__ import annotations

from app.contracts import DetectedEntity, EntityType
from privacy.detection import detect, resolve_overlaps


def test_detect_returns_result_shape(sample_text) -> None:
    result = detect(sample_text)
    assert result.text == sample_text
    assert result.language == "auto"
    assert isinstance(result.duration_ms, int) and result.duration_ms >= 0
    for entity in result.entities:
        assert entity.end > entity.start
        assert 0.0 <= entity.score <= 1.0
        assert entity.source in ("presidio", "gliner", "spacy", "regex", "heuristic")


def test_detect_entities_sorted_by_start(sample_text) -> None:
    result = detect(sample_text)
    starts = [e.start for e in result.entities]
    assert starts == sorted(starts)


def test_detect_no_overlaps(sample_text) -> None:
    result = detect(sample_text)
    for earlier, later in zip(result.entities, result.entities[1:]):
        assert earlier.end <= later.start


def test_detect_ordinary_text_does_not_raise() -> None:
    result = detect("Hello world, this is ordinary prose with no personal data.")
    assert isinstance(result.entities, list)
    assert isinstance(result.duration_ms, int) and result.duration_ms >= 0


def test_resolve_overlaps_prefers_higher_priority() -> None:
    entities = [
        DetectedEntity(type=EntityType.PERSON, start=11, end=23, text="Rahul Sharma", score=0.9, source="gliner"),
        DetectedEntity(type=EntityType.AADHAAR, start=0, end=14, text="My aadhaar", score=0.8, source="presidio"),
    ]
    resolved = resolve_overlaps(entities)
    assert [e.type for e in resolved] == [EntityType.AADHAAR]


def test_resolve_overlaps_keeps_longer_span_on_tie() -> None:
    entities = [
        DetectedEntity(type=EntityType.ADDRESS, start=0, end=10, text="MG Road", score=0.8, source="spacy"),
        DetectedEntity(type=EntityType.ADDRESS, start=0, end=20, text="12 MG Road Bangalore", score=0.7, source="spacy"),
    ]
    resolved = resolve_overlaps(entities)
    assert len(resolved) == 1
    assert resolved[0].end - resolved[0].start == 20
