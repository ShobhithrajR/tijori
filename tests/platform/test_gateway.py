"""Gateway API behaviour: sanitization, forwarding, reinsertion, audit."""

from __future__ import annotations

import json

import pytest

from app.contracts import DetectedEntity, DetectionResult, EntityType, MaskingResult
from app.pipeline.pipeline import serialize_messages
from privacy import detection, masking
from privacy.vault import PlaceholderVault

SAMPLE_TEXT = (
    "My name is Rahul Sharma. My Aadhaar number is 1234-5678-9012 "
    "and my PAN is ABCDE1234F."
)
PII_ORIGINALS = ("Rahul Sharma", "1234-5678-9012", "ABCDE1234F")


def _assert_no_originals(document: str) -> None:
    for original in PII_ORIGINALS:
        assert original not in document


def test_health(gateway) -> None:
    client, _provider, _repository = gateway
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["provider"] == "spy"
    assert body["model"] == "spy-model"


def test_sanitize_never_returns_originals(gateway) -> None:
    client, _provider, repository = gateway

    response = client.post(
        "/v1/sanitize",
        json={"text": SAMPLE_TEXT, "doc_type": "kyc", "purpose": "general"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["sanitized_text"] == (
        "My name is <PERSON_1>. My Aadhaar number is <AADHAAR_1> "
        "and my PAN is <PAN_1>."
    )
    assert body["counts"] == {"PERSON": 1, "AADHAAR": 1, "PAN": 1}
    assert [entity["placeholder"] for entity in body["entities"]] == [
        "<PERSON_1>",
        "<AADHAAR_1>",
        "<PAN_1>",
    ]
    assert "original" not in body
    assert "text" not in body["entities"][0]
    _assert_no_originals(json.dumps(body))

    record = repository.get(body["request_id"])
    assert record is not None
    assert record.task == "sanitize"
    assert record.status == "ok"
    assert record.outbound_payload == ""
    assert record.entity_counts == {"PERSON": 1, "AADHAAR": 1, "PAN": 1}


def test_process_sends_only_sanitized_text_and_reinserts(gateway) -> None:
    client, provider, repository = gateway
    instruction = "Summarize in one line."

    response = client.post(
        "/v1/process",
        json={
            "text": SAMPLE_TEXT,
            "task": "summarize",
            "instruction": instruction,
            "doc_type": "loan_application",
            "purpose": "general",
            "max_tokens": 128,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "spy"
    assert body["model"] == "spy-model"
    assert body["task"] == "summarize"
    assert body["final_text"] == "Summary: Rahul Sharma holds 1234-5678-9012 and ABCDE1234F."
    assert body["reinsertion"] == {"replaced": 3, "missing": [], "unknown": []}

    assert provider.calls == 1
    sent = provider.messages[0]
    assert sent[0].role == "system"
    assert sent[0].content == (
        "Preserve every placeholder like <PERSON_1> exactly. "
        "Never alter, guess, or invent placeholders."
    )
    assert sent[1].role == "user"
    assert sent[1].content.startswith(instruction + "\n\n")
    for message in sent:
        _assert_no_originals(message.content)

    assert body["outbound_payload"] == serialize_messages(sent)
    _assert_no_originals(body["outbound_payload"])
    assert "<PERSON_1>" in body["outbound_payload"]
    assert "<AADHAAR_1>" in body["outbound_payload"]
    assert "<PAN_1>" in body["outbound_payload"]

    record = repository.get(body["request_id"])
    assert record is not None
    assert record.status == "ok"
    assert record.task == "summarize"
    assert record.provider == "spy"
    assert record.model == "spy-model"
    assert record.outbound_payload == body["outbound_payload"]
    assert record.leakage_count == 0
    assert record.entity_counts == {"PERSON": 1, "AADHAAR": 1, "PAN": 1}
    _assert_no_originals(record.outbound_payload)

    audit = client.get(f"/v1/audit/{body['request_id']}")
    assert audit.status_code == 200
    _assert_no_originals(audit.text)
    assert "original" not in audit.json()


def test_provider_failure_returns_502_and_writes_error_audit(gateway) -> None:
    client, provider, repository = gateway
    provider.error = RuntimeError(
        "connection failed for Rahul Sharma / 1234-5678-9012 / ABCDE1234F"
    )

    response = client.post(
        "/v1/process",
        json={"text": SAMPLE_TEXT, "task": "extract", "doc_type": "kyc"},
    )

    assert response.status_code == 502
    _assert_no_originals(response.text)
    assert "request_id=req_" in response.json()["detail"]

    rows = repository.list()
    assert len(rows) == 1
    record = rows[0]
    assert record.status == "error"
    assert record.task == "extract"
    assert record.error is not None
    _assert_no_originals(record.error)
    assert "[REDACTED]" in record.error
    assert record.outbound_payload
    _assert_no_originals(record.outbound_payload)
    assert record.leakage_count == 0


def test_leaky_masker_is_blocked_before_provider(gateway, monkeypatch: pytest.MonkeyPatch) -> None:
    client, provider, repository = gateway

    def leaky_mask(text, entities):
        vault = PlaceholderVault()
        for entity in entities:
            vault.add(entity.type, entity.text)
        return MaskingResult(
            sanitized_text=text,
            mapping=vault.entries,
            entities=list(entities),
        )

    monkeypatch.setattr(masking, "mask", leaky_mask)

    response = client.post(
        "/v1/process",
        json={"text": SAMPLE_TEXT, "task": "summarize"},
    )

    assert response.status_code == 500
    _assert_no_originals(response.text)
    assert provider.calls == 0

    rows = repository.list()
    assert len(rows) == 1
    assert rows[0].status == "error"
    assert rows[0].leakage_count >= 1
    assert rows[0].outbound_payload == ""
    _assert_no_originals(rows[0].error or "")


def test_validation_errors_are_422_and_do_not_call_provider(gateway) -> None:
    client, provider, _repository = gateway

    assert client.post("/v1/sanitize", json={"text": ""}).status_code == 422
    assert (
        client.post(
            "/v1/process",
            json={"text": SAMPLE_TEXT, "task": "summarize", "max_tokens": 1},
        ).status_code
        == 422
    )
    assert provider.calls == 0


def test_audit_unknown_request_is_404(gateway) -> None:
    client, _provider, _repository = gateway
    response = client.get("/v1/audit/req_missing")
    assert response.status_code == 404
    assert response.json() == {"detail": "audit record not found"}


def test_audit_list_is_newest_first_and_respects_limit(gateway) -> None:
    client, _provider, _repository = gateway

    first = client.post("/v1/sanitize", json={"text": SAMPLE_TEXT}).json()
    second = client.post("/v1/sanitize", json={"text": SAMPLE_TEXT}).json()

    response = client.get("/v1/audit?limit=1")
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 1
    assert rows[0]["request_id"] == second["request_id"]
    assert rows[0]["request_id"] != first["request_id"]

    listing = client.get("/v1/audit?limit=50").json()
    assert [row["request_id"] for row in listing][:2] == [
        second["request_id"],
        first["request_id"],
    ]


def test_instruction_pii_is_masked_before_provider(gateway) -> None:
    client, provider, repository = gateway
    provider.reply = "Summary: <PERSON_1>."
    instruction = "Also reference Aadhaar 9999-8888-7777."

    response = client.post(
        "/v1/process",
        json={"text": SAMPLE_TEXT, "task": "summarize", "instruction": instruction},
    )

    assert response.status_code == 200
    body = response.json()
    user_content = provider.messages[0][1].content
    assert "9999-8888-7777" not in user_content
    assert "<AADHAAR_2>" in user_content
    assert "9999-8888-7777" not in body["outbound_payload"]
    assert body["final_text"] == "Summary: Rahul Sharma."

    record = repository.get(body["request_id"])
    assert record is not None
    assert record.status == "ok"
    assert record.leakage_count == 0
    assert "9999-8888-7777" not in record.outbound_payload


def test_multiline_original_is_caught_by_leakage_gate(gateway, monkeypatch: pytest.MonkeyPatch) -> None:
    client, provider, repository = gateway
    address = '12 MG Road\n"Rose" Apartments, Bengaluru 560001'
    text = f"Address: {address}"
    entity = DetectedEntity(
        type=EntityType.ADDRESS,
        start=len("Address: "),
        end=len(text),
        text=address,
        score=1.0,
        source="fake",
    )

    def detect_only_address(candidate: str, *, language: str = "auto") -> DetectionResult:
        return DetectionResult(text=candidate, entities=[entity], language="en")

    def leaky_mask(candidate: str, entities):
        vault = PlaceholderVault()
        vault.add(EntityType.ADDRESS, address)
        return MaskingResult(
            sanitized_text=candidate,
            mapping=vault.entries,
            entities=list(entities),
        )

    monkeypatch.setattr(detection, "detect", detect_only_address)
    monkeypatch.setattr(masking, "mask", leaky_mask)

    response = client.post("/v1/process", json={"text": text, "task": "summarize"})

    assert response.status_code == 500
    assert "unmasked PII" in response.text
    assert provider.calls == 0
    rows = repository.list()
    assert len(rows) == 1
    assert rows[0].status == "error"
    assert rows[0].leakage_count >= 1
    assert rows[0].outbound_payload == ""
    assert address not in (rows[0].error or "")


def test_sanitize_failure_returns_json_500_and_one_audit_row(
    gateway,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _provider, repository = gateway

    def exploding_detect(candidate: str, *, language: str = "auto") -> DetectionResult:
        raise RuntimeError(f"detector exploded on {candidate}")

    monkeypatch.setattr(detection, "detect", exploding_detect)

    response = client.post("/v1/sanitize", json={"text": SAMPLE_TEXT})

    assert response.status_code == 500
    detail = response.json()["detail"]
    assert "request_id=req_" in detail
    _assert_no_originals(response.text)

    rows = repository.list()
    assert len(rows) == 1
    assert rows[0].status == "error"
    assert rows[0].task == "sanitize"
    assert "Rahul Sharma" not in (rows[0].error or "")
