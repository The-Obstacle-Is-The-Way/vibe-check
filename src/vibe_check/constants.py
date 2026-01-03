"""Shared constants for vibe-check."""

from __future__ import annotations

from typing import Literal

PHQ8_ITEMS: tuple[str, ...] = (
    "anhedonia",
    "depressed_mood",
    "sleep",
    "fatigue",
    "appetite",
    "guilt",
    "concentration",
    "psychomotor",
)

SeverityBucket = Literal["0-4", "5-9", "10-14", "15-19", "20-24"]

SEVERITY_BUCKETS: dict[SeverityBucket, tuple[int, int]] = {
    "0-4": (0, 4),
    "5-9": (5, 9),
    "10-14": (10, 14),
    "15-19": (15, 19),
    "20-24": (20, 24),
}

# Operational Hygiene / Cost Control
MAX_EVIDENCE_SNIPPET_WORDS = 50
MAX_EVIDENCE_SNIPPET_CHARS = 400
MAX_JUDGE_EVIDENCE_SNIPPETS = 10
