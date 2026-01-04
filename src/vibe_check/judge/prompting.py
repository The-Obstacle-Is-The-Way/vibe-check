"""Prompt builders for the Judge agent."""

from __future__ import annotations

from vibe_check.constants import (
    MAX_JUDGE_EVIDENCE_SNIPPETS,
    PHQ8_ITEMS,
    PHQ8_RUBRIC,
    PHQ8_SCORE_SCALE,
    PHQ8_TIME_FRAME,
)


def build_judge_system_prompt(prompt_version: str) -> str:
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
