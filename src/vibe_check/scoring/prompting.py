"""Prompt builders for PHQ-8 juror scoring."""

from __future__ import annotations

from vibe_check.constants import PHQ8_ITEMS, PHQ8_RUBRIC, PHQ8_SCORE_SCALE, PHQ8_TIME_FRAME


def build_juror_system_prompt(
    prompt_version: str,
    view_name: str = "client_qa",
    extra_instructions: str | None = None,
) -> str:
    """Build the system prompt for a single juror PHQ-8 scoring run."""
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
    if extra_instructions:
        return base + "\n" + extra_instructions.strip() + "\n"
    return base
