"""Exact-token local reinsertion (lane 1).

See CONTRACT.md §3: no fuzzy matching, no repairs, no cross-entity guessing.
"""

from __future__ import annotations

from app.contracts import PlaceholderEntry, ReinsertionResult


def reinsert(
    text: str,
    mapping: list[PlaceholderEntry],
) -> ReinsertionResult:
    raise NotImplementedError(
        "Lane 1: implement exact-token reinsertion, reporting missing/unknown tokens."
    )
