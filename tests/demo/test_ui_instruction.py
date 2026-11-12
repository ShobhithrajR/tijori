"""Instruction and API-key checks with a stubbed gateway (no network)."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[2] / "ui" / "app.py"

DEFAULT_INSTRUCTION = "Summarize in 3 bullet points and keep all placeholders."
CUSTOM_INSTRUCTION = "Extract only the applicant name and PAN. Keep <PERSON_1> exactly."
AUTH_ERROR = "Gateway rejected the API key (check TIJORI_API_KEY)"


class FakeResponse:
    def __init__(self, payload, status_code: int = 200, method: str = "GET"):
        self._payload = payload
        self.status_code = status_code
        self.text = json.dumps(payload)
        self._request = httpx.Request(method, "http://stub")

    def json(self):
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"{self.status_code} response",
                request=self._request,
                response=httpx.Response(
                    self.status_code,
                    request=self._request,
                    json=self._payload,
                ),
            )


PROCESS_PAYLOAD = {
    "request_id": "req_test",
    "final_text": "• Applicant: <PERSON_1>\n• PAN: <PAN_1>\n• Loan: Rs 12,00,000.",
    "sanitized_text": "Applicant: <PERSON_1>, PAN: <PAN_1>.",
    "outbound_payload": "Summarize: <PERSON_1> <PAN_1>.",
    "entities": [],
    "provider": "stub",
    "model": "stub-1",
    "task": "summarize",
    "latency_ms": 12,
    "reinsertion": {"replaced": 0, "missing": [], "unknown": []},
}


def fake_get(calls: dict, audit_status: int = 200):
    def get(url, *args, **kwargs):
        calls["get"].append({"url": url, "headers": kwargs.get("headers")})
        if url.endswith("/health"):
            return FakeResponse({"status": "ok", "provider": "stub", "model": "stub-1"})
        if audit_status == 200:
            return FakeResponse([])
        return FakeResponse({"detail": "unauthorized"}, audit_status)

    return get


def fake_post(calls: dict, status_code: int):
    def post(url, *args, **kwargs):
        calls["post"].append(
            {"url": url, "json": kwargs.get("json"), "headers": kwargs.get("headers")}
        )
        if status_code == 401:
            return FakeResponse({"detail": "unauthorized"}, 401, "POST")
        return FakeResponse(PROCESS_PAYLOAD)

    return post


def run_app(
    monkeypatch,
    instruction: str | None = None,
    api_key: str | None = None,
    post_status: int = 200,
    audit_status: int = 200,
) -> tuple[AppTest, dict]:
    calls: dict = {"get": [], "post": []}
    monkeypatch.setenv("TIJORI_API_URL", "http://stub")
    if api_key is None:
        monkeypatch.delenv("TIJORI_API_KEY", raising=False)
    else:
        monkeypatch.setenv("TIJORI_API_KEY", api_key)
    monkeypatch.setattr(httpx, "get", fake_get(calls, audit_status))
    monkeypatch.setattr(httpx, "post", fake_post(calls, post_status))

    app = AppTest.from_file(str(APP), default_timeout=30).run()
    assert not app.exception, app.exception

    if instruction is not None:
        next(item for item in app.text_area if item.key == "instruction").set_value(instruction)
        app.run()
        assert not app.exception, app.exception

    button = next(button for button in app.button if button.label == "Run gateway")
    assert not button.disabled
    button.click().run()
    assert not app.exception, app.exception
    return app, calls


def test_default_instruction_is_sent(monkeypatch):
    app, calls = run_app(monkeypatch)
    assert calls["post"][0]["json"]["instruction"] == DEFAULT_INSTRUCTION
    assert any(
        caption.value.startswith("Instruction sent: Summarize in 3 bullet points")
        for caption in app.caption
    )


def test_custom_instruction_replaces_default(monkeypatch):
    app, calls = run_app(monkeypatch, instruction=CUSTOM_INSTRUCTION)
    assert calls["post"][0]["json"]["instruction"] == CUSTOM_INSTRUCTION
    assert any(
        caption.value == f"Instruction sent: {CUSTOM_INSTRUCTION}" for caption in app.caption
    )


def test_empty_instruction_is_omitted(monkeypatch):
    _app, calls = run_app(monkeypatch, instruction="   ")
    assert "instruction" not in calls["post"][0]["json"]


def test_api_key_is_sent_when_configured(monkeypatch):
    app, calls = run_app(monkeypatch, api_key="test-key-123")

    assert calls["post"][0]["headers"]["X-API-Key"] == "test-key-123"
    audit_calls = [call for call in calls["get"] if call["url"].endswith("/v1/audit")]
    assert audit_calls
    assert all(call["headers"]["X-API-Key"] == "test-key-123" for call in audit_calls)
    health_calls = [call for call in calls["get"] if call["url"].endswith("/health")]
    assert health_calls
    assert all("X-API-Key" not in (call["headers"] or {}) for call in health_calls)

    rendered = " ".join(
        str(element.value)
        for group in (app.caption, app.code, app.info, app.success, app.error, app.warning)
        for element in group
    )
    assert "test-key-123" not in rendered
    assert all("test-key-123" not in str(widget.value) for widget in app.text_area)
    assert all("test-key-123" not in str(widget.value) for widget in app.text_input)


@pytest.mark.parametrize("api_key", [None, ""])
def test_api_key_header_is_absent_without_key(monkeypatch, api_key):
    app, calls = run_app(monkeypatch, api_key=api_key)

    assert "X-API-Key" not in calls["post"][0]["headers"]
    audit_calls = [call for call in calls["get"] if call["url"].endswith("/v1/audit")]
    assert audit_calls
    assert all("X-API-Key" not in (call["headers"] or {}) for call in audit_calls)


def test_401_shows_actionable_message_without_traceback(monkeypatch):
    app, _calls = run_app(monkeypatch, post_status=401)

    assert not app.exception, app.exception
    assert any(AUTH_ERROR in element.value for element in app.error)


def test_audit_401_shows_actionable_message(monkeypatch):
    app, _calls = run_app(monkeypatch, audit_status=401)

    assert not app.exception, app.exception
    assert any(AUTH_ERROR in element.value for element in app.info)


def test_instruction_renders_when_api_is_offline(monkeypatch):
    monkeypatch.setenv("TIJORI_API_URL", "http://127.0.0.1:9")
    monkeypatch.delenv("TIJORI_API_KEY", raising=False)

    def offline_get(*args, **kwargs):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(httpx, "get", offline_get)
    app = AppTest.from_file(str(APP), default_timeout=30).run()

    assert not app.exception, app.exception
    assert any("API offline" in element.value for element in app.error)
    assert [tab.label for tab in app.tabs] == ["Gateway demo", "Audit browser"]
    instruction = next(item for item in app.text_area if item.key == "instruction")
    assert instruction.value == DEFAULT_INSTRUCTION
