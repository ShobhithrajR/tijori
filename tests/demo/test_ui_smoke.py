"""Headless smoke test: the demo must render with the API offline."""

from __future__ import annotations

import os
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[2] / "ui" / "app.py"


def test_ui_renders_when_api_is_offline():
    os.environ["TIJORI_API_URL"] = "http://127.0.0.1:9"
    app = AppTest.from_file(str(APP), default_timeout=30)
    app.run()
    assert not app.exception, app.exception
    assert any("API offline" in element.value for element in app.error)
    # The three panes are still present.
    assert [tab.label for tab in app.tabs] == ["Gateway demo", "Audit browser"]
