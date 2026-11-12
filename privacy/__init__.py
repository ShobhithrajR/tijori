"""Tijori privacy core (lane 1): detection, masking, vault, reinsertion."""

import os

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

from privacy.detection import DetectionError, detect, resolve_overlaps
from privacy.masking import mask
from privacy.reinsertion import reinsert
from privacy.vault import PlaceholderVault

__all__ = [
    "DetectionError",
    "detect",
    "mask",
    "reinsert",
    "resolve_overlaps",
    "PlaceholderVault",
]
