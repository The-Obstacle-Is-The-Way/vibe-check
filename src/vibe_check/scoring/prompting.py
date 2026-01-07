"""Prompt builders for PHQ-8 juror scoring."""

from __future__ import annotations

from vibe_check.constants import (
    PHQ8_ASSERTION_RULES_V2,
    PHQ8_CONTEXT_RULES_V2,
    PHQ8_EVIDENCE_CONSTRAINTS_V2,
    PHQ8_ITEMS,
    PHQ8_JSON_SKELETON_V2,
    PHQ8_RUBRIC,
    PHQ8_SCORE_SCALE,
    PHQ8_SCORE_SCALE_V2,
    PHQ8_TIME_FRAME,
    PHQ8_TIME_FRAME_V2,
)


def build_juror_system_prompt(
    prompt_version: str,
    view_name: str = "client_qa",
    extra_instructions: str | None = None,
) -> str:
    """Build system prompt for PHQ-8 scoring.

    Args:
        prompt_version: "v1.x.x" for legacy, "v2.x.x" for clinical inference
        view_name: Dialogue view being scored
        extra_instructions: Additional instructions to append (optional)

    Returns:
        Complete system prompt string
    """
    if prompt_version.startswith("v2"):
        return _build_v2_prompt(prompt_version, view_name, extra_instructions)
    else:
        return _build_v1_prompt(prompt_version, view_name, extra_instructions)


def _build_v1_prompt(
    prompt_version: str,
    view_name: str,
    extra_instructions: str | None,
) -> str:
    """Build legacy frequency-based prompt (v1)."""
    rubric_items = "\n".join(
        f"  {i}. {item}: {PHQ8_RUBRIC[item]}" for i, item in enumerate(PHQ8_ITEMS, 1)
    )
    base = f"""You are a clinical scoring juror. Score PHQ-8.

Input: a preprocessed dialogue view named `{view_name}` from a synthetic therapy conversation.
Prompt version: {prompt_version}.

PHQ-8 CLINICAL RUBRIC
=====================

Time frame: {PHQ8_TIME_FRAME}

Scoring scale (0-3 based on frequency):
{PHQ8_SCORE_SCALE}

Item definitions:
{rubric_items}

IMPORTANT: Match evidence to the EXACT item definition above. Do not infer beyond the text.

Rules:
- Use ONLY the provided text. Do not assume facts not stated.
- Score PHQ-8 items only (8 items). Self-harm is a separate boolean tag, not an extra item.
- Therapist lines are context; evidence should quote/paraphrase CLIENT statements.
- If evidence is insufficient for an item, set `insufficient_evidence=true` and still choose the best score (0-3).

For each item, return:
- score: integer 0-3
- confidence: float 0.0-1.0
- evidence: list of up to 3 short snippets (each <= 50 words)
- insufficient_evidence: boolean

Also return:
- mentions_self_harm: boolean (true if the client expresses self-harm/suicidal ideation)
- self_harm_evidence: list of up to 3 short snippets
- total_score: sum of the 8 item scores (0-24)

Return JSON ONLY. No markdown, no code fences, no prose.
"""
    if extra_instructions and extra_instructions.strip():
        return base + "\n" + extra_instructions.strip() + "\n"
    return base


def _build_v2_prompt(
    prompt_version: str,
    view_name: str,
    extra_instructions: str | None,
) -> str:
    """Build clinical inference prompt (v2)."""
    rubric_items = "\n".join(
        f"  {i}. {item}: {PHQ8_RUBRIC[item]}" for i, item in enumerate(PHQ8_ITEMS, 1)
    )

    base = f"""You are a psychiatrist reviewing a therapy transcript to infer PHQ-8 symptom severity.

Input: A preprocessed dialogue view named `{view_name}` from a synthetic therapy conversation.
Prompt version: {prompt_version}.

## PHQ-8 CLINICAL RUBRIC

### Target Timeframe
{PHQ8_TIME_FRAME_V2}

### Item Definitions
{rubric_items}

### Severity Inference (Evidence → Score)
{PHQ8_SCORE_SCALE_V2}

## CONTEXT RULES (ConText-style)
{PHQ8_CONTEXT_RULES_V2}

## ASSERTION SEMANTICS
{PHQ8_ASSERTION_RULES_V2}

## CRITICAL: NOT MENTIONED vs DENIED

**DENIED (score=0, assertion="denied")**:
Patient EXPLICITLY says they DON'T have the symptom.
Example: "My sleep has been fine" → sleep: score=0, assertion="denied"

**NOT MENTIONED (score=null, assertion="not_mentioned")**:
No evidence for the CLIENT in the target timeframe.
Example: Sleep never discussed → sleep: score=null, assertion="not_mentioned"

⚠️ DO NOT score 0 for items that are simply not mentioned. Score 0 means DENIED.

## EVIDENCE REQUIREMENTS
{PHQ8_EVIDENCE_CONSTRAINTS_V2}

## OUTPUT FORMAT

Return JSON matching this exact structure:
```json
{PHQ8_JSON_SKELETON_V2}
```

- `total_score`: Sum of non-null item scores (NA items contribute 0)
- `discussed_count`: Count of items where discussed=true

Return JSON ONLY. No markdown code fences, no explanatory prose.
"""
    if extra_instructions and extra_instructions.strip():
        return base + "\n" + extra_instructions.strip() + "\n"
    return base
