"""Shared fixtures for the lane 1 privacy core tests."""

from __future__ import annotations

import pytest

from app.contracts import EntityType
from privacy.detection import detect
from privacy.detection.india import recognize

PS02_SAMPLE = (
    "My name is Rahul Sharma. My Aadhaar number is 1234-5678-9012 "
    "and my PAN is ABCDE1234F."
)


@pytest.fixture
def sample_text() -> str:
    return PS02_SAMPLE


@pytest.fixture
def detection():
    return detect(PS02_SAMPLE)


@pytest.fixture
def mapping():
    from privacy.vault import PlaceholderVault

    vault = PlaceholderVault()
    vault.add(EntityType.PERSON, "Rahul Sharma")
    vault.add(EntityType.AADHAAR, "1234-5678-9012")
    vault.add(EntityType.PAN, "ABCDE1234F")
    return vault.entries
