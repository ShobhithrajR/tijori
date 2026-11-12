"""Reinsertion behaviour under realistic LLM editing (PS-02 criterion 3).

The contract allows exact-token substitution only: reordered or duplicated
tokens are fine, dropped tokens are reported as ``missing``, and malformed
tokens are reported as ``unknown`` but never repaired. These cases are
deterministic and do not call the model.
"""

from __future__ import annotations

import pytest

from app.contracts import EntityType, PlaceholderEntry
from privacy.reinsertion import reinsert

MAPPING = [
    PlaceholderEntry(placeholder="<PERSON_1>", type=EntityType.PERSON, original="Rahul Sharma"),
    PlaceholderEntry(
        placeholder="<AADHAAR_1>", type=EntityType.AADHAAR, original="2234-5678-9012"
    ),
    PlaceholderEntry(placeholder="<PAN_1>", type=EntityType.PAN, original="ABCDE1234F"),
    PlaceholderEntry(placeholder="<PHONE_1>", type=EntityType.PHONE, original="9876543210"),
]


def test_reordered_placeholders_are_restored() -> None:
    result = reinsert("Verified <PAN_1> and <AADHAAR_1> for <PERSON_1>.", MAPPING)
    assert result.text == "Verified ABCDE1234F and 2234-5678-9012 for Rahul Sharma."
    assert result.replaced == 3
    assert result.unknown == []


def test_duplicated_placeholders_are_all_restored() -> None:
    result = reinsert("<PERSON_1> is <PERSON_1>; Aadhaar <AADHAAR_1> / <AADHAAR_1>.", MAPPING)
    assert result.text == "Rahul Sharma is Rahul Sharma; Aadhaar 2234-5678-9012 / 2234-5678-9012."
    assert result.replaced == 4
    assert result.unknown == []


def test_placeholder_case_is_tolerated() -> None:
    result = reinsert("ok <aadhaar_1> and <Pan_1>", MAPPING)
    assert result.text == "ok 2234-5678-9012 and ABCDE1234F"
    assert result.replaced == 2


def test_dropped_placeholders_are_reported_missing() -> None:
    result = reinsert("Verified <PAN_1>.", MAPPING)
    assert result.replaced == 1
    assert set(result.missing) == {"<PERSON_1>", "<AADHAAR_1>", "<PHONE_1>"}
    assert result.unknown == []


@pytest.mark.parametrize(
    "text, token",
    [
        ("bad <AADHAAR_1 > here", "<AADHAAR_1 >"),
        ("bad <AADHAAR-1> here", "<AADHAAR-1>"),
        ("bad <AADHAAR_1 here", "<AADHAAR_1"),
    ],
)
def test_malformed_tokens_are_reported_unknown_not_repaired(text: str, token: str) -> None:
    result = reinsert(text, MAPPING)
    assert result.replaced == 0
    assert token in result.unknown
    assert "<AADHAAR_1>" not in result.text or token == "<AADHAAR_1>"
    assert "2234-5678-9012" not in result.text


def test_unclosed_token_mid_sentence_is_reported() -> None:
    """Regression: unclosed tokens used to be detected only at end of line."""
    result = reinsert("The model wrote <AADHAAR_1 and stopped.", MAPPING)
    assert "<AADHAAR_1" in result.unknown
    assert result.replaced == 0


def test_unknown_index_is_reported_not_invented() -> None:
    result = reinsert("seen <PAN_9> here", MAPPING)
    assert result.replaced == 0
    assert result.unknown == ["<PAN_9>"]
    assert result.text == "seen <PAN_9> here"


def test_plain_angle_brackets_are_ignored() -> None:
    result = reinsert("html <b> and <p> tags", MAPPING)
    assert result.unknown == []
    assert result.text == "html <b> and <p> tags"
