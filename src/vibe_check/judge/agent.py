"""PydanticAI agent builders for judge arbitration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic_ai import Agent

from vibe_check.judge.prompting import build_judge_system_prompt
from vibe_check.judge.schema import JudgeItemResolution

if TYPE_CHECKING:
    from pydantic_ai.models import KnownModelName, Model


def build_judge_agent(
    *,
    model: Model | KnownModelName | str | None,
    prompt_version: str,
) -> Agent[None, JudgeItemResolution]:
    """Build a PydanticAI agent configured for judge arbitration.

    Unlike juror agents, the judge uses strict Pydantic validation because:
    - Judge outputs are simpler (one item, not 8)
    - We want PydanticAI retries for malformed responses
    - Arbitration is rare, so we can afford retries
    """
    return Agent(
        model=model,
        output_type=JudgeItemResolution,
        system_prompt=build_judge_system_prompt(prompt_version=prompt_version),
    )
