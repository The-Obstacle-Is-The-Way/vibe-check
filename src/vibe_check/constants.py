"""Shared constants for vibe-check."""

from __future__ import annotations

import hashlib
import json
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

# Preprocessing caps (defensive against pathological utterances).
MAX_UTTERANCE_WORDS = 200
MAX_UTTERANCE_CHARS = 4000

# Preprocessing parsing hygiene
MAX_SPEAKER_PREFIX_CHARS = 32
MAX_BRACKET_CHARS = 200

# Operational defaults
SQLITE_TIMEOUT = 30.0
DEFAULT_RPM_FALLBACK = 60
MAX_ERROR_MESSAGE_CHARS = 500

# Diagnostic quality gates (SPEC-07)
KRIPPENDORFF_ALPHA_MIN = 0.67
CRONBACH_ALPHA_MIN = 0.70
ARBITRATION_RATE_MAX = 0.30
COHENS_D_MIN = 0.5
P_VALUE_MAX = 0.01

# PHQ-8 Clinical Rubric (for prompt embedding; see SPEC-11)
PHQ8_TIME_FRAME: str = "Over the last 2 weeks"

PHQ8_SCORE_SCALE: str = (
    "0 = Not at all\n1 = Several days\n2 = More than half the days\n3 = Nearly every day"
)

PHQ8_RUBRIC: dict[str, str] = {
    "anhedonia": "Little interest or pleasure in doing things",
    "depressed_mood": "Feeling down, depressed, or hopeless",
    "sleep": "Trouble falling or staying asleep, or sleeping too much",
    "fatigue": "Feeling tired or having little energy",
    "appetite": "Poor appetite or overeating",
    "guilt": (
        "Feeling bad about yourself—or that you are a failure or have let yourself or your family down"
    ),
    "concentration": (
        "Trouble concentrating on things, such as reading the newspaper or watching television"
    ),
    "psychomotor": (
        "Moving or speaking so slowly that other people could have noticed—or the opposite, being so "
        "fidgety or restless that you have been moving around a lot more than usual"
    ),
}


def phq8_rubric_hash() -> str:
    """Return a stable hash of the PHQ-8 rubric constants for audit."""
    payload = {
        "time_frame": PHQ8_TIME_FRAME,
        "score_scale": PHQ8_SCORE_SCALE,
        "items": PHQ8_RUBRIC,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
