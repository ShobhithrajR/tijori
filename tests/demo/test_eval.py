"""Checks for the pure evaluation helpers (no gateway needed)."""

from __future__ import annotations

from evaluation.run import leak_occurrences, percentile, score_predictions


def test_aadhaar_leak_is_detected_in_stripped_form():
    entity = {"type": "AADHAAR", "text": "1234 5678 9012"}
    assert leak_occurrences(entity, "masked 123456789012") == 1


def test_clean_payload_has_zero_leaks():
    entity = {"type": "PERSON", "text": "Rahul Sharma"}
    assert leak_occurrences(entity, "My name is <PERSON_1>.") == 0


def test_leak_match_is_case_insensitive_for_text():
    entity = {"type": "PERSON", "text": "Rahul Sharma"}
    assert leak_occurrences(entity, "rahul sharma is here") == 1


def test_exact_span_and_type_matching():
    doc = {
        "entities": [
            {"type": "PERSON", "text": "Rahul Sharma", "start": 11, "end": 23},
            {"type": "AADHAAR", "text": "123456789012", "start": 47, "end": 59},
        ]
    }
    response = {
        "entities": [
            {"type": "PERSON", "placeholder": "<PERSON_1>", "start": 11, "end": 23},
            {"type": "AADHAAR", "placeholder": "<AADHAAR_1>", "start": 47, "end": 58},
        ]
    }
    per_type, totals = score_predictions(doc, response)
    assert totals == {"tp": 1, "fp": 1, "fn": 1}
    assert per_type["PERSON"] == [1, 0, 0]
    assert per_type["AADHAAR"] == [0, 1, 1]


def test_percentile_interpolates():
    assert percentile([], 50) is None
    assert percentile([10], 95) == 10
    assert percentile([10, 20], 50) == 15
    assert percentile([1, 2, 3, 4, 5], 95) == 4.8
