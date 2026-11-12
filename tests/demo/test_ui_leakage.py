"""End-to-end UI badge checks with a stubbed gateway (no network)."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import httpx
from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[2] / "ui" / "app.py"
DATASET = Path(__file__).resolve().parents[2] / "data" / "dataset.jsonl"


class FakeResponse:
    def __init__(self, payload: dict):
        self._payload = payload
        self.status_code = 200
        self.text = json.dumps(payload)

    def json(self) -> dict:
        return self._payload

    def raise_for_status(self) -> None:
        return None


def first_document() -> dict:
    line = DATASET.read_text(encoding="utf-8").splitlines()[0]
    return json.loads(line)


def masked_views(doc: dict) -> list[dict]:
    counters: Counter = Counter()
    views = []
    for entity in doc["entities"]:
        counters[entity["type"]] += 1
        views.append({
            "type": entity["type"],
            "placeholder": f"<{entity['type']}_{counters[entity['type']]}>",
            "start": entity["start"],
            "end": entity["end"],
        })
    return views


def run_app(monkeypatch, outbound: str) -> AppTest:
    doc = first_document()
    views = masked_views(doc)
    process_payload = {
        "request_id": "req_test",
        "final_text": "Summary with placeholders restored.",
        "sanitized_text": " ".join(view["placeholder"] for view in views),
        "outbound_payload": outbound,
        "entities": views,
        "provider": "stub",
        "model": "stub-1",
        "task": "summarize",
        "latency_ms": 12,
        "reinsertion": {"replaced": len(views), "missing": [], "unknown": []},
    }

    monkeypatch.setenv("TIJORI_API_URL", "http://stub")
    monkeypatch.setattr(
        httpx, "get",
        lambda *args, **kwargs: FakeResponse({"status": "ok", "provider": "stub", "model": "stub-1"}),
    )
    monkeypatch.setattr(httpx, "post", lambda *args, **kwargs: FakeResponse(process_payload))

    app = AppTest.from_file(str(APP), default_timeout=30).run()
    assert not app.exception, app.exception
    button = next(button for button in app.button if button.label == "Run gateway")
    assert not button.disabled
    button.click().run()
    assert not app.exception, app.exception
    return app


def test_badge_is_green_when_outbound_has_no_raw_values(monkeypatch):
    app = run_app(monkeypatch, "Please summarize: <PERSON_1> <AADHAAR_1>.")
    assert any("No raw PII in outbound payload" in item.value for item in app.success)


def test_badge_is_red_when_outbound_leaks_a_raw_value(monkeypatch):
    app = run_app(monkeypatch, first_document()["text"])
    assert any("Leakage" in item.value for item in app.error)
    assert not any("No raw PII in outbound payload" in item.value for item in app.success)


def test_sample_loader_fills_the_editor():
    samples = [
        json.loads(line)
        for line in DATASET.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    target = next(doc for doc in samples if doc["id"] == "kyc_002")
    app = AppTest.from_file(str(APP), default_timeout=30).run()
    sample_select = next(item for item in app.selectbox if item.label == "Sample document")
    sample_select.set_value("kyc_002")
    app.run()
    next(button for button in app.button if button.label == "Load sample").click()
    app.run()
    assert not app.exception, app.exception
    editor = next(item for item in app.text_area if item.key == "original_text")
    assert editor.value == target["text"]
