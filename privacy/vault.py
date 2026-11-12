"""In-memory placeholder vault.

This is the *only* place original values are held. It is request-scoped:
create one, use it, drop it. Never serialise it, never log it, never store it.

Lane 1 may extend this module, but must preserve the semantics in CONTRACT.md §2.
"""

from __future__ import annotations

import re
from collections import defaultdict

from app.contracts import EntityType, PlaceholderEntry, make_placeholder

_AADHAAR_SEPARATORS = re.compile(r"[\s-]+")
_UPPERCASE_TYPES = {
    EntityType.PAN,
    EntityType.GSTIN,
    EntityType.VOTER_ID,
    EntityType.PASSPORT,
}


def normalize_value(entity_type: EntityType, value: str) -> str:
    """Normalise a raw value so equivalent spellings share a placeholder."""
    collapsed = " ".join(value.split())
    if entity_type is EntityType.AADHAAR:
        return _AADHAAR_SEPARATORS.sub("", collapsed)
    if entity_type in _UPPERCASE_TYPES:
        return collapsed.upper()
    return collapsed.casefold()


class PlaceholderVault:
    """Deterministic, per-request mapping from values to typed placeholders."""

    def __init__(self) -> None:
        self._entries: list[PlaceholderEntry] = []
        self._by_key: dict[tuple[EntityType, str], PlaceholderEntry] = {}
        self._by_placeholder: dict[str, PlaceholderEntry] = {}
        self._counters: dict[EntityType, int] = defaultdict(int)

    def add(self, entity_type: EntityType | str, original: str) -> str:
        entity_type = EntityType(entity_type)
        key = (entity_type, normalize_value(entity_type, original))

        existing = self._by_key.get(key)
        if existing is not None:
            existing.occurrences += 1
            return existing.placeholder

        self._counters[entity_type] += 1
        placeholder = make_placeholder(entity_type, self._counters[entity_type])
        entry = PlaceholderEntry(
            placeholder=placeholder,
            type=entity_type,
            original=original,
        )
        self._entries.append(entry)
        self._by_key[key] = entry
        self._by_placeholder[placeholder.casefold()] = entry
        return placeholder

    def resolve(self, placeholder: str) -> str | None:
        entry = self._by_placeholder.get(placeholder.casefold())
        return None if entry is None else entry.original

    @property
    def entries(self) -> list[PlaceholderEntry]:
        return list(self._entries)

    def clear(self) -> None:
        self._entries.clear()
        self._by_key.clear()
        self._by_placeholder.clear()
        self._counters.clear()

    def __len__(self) -> int:
        return len(self._entries)
