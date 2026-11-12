"""Public detect API tests: merging, sorting, overlap resolution, robustness."""

from __future__ import annotations

import pytest

from app.contracts import DetectedEntity, EntityType
from privacy.detection import DetectionError, detect, resolve_overlaps


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


def test_resolve_overlaps_both_orderings_person_and_aadhaar() -> None:
    person = DetectedEntity(type=EntityType.PERSON, start=0, end=10, text="0123456789", score=0.9, source="gliner")
    aadhaar = DetectedEntity(type=EntityType.AADHAAR, start=2, end=8, text="234567", score=0.8, source="presidio")

    # Order 1: PERSON first, then AADHAAR
    resolved_1 = resolve_overlaps([person, aadhaar])
    assert len(resolved_1) == 1
    assert resolved_1[0].type == EntityType.AADHAAR
    assert resolved_1[0].start == 2
    assert resolved_1[0].end == 8

    # Order 2: AADHAAR first, then PERSON
    resolved_2 = resolve_overlaps([aadhaar, person])
    assert len(resolved_2) == 1
    assert resolved_2[0].type == EntityType.AADHAAR
    assert resolved_2[0].start == 2
    assert resolved_2[0].end == 8


def test_detect_raises_when_both_backends_fail(monkeypatch) -> None:
    def _fail_presidio(_text):
        raise RuntimeError("Presidio crashed")

    def _fail_ner(_text):
        raise RuntimeError("NER crashed")

    monkeypatch.setattr("privacy.detection.india.recognize", _fail_presidio)
    monkeypatch.setattr("privacy.detection.ner.entities", _fail_ner)

    with pytest.raises(DetectionError):
        detect("Some text to analyze")


def test_detect_presidio_fails_ner_succeeds(monkeypatch) -> None:
    def _fail_presidio(_text):
        raise RuntimeError("Presidio crashed")

    expected = [
        DetectedEntity(type=EntityType.PERSON, start=0, end=5, text="Rahul", score=0.9, source="gliner")
    ]

    monkeypatch.setattr("privacy.detection.india.recognize", _fail_presidio)
    monkeypatch.setattr("privacy.detection.ner.entities", lambda _text: list(expected))

    result = detect("Rahul")
    assert any(e.type == EntityType.PERSON and e.text == "Rahul" for e in result.entities)


def test_detect_ner_fails_presidio_succeeds(monkeypatch) -> None:
    def _fail_ner(_text):
        raise RuntimeError("NER crashed")

    expected_hits = [
        {"type": EntityType.PAN, "start": 0, "end": 10, "score": 0.95, "source": "presidio"}
    ]

    monkeypatch.setattr("privacy.detection.ner.entities", _fail_ner)
    monkeypatch.setattr("privacy.detection.india.recognize", lambda _text: list(expected_hits))

    result = detect("ABCDE1234F")
    assert any(e.type == EntityType.PAN and e.text == "ABCDE1234F" for e in result.entities)
