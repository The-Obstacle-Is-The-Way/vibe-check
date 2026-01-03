"""Prompt builders for PHQ-8 juror scoring."""

from __future__ import annotations


def build_juror_system_prompt(
    prompt_version: str,
    view_name: str = "client_qa",
    extra_instructions: str | None = None,
) -> str:
    """Build the system prompt for a single juror PHQ-8 scoring run."""
    base = f"""You are a clinical scoring juror. Score PHQ-8.

Input: a preprocessed dialogue view named `{view_name}` from a synthetic therapy conversation.
Prompt version: {prompt_version}.

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

Items (PHQ-8):
- anhedonia
- depressed_mood
- sleep
- fatigue
- appetite
- guilt
- concentration
- psychomotor
"""
    if extra_instructions:
        return base + "\n" + extra_instructions.strip() + "\n"
    return base
