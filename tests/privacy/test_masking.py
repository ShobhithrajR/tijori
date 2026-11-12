"""Masking tests: placeholders, consistency, zero leakage."""

from __future__ import annotations

from app.contracts import DetectedEntity, EntityType
from privacy.detection import detect
from privacy.masking import mask

AADHAAR_VALUE = "223456789012"
MASKED_TEXT = (
    "My name is Rahul Sharma. My Aadhaar number is 2234 5678 9012 "
    "and my PAN is ABCDE1234F."
)


def test_mask_replaces_entities_with_placeholders() -> None:
    result = mask(MASKED_TEXT, detect(MASKED_TEXT).entities)
    sanitized = result.sanitized_text
    assert "<PERSON_1>" in sanitized
    assert "<PAN_1>" in sanitized
    assert AADHAAR_VALUE not in sanitized
    assert "Rahul Sharma" not in sanitized
    assert "ABCDE1234F" not in sanitized


def test_mask_zero_leakage() -> None:
    result = mask(MASKED_TEXT, detect(MASKED_TEXT).entities)
    assert result.mapping
    for entry in result.mapping:
        assert entry.original not in result.sanitized_text
        if entry.type == EntityType.AADHAAR:
            stripped = "".join(ch for ch in entry.original if ch.isdigit())
            assert stripped not in result.sanitized_text


def test_mask_reuses_placeholder_for_repeated_value() -> None:
    text = "Aadhaar is 223456789012 and again 223456789012 here."
    first = text.index("223456789012")
    second = text.index("223456789012", first + 1)
    entities = [
        DetectedEntity(type=EntityType.AADHAAR, start=first, end=first + 12, text="223456789012", score=0.9, source="presidio"),
        DetectedEntity(type=EntityType.AADHAAR, start=second, end=second + 12, text="223456789012", score=0.9, source="presidio"),
    ]
    result = mask(text, entities)
    assert len(result.mapping) == 1
    assert result.mapping[0].occurrences == 2
    assert result.mapping[0].placeholder == "<AADHAAR_1>"
    assert result.sanitized_text.count("<AADHAAR_1>") == 2
    assert "223456789012" not in result.sanitized_text
