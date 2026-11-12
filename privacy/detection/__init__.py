"""Local PII detection (lane 1).

Implement Presidio + India recognizers + GLiNER/spaCy here.
The signature and return type are frozen in CONTRACT.md §3.
"""

from __future__ import annotations

from app.contracts import DetectionResult


def detect(text: str, *, language: str = "auto") -> DetectionResult:
    raise NotImplementedError(
        "Lane 1: implement Presidio India recognizers + GLiNER NER detection."
    )
