"""India-specific Presidio recognizer tests (positive + negative per type)."""

from __future__ import annotations

from app.contracts import EntityType
from privacy.detection.india import recognize

AADHAAR_POSITIVE = "My aadhaar number is 2234 5678 9012 and I filed it."
AADHAAR_NO_CONTEXT = "The number 223456789012 looks fine today."
AADHAAR_BAD_FIRST_DIGIT = "My aadhaar number is 123456789012 filed today."

PAN_POSITIVE = "Income tax PAN is ABCDE1234F for the filing."
PAN_NO_CONTEXT = "The code ABCDE1234F appears in the letter."

GSTIN_POSITIVE = "GSTIN 27AAPFU0939F1ZV was issued to the company."
GSTIN_NO_CONTEXT = "The code 27AAPFU0939F1ZV looks fine today."

VOTER_ID_POSITIVE = "My voter id is ABC1234567 and I voted."
VOTER_ID_NO_CONTEXT = "The id ABC1234567 looks fine today."

PASSPORT_POSITIVE = "Passport number J1234567 was submitted."
PASSPORT_NO_CONTEXT = "The number J1234567 looks fine today."


def _types(text: str) -> list[str]:
    return [hit["type"].value for hit in recognize(text)]


def _hits(text: str, entity_type: EntityType):
    return [h for h in recognize(text) if h["type"] == entity_type]


def test_aadhaar_positive_detected() -> None:
    hits = _hits(AADHAAR_POSITIVE, EntityType.AADHAAR)
    assert len(hits) == 1
    assert hits[0]["start"] < hits[0]["end"]
    assert hits[0]["end"] - hits[0]["start"] > 0


def test_aadhaar_without_context_not_detected() -> None:
    assert EntityType.AADHAAR.value not in _types(AADHAAR_NO_CONTEXT)


def test_aadhaar_invalid_first_digit_not_detected() -> None:
    assert EntityType.AADHAAR.value not in _types(AADHAAR_BAD_FIRST_DIGIT)


def test_pan_positive_detected() -> None:
    hits = _hits(PAN_POSITIVE, EntityType.PAN)
    assert len(hits) == 1
    assert hits[0]["start"] < hits[0]["end"]


def test_pan_without_context_not_detected() -> None:
    assert EntityType.PAN.value not in _types(PAN_NO_CONTEXT)


def test_gstin_positive_detected() -> None:
    hits = _hits(GSTIN_POSITIVE, EntityType.GSTIN)
    assert len(hits) == 1


def test_gstin_without_context_not_detected() -> None:
    assert EntityType.GSTIN.value not in _types(GSTIN_NO_CONTEXT)


def test_voter_id_positive_detected() -> None:
    hits = _hits(VOTER_ID_POSITIVE, EntityType.VOTER_ID)
    assert len(hits) == 1


def test_voter_id_without_context_not_detected() -> None:
    assert EntityType.VOTER_ID.value not in _types(VOTER_ID_NO_CONTEXT)


def test_passport_positive_detected() -> None:
    hits = _hits(PASSPORT_POSITIVE, EntityType.PASSPORT)
    assert len(hits) == 1


def test_passport_without_context_not_detected() -> None:
    assert EntityType.PASSPORT.value not in _types(PASSPORT_NO_CONTEXT)
