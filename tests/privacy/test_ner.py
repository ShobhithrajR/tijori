"""NER tests: GLiNER + spaCy names and addresses, Hinglish samples, backend union."""

from __future__ import annotations

import pytest

from app.contracts import DetectedEntity, EntityType
from privacy.detection import detect, ner


def test_gliner_or_spacy_detects_person_name() -> None:
    hits = ner.entities("My name is Rahul Sharma. Please help today.")
    assert any(h.type == EntityType.PERSON for h in hits)


def test_gliner_or_spacy_detects_address() -> None:
    hits = ner.entities("I live at 12 MG Road, Bangalore and work there.")
    assert any(h.type == EntityType.ADDRESS for h in hits)


def test_hinglish_name_detected() -> None:
    hits = ner.entities("Meri mulaqat hai Rahul Sharma ji aur woh kaam karte hain.")
    assert any(h.type == EntityType.PERSON for h in hits)


def test_no_pii_in_ordinary_text() -> None:
    hits = ner.entities("Hello there, how are you today please?")
    assert hits == []


def test_gliner_and_spacy_both_survive(monkeypatch) -> None:
    text = "Rahul lives in Delhi."
    gliner_hit = DetectedEntity(
        type=EntityType.ADDRESS,
        start=15,
        end=20,
        text="Delhi",
        score=0.8,
        source="gliner",
    )
    spacy_hit = DetectedEntity(
        type=EntityType.PERSON,
        start=0,
        end=5,
        text="Rahul",
        score=0.9,
        source="spacy",
    )

    monkeypatch.setattr(ner, "_gliner_hits", lambda _t: [gliner_hit])
    monkeypatch.setattr(ner, "_spacy_hits", lambda _t: [spacy_hit])

    hits = ner.entities(text)
    types = {h.type for h in hits}
    assert EntityType.ADDRESS in types
    assert EntityType.PERSON in types
    assert len(hits) == 2


def test_ner_gliner_fails_spacy_succeeds(monkeypatch) -> None:
    def _fail_gliner(_text):
        raise RuntimeError("GLiNER error")

    spacy_hit = DetectedEntity(
        type=EntityType.PERSON,
        start=0,
        end=5,
        text="Rahul",
        score=0.85,
        source="spacy",
    )

    monkeypatch.setattr(ner, "_gliner_hits", _fail_gliner)
    monkeypatch.setattr(ner, "_spacy_hits", lambda _t: [spacy_hit])

    hits = ner.entities("Rahul is here")
    assert len(hits) == 1
    assert hits[0].type == EntityType.PERSON


def test_ner_spacy_fails_gliner_succeeds(monkeypatch) -> None:
    def _fail_spacy(_text):
        raise RuntimeError("spaCy error")

    gliner_hit = DetectedEntity(
        type=EntityType.ADDRESS,
        start=0,
        end=7,
        text="MG Road",
        score=0.9,
        source="gliner",
    )

    monkeypatch.setattr(ner, "_gliner_hits", lambda _t: [gliner_hit])
    monkeypatch.setattr(ner, "_spacy_hits", _fail_spacy)

    hits = ner.entities("MG Road is here")
    assert len(hits) == 1
    assert hits[0].type == EntityType.ADDRESS


def test_ner_both_backends_fail_raises(monkeypatch) -> None:
    def _fail(_text):
        raise RuntimeError("Backend failure")

    monkeypatch.setattr(ner, "_gliner_hits", _fail)
    monkeypatch.setattr(ner, "_spacy_hits", _fail)

    with pytest.raises(RuntimeError):
        ner.entities("Some text")


def test_hinglish_coverage_two_code_mixed_docs() -> None:
    docs = [
        {
            "id": "doc1",
            "text": (
                "LOAN APPLICATION FORM\n\n"
                "Mera naam Sneha Joshi hai.\n"
                "Pata: 28, Civil Lines, Behind Collector Office, Nagpur, Maharashtra 440001\n"
                "Aadhaar number: 8987 9730 9114\n"
            ),
            "gold_person": "Sneha Joshi",
            "gold_address": "28, Civil Lines, Behind Collector Office, Nagpur, Maharashtra 440001",
        },
        {
            "id": "doc2",
            "text": (
                "KYC VERIFICATION FORM\n\n"
                "Mera naam Amit Patel hai.\n"
                "Address: Flat 402, Sunrise Apartments, 12 MG Road, Indiranagar, Bengaluru, Karnataka 560038\n"
                "PAN card: ABCDE1234F\n"
            ),
            "gold_person": "Amit Patel",
            "gold_address": "Flat 402, Sunrise Apartments, 12 MG Road, Indiranagar, Bengaluru, Karnataka 560038",
        },
    ]

    misses = []
    for doc in docs:
        res = detect(doc["text"])
        found_persons = [e.text for e in res.entities if e.type == EntityType.PERSON]
        found_addresses = [e.text for e in res.entities if e.type == EntityType.ADDRESS]

        if not any(doc["gold_person"] in p or p in doc["gold_person"] for p in found_persons):
            misses.append((doc["id"], "PERSON", doc["gold_person"]))

        if not any(doc["gold_address"] in a or a in doc["gold_address"] for a in found_addresses):
            misses.append((doc["id"], "ADDRESS", doc["gold_address"]))

        # Report misses, do not hide them
        print(f"Hinglish doc {doc['id']}: found persons={found_persons}, addresses={found_addresses}")

    if misses:
        print(f"Hinglish detection misses: {misses}")
    assert len(misses) == 0, f"Misses detected in Hinglish documents: {misses}"
