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

# Preprocessing artifact stripping (SPEC-12)
# These are deterministic, corpus-specific cleanup rules intended to remove
# template placeholders and termination markers from SQPsychConv-style dialogues.
STRIP_GENERATION_ARTIFACT_PATTERNS: tuple[str, ...] = (
    # Termination markers
    r"\[\s*/?\s*END\s*\]",
    # Template placeholders / scheduling scaffolding
    r"\[\s*insert[^\]]*\]",
    r"\[\s*next[^\]]*\]",
    r"\[\s*please\s+confirm[^\]]*\]",
    r"\[\s*review[^\]]*\]",
    r"\[\s*turn\s+\d+[^\]]*\]",
    r"\[\s*client\s+agrees[^\]]*\]",
    r"\[\s*if\s+the\s+client\s+agrees[^\]]*\]",
    # Name placeholders (support straight and curly apostrophes)
    r"\[\s*client(?:'|\u2019)?s?\s*name\s*\]",
    r"\[\s*therapist(?:'|\u2019)?s?\s*name\s*\]",
    r"\[\s*colleague(?:'|\u2019)?s?\s*name\s*\]",
    r"\[\s*(?:daughter|sister)(?:'|\u2019)?s?\s*name\s*\]",
    # Export / chunking artifacts (seen in a small number of rows)
    r"\[\s*\d+\s*/\s*\d+\s*\]",
    # Semantic-void roleplay directives
    r"\[\s*keep\s+silent\s*\]",
    r"\[\s*no\s+reply\s*\]",
    r"\[\s*quiet\s*\]",
    r"\[\s*pause[^\]]*\]",
    # Bracketed stage directions / closings (not useful for PHQ-8 evidence)
    r"\[\s*(?:sigh|smiles?|exhales?|inhales?(?:\s+deeply)?|taking\s+a\s+deep\s+breath)[^\]]*\]",
    r"\[\s*repeats\s+a\s+few\s+times[^\]]*\]",
    r"\[\s*(?:see\s+you|take\s+care|thank\s+you)[^\]]*\]",
    r"\[\s*i(?:'|\u2019)?ll\s+send[^\]]*\]",
)

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

# Coverage quality gates (SPEC-18)
MIN_ITEM_COVERAGE: float = 0.50
MAX_CORPUS_NA_RATE: float = 0.25
MIN_DIALOGUE_MIN_COVERAGE_RATE: float = 0.90

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

# === V2 CONSTANTS (CLINICAL INFERENCE) - SPEC-14 ===
PHQ8_TIME_FRAME_V2: str = "Recent period (~last 2 weeks), unless transcript indicates otherwise"

PHQ8_SCORE_SCALE_V2: str = """| Evidence Pattern | Score | Cues |
|-----------------|-------|------|
| Mild / intermittent, minimal impact | 1 | "sometimes", "a bit", "here and there" |
| Frequent/persistent OR moderate impact | 2 | "often", "most days", "regularly", clear disruption |
| Near-daily/persistent AND severe impact | 3 | "every day", "nearly every day", "can't function" |
| Explicit denial of symptom | 0 | "I'm sleeping fine", "my appetite is good" |
| No evidence for CLIENT+timeframe | null | not discussed / not scorable |"""

PHQ8_ASSERTION_RULES_V2: str = """- present (score 1-3): Symptom clearly described by CLIENT for current/recent timeframe
- denied (score 0): CLIENT explicitly denies symptom
- possible (score 1): Hedged/uncertain mention by CLIENT ("maybe", "I guess")
- not_mentioned (score null): No evidence for CLIENT in target timeframe"""

PHQ8_CONTEXT_RULES_V2: str = """- Experiencer: Score ONLY symptoms attributed to the CLIENT (not family/others)
- Temporality: Score current/recent symptoms ONLY (not historical/resolved)
- Hypothetical: Exclude "what if" / conditional / future statements
- Negation: Explicit denial → score=0, assertion="denied" """

PHQ8_EVIDENCE_CONSTRAINTS_V2: str = """Evidence requirements:
- Maximum 3 snippets per item
- Each snippet: ≤50 words, ≤400 characters
- Quote CLIENT language, not therapist paraphrasing
- For not_mentioned: evidence=[], confidence=null"""

PHQ8_JSON_SKELETON_V2: str = """{
  "anhedonia": {"discussed": true, "score": 2, "assertion": "present", "confidence": 0.85, "evidence": ["quote"]},
  "depressed_mood": {"discussed": true, "score": 0, "assertion": "denied", "confidence": 0.90, "evidence": ["I feel fine"]},
  "sleep": {"discussed": false, "score": null, "assertion": "not_mentioned", "confidence": null, "evidence": []},
  "fatigue": {"discussed": true, "score": 1, "assertion": "possible", "confidence": 0.55, "evidence": ["maybe tired"]},
  "appetite": {"discussed": false, "score": null, "assertion": "not_mentioned", "confidence": null, "evidence": []},
  "guilt": {"discussed": true, "score": 1, "assertion": "present", "confidence": 0.70, "evidence": ["quote"]},
  "concentration": {"discussed": false, "score": null, "assertion": "not_mentioned", "confidence": null, "evidence": []},
  "psychomotor": {"discussed": false, "score": null, "assertion": "not_mentioned", "confidence": null, "evidence": []},
  "total_score": 4,
  "discussed_count": 4,
  "mentions_self_harm": false,
  "self_harm_evidence": []
}"""

# === JUDGE V2 CONSTANTS (SPEC-17) ===
JUDGE_ASSERTION_GUIDANCE_V2: str = """
ASSERTION TYPES
===============

When resolving contested items, you must determine the appropriate assertion:

- **present**: Client clearly indicates experiencing the symptom with severity > 0
  → Score must be 1, 2, or 3

- **denied**: Client explicitly denies or negates the symptom
  → Score must be 0

- **possible**: Symptom domain is clearly referenced, but severity/intensity is hedged/uncertain
  → Default to score=1 (low severity)

- **not_mentioned**: Symptom was never discussed in the transcript
  → Score must be null (no score assigned)
  → ONLY use if the symptom domain is not referenced at all for the CLIENT+timeframe
"""

JUDGE_NA_HANDLING_V2: str = """
HANDLING NA VOTES
=================

When jurors have voted "not_mentioned" (None) for some votes:

1. If ALL jurors voted not_mentioned → confirm not_mentioned
2. If MAJORITY (> 50%) voted not_mentioned but some provided numeric scores:
   - Review the evidence from numeric jurors carefully
   - If evidence is compelling and clearly references the symptom → override to numeric
   - If evidence is weak or tangential → confirm not_mentioned
3. If MINORITY (≤ 50%) voted not_mentioned:
   - Default to numeric resolution using evidence from other jurors
   - Only confirm not_mentioned if numeric evidence is clearly mistaken

CRITICAL: "Not mentioned" means the symptom was NEVER discussed. If there's ANY
evidence of the symptom being mentioned (even to deny it), it was discussed.
"""

JUDGE_JSON_SKELETON_V2: str = """{
  "item": "anhedonia",
  "discussed": true,
  "final_score": 2,
  "assertion": "present",
  "confidence": 0.85,
  "evidence": ["Client: I can't enjoy anything anymore."],
  "rationale": "Client explicitly describes loss of interest and impairment."
}"""


def phq8_rubric_hash() -> str:
    """Return a stable hash of the PHQ-8 rubric constants for audit."""
    payload = {
        "time_frame": PHQ8_TIME_FRAME,
        "score_scale": PHQ8_SCORE_SCALE,
        "items": PHQ8_RUBRIC,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
