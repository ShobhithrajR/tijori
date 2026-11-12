"""Reinsertion tests: exact tokens, reorder, dropped and malformed placeholders."""

from __future__ import annotations

from app.contracts import EntityType, PlaceholderEntry
from privacy.reinsertion import reinsert


def _entry(entity_type: EntityType, number: int, original: str) -> PlaceholderEntry:
    return PlaceholderEntry(placeholder=f"<{entity_type.value}_{number}>", type=entity_type, original=original)


def test_reinsert_substitutes_exact_tokens() -> None:
    mapping = [PlaceholderEntry(placeholder="<PERSON_1>", type=EntityType.PERSON, original="Rahul Sharma")]
    result = reinsert("Thanks <PERSON_1>, noted.", mapping)
    assert result.replaced == 1
    assert result.missing == []
    assert result.unknown == []
    assert result.text == "Thanks Rahul Sharma, noted."


def test_reinsert_after_reorder() -> None:
    mapping = [
        _entry(EntityType.PERSON, 1, "Rahul Sharma"),
        _entry(EntityType.PERSON, 2, "Anita Rao"),
    ]
    result = reinsert("<PERSON_2> called <PERSON_1> today.", mapping)
    assert result.replaced == 2
    assert result.text == "Anita Rao called Rahul Sharma today."
    assert result.missing == []


def test_reinsert_dropped_placeholder_is_missing() -> None:
    mapping = [
        _entry(EntityType.PERSON, 1, "Rahul Sharma"),
        _entry(EntityType.AADHAAR, 1, "1234-5678-9012"),
    ]
    result = reinsert("No tokens in this reply at all.", mapping)
    assert result.replaced == 0
    assert result.text == "No tokens in this reply at all."
    assert result.missing == ["<PERSON_1>", "<AADHAAR_1>"]


def test_reinsert_malformed_token_is_unknown_and_untouched() -> None:
    mapping = [_entry(EntityType.PERSON, 1, "Rahul Sharma")]
    result = reinsert("Bad <PERSON 1> token and <PERSON_1> ok.", mapping)
    assert result.replaced == 1
    assert "<PERSON 1>" in result.unknown
    assert result.text == "Bad <PERSON 1> token and Rahul Sharma ok."


def test_reinsert_unknown_valid_token_not_in_mapping() -> None:
    mapping = [_entry(EntityType.PERSON, 1, "Rahul Sharma")]
    result = reinsert("Please use <PERSON_99> going forward.", mapping)
    assert result.replaced == 0
    assert result.text == "Please use <PERSON_99> going forward."
    assert result.unknown == ["<PERSON_99>"]


def test_reinsert_no_cross_person_substitution() -> None:
    mapping = [
        _entry(EntityType.PERSON, 1, "Rahul Sharma"),
        _entry(EntityType.PERSON, 2, "Anita Rao"),
    ]
    result = reinsert("<PERSON_2> -> <PERSON_1>.", mapping)
    assert "Anita Rao" in result.text
    assert "Rahul Sharma" in result.text
    assert "<PERSON_" not in result.text
