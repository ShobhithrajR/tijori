"""Dataset contract checks (CONTRACT.md sections 2 and 8)."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

import pytest

from data import generate

DATASET = Path(__file__).resolve().parents[2] / "data" / "dataset.jsonl"
MANDATORY = {"AADHAAR", "PAN", "GSTIN", "VOTER_ID", "PASSPORT", "PERSON", "ADDRESS"}
OPTIONAL = {"PHONE", "EMAIL", "DOB", "BANK_ACCOUNT", "CREDIT_CARD", "OTHER"}


def read_dataset() -> list[dict]:
    return [json.loads(line) for line in DATASET.read_text(encoding="utf-8").splitlines() if line.strip()]


@pytest.fixture(scope="module")
def docs() -> list[dict]:
    return read_dataset()


def luhn_ok(number: str) -> bool:
    total = 0
    for index, char in enumerate(reversed(number)):
        digit = int(char)
        if index % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


def test_file_is_committed_and_matches_generator(docs):
    assert docs == generate.build_documents(), "data/dataset.jsonl is stale; rerun python -m data.generate"


def test_exactly_50_unique_ids(docs):
    assert len(docs) == 50
    assert len({doc["id"] for doc in docs}) == 50


def test_doc_type_minimums(docs):
    counts = Counter(doc["doc_type"] for doc in docs)
    for doc_type in ("loan_application", "kyc", "support_ticket", "insurance_claim"):
        assert counts[doc_type] >= 10, f"{doc_type} has only {counts[doc_type]} documents"


def test_language_minimums(docs):
    counts = Counter(doc["language"] for doc in docs)
    assert counts["hi-en"] >= 15
    assert counts["en"] + counts["hi-en"] == 50


def test_spans_are_exact_and_ordered(docs):
    for doc in docs:
        entities = doc["entities"]
        assert entities, f"{doc['id']} has no entities"
        for entity in entities:
            assert doc["text"][entity["start"]:entity["end"]] == entity["text"], doc["id"]
            assert entity["end"] > entity["start"]
        for previous, current in zip(entities, entities[1:]):
            assert previous["end"] <= current["start"], f"overlapping spans in {doc['id']}"


def test_entity_type_coverage(docs):
    counts = Counter(entity["type"] for doc in docs for entity in doc["entities"])
    for entity_type in MANDATORY | OPTIONAL:
        assert counts[entity_type] >= 10, f"{entity_type} appears only {counts[entity_type]} times"


def test_indian_formats(docs):
    for doc in docs:
        for entity in doc["entities"]:
            value = entity["text"]
            entity_type = entity["type"]
            if entity_type == "AADHAAR":
                assert len(re.sub(r"[\s-]", "", value)) == 12
            elif entity_type == "PAN":
                assert re.fullmatch(r"[A-Z]{5}[0-9]{4}[A-Z]", value), value
            elif entity_type == "GSTIN":
                assert re.fullmatch(r"[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9A-Z]Z[0-9A-Z]", value), value
                assert generate.gstin_checksum(value[:14]) == value[14], value
            elif entity_type == "VOTER_ID":
                assert re.fullmatch(r"[A-Z]{3}[0-9]{7}", value), value
            elif entity_type == "PASSPORT":
                assert re.fullmatch(r"[A-Z][0-9]{7}", value), value
            elif entity_type == "PHONE":
                digits = re.sub(r"[\s-]", "", value).removeprefix("+91").removeprefix("0")
                assert len(digits) == 10 and digits[0] in "6789", value
            elif entity_type == "EMAIL":
                assert re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value), value
            elif entity_type == "DOB":
                assert re.search(r"\b(19|20)\d{2}\b", value), value
            elif entity_type == "ADDRESS":
                assert re.search(r"\b\d{6}\b", value), value
            elif entity_type == "BANK_ACCOUNT":
                assert re.fullmatch(r"[0-9]{12,15}", value), value
            elif entity_type == "CREDIT_CARD":
                digits = re.sub(r"\s", "", value)
                assert len(digits) == 16 and luhn_ok(digits), value
            elif entity_type == "OTHER":
                assert re.fullmatch(r"(POL|CUST|REF)-[0-9-]+", value), value
            elif entity_type == "PERSON":
                assert re.fullmatch(r"[A-Za-z]+ [A-Za-z]+", value), value


def test_generator_is_deterministic():
    assert generate.build_documents() == generate.build_documents()
