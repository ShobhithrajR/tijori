"""Exact-token local reinsertion (lane 1).

See CONTRACT.md §3: no fuzzy matching, no repairs, no cross-entity guessing.
"""

from __future__ import annotations

import re
import time

from app.contracts import PLACEHOLDER_RE, PLACEHOLDER_SCAN_RE, PlaceholderEntry, ReinsertionResult

# Lenient scanner used ONLY to *spot* placeholder-looking tokens that are
# malformed (e.g. "<PERSON 1>", "<PERSON-1>", "<PERSON_1").  Well-formed tokens
# are handled exclusively by PLACEHOLDER_SCAN_RE; malformed ones are never
# repaired, only reported as unknown.
_MALFORMED_TOKEN_RE = re.compile(r"<[A-Za-z][A-Za-z0-9_]*[^<>\n]{0,30}>")
#: Unclosed token anywhere in a line, e.g. "<AADHAAR_1 and ...". The lookahead
#: stops at whitespace/punctuation so a well-formed "<AADHAAR_1>" never matches.
_MALFORMED_UNCLOSED_RE = re.compile(
    r"<[A-Za-z][A-Za-z0-9_]*(?:[\s_-]+\d+)?(?=[\s,.;:)\]]|$)"
)
_MALFORMED_CANONICAL_RE = re.compile(r"^<\s*([A-Za-z]+)[\s_ -]*(\d*)[\s_ -]*>?$")


def _canonical(token: str) -> str | None:
    """Canonical ``<TYPE_N>`` form of a placeholder-ish token, else None."""
    match = _MALFORMED_CANONICAL_RE.match(token.strip())
    if match is None:
        return None
    entity_type = match.group(1).upper()
    digits = match.group(2)
    if not digits.isdigit() or int(digits) < 1:
        return None
    return f"<{entity_type}_{int(digits)}>"


def _lookup_key(placeholder: str) -> tuple[str, int] | None:
    match = PLACEHOLDER_RE.match(placeholder)
    if match is None:
        return None
    return (match.group(1), int(match.group(2)))


def _add_unknown(unknown: list[str], seen: set[str], canonical: str) -> None:
    if canonical in seen:
        return
    seen.add(canonical)
    unknown.append(canonical)


def reinsert(
    text: str,
    mapping: list[PlaceholderEntry],
) -> ReinsertionResult:
    """Substitute exact placeholder tokens with mapped original values."""
    started = time.perf_counter()

    entries_by_key: dict[tuple[str, int], PlaceholderEntry] = {}
    for entry in mapping:
        key = _lookup_key(entry.placeholder)
        if key is not None:
            entries_by_key.setdefault(key, entry)

    found_keys: set[tuple[str, int]] = set()
    found_tokens: set[str] = set()
    unknown: list[str] = []
    unknown_seen: set[str] = set()
    parts: list[str] = []
    cursor = 0
    replaced = 0

    for match in PLACEHOLDER_SCAN_RE.finditer(text):
        entity_type = match.group(1).upper()
        number = int(match.group(2))
        key = (entity_type, number)
        found_keys.add(key)
        found_tokens.add(f"<{entity_type}_{number}>")
        entry = entries_by_key.get(key)
        canonical = f"<{entity_type}_{number}>"
        if entry is None:
            _add_unknown(unknown, unknown_seen, canonical)
            continue
        replaced += 1
        parts.append(text[cursor : match.start()])
        parts.append(entry.original)
        cursor = match.end()
    parts.append(text[cursor:])
    new_text = "".join(parts)

    for candidate in _MALFORMED_TOKEN_RE.findall(text):
        if PLACEHOLDER_SCAN_RE.fullmatch(candidate) is not None:
            continue
        canonical = _canonical(candidate)
        if canonical is None:
            continue
        if candidate in found_tokens:
            continue
        _add_unknown(unknown, unknown_seen, candidate)
    for candidate in _MALFORMED_UNCLOSED_RE.findall(text):
        canonical = _canonical(candidate)
        if canonical is None:
            continue
        if candidate in found_tokens:
            continue
        _add_unknown(unknown, unknown_seen, candidate)

    missing: list[str] = []
    for entry in mapping:
        key = _lookup_key(entry.placeholder)
        if key is None:
            continue
        if key not in found_keys and entry.placeholder not in missing:
            missing.append(entry.placeholder)

    duration_ms = int((time.perf_counter() - started) * 1000)
    return ReinsertionResult(
        text=new_text,
        replaced=replaced,
        missing=missing,
        unknown=unknown,
        duration_ms=duration_ms,
    )
