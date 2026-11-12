"""Consistent typed placeholder masking (lane 1).

See CONTRACT.md §2 and §3 for the invariants.
"""

from __future__ import annotations

from app.contracts import DetectedEntity, MaskingResult


def mask(text: str, entities: list[DetectedEntity]) -> MaskingResult:
    raise NotImplementedError(
        "Lane 1: implement placeholder masking using privacy.vault.PlaceholderVault."
    )
