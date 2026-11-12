from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.contracts import (
    DetectedEntity,
    EntityType,
    MaskedEntityView,
    SanitizeResponse,
    make_placeholder,
)
from privacy.vault import PlaceholderVault


def test_placeholder_grammar() -> None:
    assert make_placeholder(EntityType.PERSON, 1) == "<PERSON_1>"
    assert make_placeholder(EntityType.VOTER_ID, 12) == "<VOTER_ID_12>"
    with pytest.raises(ValueError):
        make_placeholder(EntityType.PERSON, 0)


def test_masked_entity_view_has_no_original() -> None:
    fields = MaskedEntityView.model_fields
    assert "original" not in fields
    assert "text" not in fields


def test_sanitize_response_never_serialises_a_mapping() -> None:
    response = SanitizeResponse(
        request_id="req_test",
        sanitized_text="My name is <PERSON_1>.",
        entities=[
            MaskedEntityView(type=EntityType.PERSON, placeholder="<PERSON_1>", start=11, end=23)
        ],
        counts={"PERSON": 1},
    )
    dumped = response.model_dump_json()
    assert "original" not in dumped
    assert "Rahul" not in dumped


def test_span_must_be_ordered() -> None:
    with pytest.raises(ValidationError):
        DetectedEntity(type=EntityType.PERSON, start=10, end=10, text="x")


def test_vault_reuses_placeholders_for_equivalent_values() -> None:
    vault = PlaceholderVault()
    a = vault.add(EntityType.AADHAAR, "1234-5678-9012")
    b = vault.add(EntityType.AADHAAR, "1234 5678 9012")
    assert a == b == "<AADHAAR_1>"

    c = vault.add(EntityType.PERSON, "Rahul Sharma")
    d = vault.add(EntityType.PERSON, "rahul  sharma")
    assert c == d == "<PERSON_1>"


def test_vault_counters_are_per_type_and_ordered() -> None:
    vault = PlaceholderVault()
    assert vault.add(EntityType.PERSON, "Rahul Sharma") == "<PERSON_1>"
    assert vault.add(EntityType.PAN, "ABCDE1234F") == "<PAN_1>"
    assert vault.add(EntityType.PERSON, "Anita Rao") == "<PERSON_2>"
    assert [e.placeholder for e in vault.entries] == ["<PERSON_1>", "<PAN_1>", "<PERSON_2>"]


def test_vault_resolve_is_case_insensitive() -> None:
    vault = PlaceholderVault()
    vault.add(EntityType.PERSON, "Rahul Sharma")
    assert vault.resolve("<person_1>") == "Rahul Sharma"
    assert vault.resolve("<PERSON_2>") is None
