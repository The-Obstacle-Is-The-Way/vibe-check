"""Prompt builders for the Judge agent."""

from __future__ import annotations

from vibe_check.constants import (
    JUDGE_ASSERTION_GUIDANCE_V2,
    JUDGE_JSON_SKELETON_V2,
    JUDGE_NA_HANDLING_V2,
    MAX_EVIDENCE_SNIPPET_CHARS,
    MAX_EVIDENCE_SNIPPET_WORDS,
    MAX_JUDGE_EVIDENCE_SNIPPETS,
    PHQ8_ITEMS,
    PHQ8_RUBRIC,
    PHQ8_SCORE_SCALE,
    PHQ8_TIME_FRAME,
    PHQ8_TIME_FRAME_V2,
)
from vibe_check.schemas.scoring import Assertion  # noqa: TC001

# === V1 Prompt Builders (PRESERVED - DO NOT MODIFY) ===


def build_judge_system_prompt(prompt_version: str) -> str:
    """Build legacy v1 judge system prompt."""
    rubric_items = "\n".join(f'  - {item}: "{PHQ8_RUBRIC[item]}"' for item in PHQ8_ITEMS)
    return f"""You are an expert judge resolving contested PHQ-8 item scores.
Prompt version: {prompt_version}.

PHQ-8 CLINICAL RUBRIC
=====================

Time frame: {PHQ8_TIME_FRAME}

Scoring scale (0-3 based on frequency):
{PHQ8_SCORE_SCALE}

Item definitions:
{rubric_items}

ARBITRATION CRITERIA
====================

When jurors disagree on a score:
1. Review the juror evidence against the EXACT item definition
2. Apply the 0-3 frequency scale strictly (0=Not at all, 3=Nearly every day)
3. If evidence supports multiple interpretations, choose the score best supported by direct CLIENT quotes
4. If evidence is sparse, favor the majority juror vote
5. Higher confidence when multiple jurors cite consistent evidence; lower when evidence is contradictory

Return JSON ONLY. No markdown, no code fences, no prose.
"""


def build_judge_item_prompt(
    *,
    scoring_text: str,
    item: str,
    juror_votes: list[int],
    juror_evidence: list[str],
) -> str:
    """Build legacy v1 judge item prompt."""
    if item not in PHQ8_ITEMS:
        raise ValueError(f"Unknown PHQ-8 item: {item!r}")

    item_definition = PHQ8_RUBRIC[item]
    evidence_block = "\n".join(f"- {e}" for e in juror_evidence[:MAX_JUDGE_EVIDENCE_SNIPPETS])

    return f"""Contested item: {item}
Item definition: "{item_definition}"

Juror votes: {juror_votes}
Juror evidence snippets:
{evidence_block}

Dialogue (view text):
{scoring_text}

Apply the scoring scale strictly: 0=Not at all, 1=Several days, 2=More than half the days, 3=Nearly every day.

Respond with JSON:
{{"item": "{item}", "final_score": 0, "confidence": 0.0, "rationale": "..."}}
"""


# === V2 Prompt Builders (NA-Aware) - SPEC-17 ===


def build_judge_system_prompt_v2(prompt_version: str) -> str:
    """Build NA-aware judge system prompt.

    Uses v2 constants with clinical inference (no frequency anchors).
    """
    rubric_items = "\n".join(f'  - {item}: "{PHQ8_RUBRIC[item]}"' for item in PHQ8_ITEMS)

    return f"""You are an expert judge resolving contested PHQ-8 item scores.
Prompt version: {prompt_version}.

PHQ-8 CLINICAL RUBRIC
=====================

Time frame: {PHQ8_TIME_FRAME_V2}

Scoring: Infer severity (0-3) from clinical context, not literal frequency words.

Item definitions:
{rubric_items}

{JUDGE_ASSERTION_GUIDANCE_V2}

{JUDGE_NA_HANDLING_V2}

ARBITRATION CRITERIA
====================

When jurors disagree on a score:
1. Review ALL juror evidence against the EXACT item definition
2. Determine the appropriate assertion type first
3. If assertion is present/denied/possible: assign severity score
4. If assertion is not_mentioned: set score to null
5. Higher confidence when evidence is consistent; lower when contradictory

EVIDENCE CONSTRAINTS
====================
- Provide up to 3 evidence snippets.
- Each snippet must be <= {MAX_EVIDENCE_SNIPPET_WORDS} words and <= {MAX_EVIDENCE_SNIPPET_CHARS} characters.
- Evidence must quote CLIENT language (not therapist paraphrasing).
- For not_mentioned: evidence must be [] and confidence must be null.

Return JSON ONLY. No markdown, no code fences, no prose.

JSON SKELETON:
{JUDGE_JSON_SKELETON_V2}
"""


def build_judge_item_prompt_v2(
    *,
    scoring_text: str,
    item: str,
    juror_votes: list[int | None],
    juror_assertions: list[Assertion],
    juror_evidence: list[str],
) -> str:
    """Build NA-aware judge item prompt.

    Args:
        scoring_text: The dialogue transcript being scored.
        item: PHQ-8 item name.
        juror_votes: Juror scores (int 0-3 or None).
        juror_assertions: Juror assertion types.
        juror_evidence: Evidence snippets from jurors (may be empty for NA).
    """
    if item not in PHQ8_ITEMS:
        raise ValueError(f"Unknown PHQ-8 item: {item!r}")

    item_definition = PHQ8_RUBRIC[item]

    # Format votes showing NA explicitly
    formatted_votes = [str(v) if v is not None else "not_mentioned" for v in juror_votes]

    # Count NA vs numeric
    na_count = sum(1 for v in juror_votes if v is None)
    numeric_count = len(juror_votes) - na_count
    na_pct = na_count / len(juror_votes) * 100 if juror_votes else 0

    # Evidence block (may be empty if all NA)
    if juror_evidence:
        evidence_block = "\n".join(f"- {e}" for e in juror_evidence[:5])
    else:
        evidence_block = "(No evidence provided - all jurors voted not_mentioned)"

    return f"""Contested item: {item}
Item definition: "{item_definition}"

Juror votes: {formatted_votes}
Juror assertions: {list(juror_assertions)}
Vote breakdown: {numeric_count} numeric, {na_count} not_mentioned ({na_pct:.0f}% NA)

Juror evidence snippets:
{evidence_block}

Dialogue (view text):
{scoring_text}

Based on the transcript and juror evidence:
1. Determine if this symptom was discussed (discussed=true/false)
2. If discussed: assign assertion (present/denied/possible) and score (0-3)
3. If NOT discussed: assertion=not_mentioned, score=null

Respond with JSON only:
{{"item": "{item}", "discussed": true/false, "final_score": 0-3 or null, "assertion": "...", "confidence": 0.0-1.0 or null, "evidence": ["..."], "rationale": "..."}}
"""
