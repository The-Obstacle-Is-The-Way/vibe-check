"""Prompt builders for the Judge agent."""

from __future__ import annotations

from vibe_check.constants import MAX_JUDGE_EVIDENCE_SNIPPETS, PHQ8_ITEMS


def build_judge_system_prompt(prompt_version: str) -> str:
    return f"""You are an expert judge resolving contested PHQ-8 item scores.
Prompt version: {prompt_version}.

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

    evidence_block = "\n".join(f"- {e}" for e in juror_evidence[:MAX_JUDGE_EVIDENCE_SNIPPETS])

    return f"""Contested item: {item}

Juror votes: {juror_votes}
Juror evidence snippets:
{evidence_block}

Dialogue (view text):
{scoring_text}

Respond with JSON:
{{"item": "{item}", "final_score": 0, "confidence": 0.0, "rationale": "..."}}
"""
