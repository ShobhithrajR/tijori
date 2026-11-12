"""India-specific PII recognizers built on Presidio ``PatternRecognizer``."""

from __future__ import annotations

import re
from typing import Any

from app.contracts import EntityType
from presidio_analyzer import AnalyzerEngine, PatternRecognizer
from presidio_analyzer.pattern import Pattern
from presidio_analyzer.recognizer_registry import RecognizerRegistry

AADHAAR_REGEX = r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}\b"
PAN_REGEX = r"\b[A-Z]{5}[0-9]{4}[A-Z]\b"
GSTIN_REGEX = r"\b\d{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]\b"
VOTER_ID_REGEX = r"\b[A-Z]{3}[0-9]{7}\b"
PASSPORT_REGEX = r"\b[A-Z][0-9]{7}\b"

AADHAAR_CONTEXTS = ("aadhaar", "aadhar", "uidai", "आधार", "aadhaar number")
PAN_CONTEXTS = ("pan", "income tax", "pan card")
GSTIN_CONTEXTS = ("gstin", "gst", "goods and services tax")
VOTER_ID_CONTEXTS = ("voter", "voters", "epic", "election", "electoral", "voting", "voter id")
PASSPORT_CONTEXTS = ("passport", "passport number")

RECOGNIZER_SPECS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("AADHAAR", AADHAAR_REGEX, AADHAAR_CONTEXTS),
    ("PAN", PAN_REGEX, PAN_CONTEXTS),
    ("GSTIN", GSTIN_REGEX, GSTIN_CONTEXTS),
    ("VOTER_ID", VOTER_ID_REGEX, VOTER_ID_CONTEXTS),
    ("PASSPORT", PASSPORT_REGEX, PASSPORT_CONTEXTS),
)


def _as_type_name(value: Any) -> str:
    return str(getattr(value, "value", value) or value)


def _as_context(entity_type: str) -> tuple[str, ...]:
    for name, _regex, context in RECOGNIZER_SPECS:
        if name == entity_type:
            return context
    return ()


def _context_regex(context_word: str) -> str:
    if re.match(r"[\u0900-\u097F]", context_word):
        return re.escape(context_word)
    return r"\b" + re.escape(context_word) + r"\b"


def _has_context(text: str, start: int, end: int, context: tuple[str, ...]) -> bool:
    """True when a context word appears near the detected span."""
    window = text[max(0, start - 40) : min(len(text), end + 40)].lower()
    for word in context:
        if not word:
            continue
        if re.search(_context_regex(word), window, re.IGNORECASE):
            return True
    return False


def _is_valid_aadhaar(start: int, end: int, text: str) -> bool:
    digits = re.sub(r"[\s-]", "", text[start:end])
    return len(digits) == 12 and digits[0] in "23456789"


def _make_recognizer(entity_type: str, regex: str, context: tuple[str, ...]) -> PatternRecognizer:
    return PatternRecognizer(
        supported_entity=entity_type,
        patterns=[Pattern(name=entity_type.lower(), regex=regex, score=0.85)],
        context=list(context),
    )


_RECOGNIZERS: list[PatternRecognizer] = [
    _make_recognizer(entity_type, regex, context)
    for entity_type, regex, context in RECOGNIZER_SPECS
]

_ENGINE: AnalyzerEngine | None = None


def get_engine() -> AnalyzerEngine:
    global _ENGINE
    if _ENGINE is None:
        registry = RecognizerRegistry(recognizers=_RECOGNIZERS)
        _ENGINE = AnalyzerEngine(registry=registry)
    return _ENGINE


def recognize(text: str) -> list[dict[str, Any]]:
    """Run the India recognizers over ``text`` and return normalized hits."""
    engine = get_engine()
    results = engine.analyze(text=text, language="en", entities=[e for e, _, _ in RECOGNIZER_SPECS])

    hits: list[dict[str, Any]] = []
    for result in results:
        entity_type = _as_type_name(result.entity_type)
        entity = EntityType(entity_type)
        start = int(result.start)
        end = int(result.end)
        context = _as_context(entity_type)
        if context and not _has_context(text, start, end, context):
            continue
        if entity is EntityType.AADHAAR and not _is_valid_aadhaar(start, end, text):
            continue
        hits.append(
            {
                "type": entity,
                "start": start,
                "end": end,
                "score": float(result.score),
                "source": "presidio",
            }
        )
    return hits
