"""NER tests: GLiNER + spaCy names and addresses, Hinglish sample."""

from __future__ import annotations

import pytest

from app.contracts import EntityType
from privacy.detection import ner


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
