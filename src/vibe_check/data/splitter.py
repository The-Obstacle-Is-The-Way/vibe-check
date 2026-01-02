"""Deterministic dataset splitting."""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vibe_check.schemas.input import SplitName


def compute_split(file_id: str) -> SplitName:
    """Deterministic split based on file_id hash."""
    if not file_id:
        raise ValueError("file_id must be non-empty")

    hash_val = int(hashlib.sha256(file_id.encode()).hexdigest(), 16)
    bucket = hash_val % 10
    if bucket < 8:
        return "train"
    if bucket == 8:
        return "dev"
    return "test"
