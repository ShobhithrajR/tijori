"""NER for names and addresses: GLiNER (multi-PII) + spaCy en_core_web_sm."""

from __future__ import annotations

from typing import Any

from app.contracts import DetectedEntity, EntityType

GLINER_MODEL_ID = "urchade/gliner_multi_pii-v1"
GLINER_LABELS = ["person", "name", "address", "location"]
GLINER_THRESHOLD = 0.4

_gliner = None
_nlp = None


def get_gliner():
    global _gliner
    if _gliner is None:
        from gliner import GLiNER

        _gliner = GLiNER.from_pretrained(GLINER_MODEL_ID)
    return _gliner


def get_nlp():
    global _nlp
    if _nlp is None:
        import spacy

        _nlp = spacy.load("en_core_web_sm")
    return _nlp


def _score(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _text_of(value: Any) -> str:
    if isinstance(value, str):
        return value
    return str(getattr(value, "text", value) or "")


def _gliner_hits(text: str) -> list[DetectedEntity]:
    ner = get_gliner()
    raw = ner.predict_entities(text, GLINER_LABELS, threshold=GLINER_THRESHOLD)
    hits: list[DetectedEntity] = []
    for entity in raw or []:
        label = str(_text_of(_field(entity, "label"))).lower()
        if label in ("person", "name"):
            entity_type = EntityType.PERSON
        elif label in ("address", "location"):
            entity_type = EntityType.ADDRESS
        else:
            continue
        start = int(_field(entity, "start") or 0)
        end = int(_field(entity, "end") or 0)
        if end <= start or end > len(text):
            continue
        hits.append(
            DetectedEntity(
                type=entity_type,
                start=start,
                end=end,
                text=text[start:end],
                score=min(1.0, max(0.0, _score(_field(entity, "score", 0.5)))),
                source="gliner",
            )
        )
    return hits


def _field(entity: Any, name: str, default: Any = None) -> Any:
    if isinstance(entity, dict):
        return entity.get(name, default)
    return getattr(entity, name, default)


def _spacy_hits(text: str) -> list[DetectedEntity]:
    nlp = get_nlp()
    doc = nlp(text)
    hits: list[DetectedEntity] = []
    for ent in doc.ents:
        label = str(ent.label or "")
        if label == "PERSON":
            entity_type = EntityType.PERSON
        elif label in ("GPE", "LOC"):
            entity_type = EntityType.ADDRESS
        else:
            continue
        if ent.end_char <= ent.start_char or ent.end_char > len(text):
            continue
        score = _score(getattr(ent, "score", 0.5))
        hits.append(
            DetectedEntity(
                type=entity_type,
                start=int(ent.start_char),
                end=int(ent.end_char),
                text=text[int(ent.start_char) : int(ent.end_char)],
                score=score,
                source="spacy",
            )
        )
    return hits


def entities(text: str) -> list[DetectedEntity]:
    """Run GLiNER + spaCy NER; GLiNER failure falls back to spaCy."""
    found: list[DetectedEntity] = []
    try:
        found.extend(_gliner_hits(text))
    except Exception:
        found = []
    if not found:
        found.extend(_spacy_hits(text))
    return found
