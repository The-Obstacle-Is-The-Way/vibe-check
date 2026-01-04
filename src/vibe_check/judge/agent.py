"""PydanticAI agent for the Judge (Arbitrator)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic_ai import Agent

from vibe_check.judge.prompting import build_judge_system_prompt
from vibe_check.judge.schema import JudgeItemResolution

if TYPE_CHECKING:
    from pydantic_ai.models import KnownModelName, Model
    from pydantic_ai.settings import ModelSettings


def build_judge_agent(
    *,
    model: Model | KnownModelName | str | None,
    prompt_version: str,
    model_settings: ModelSettings | None = None,
    retries: int = 2,
) -> Agent[None, JudgeItemResolution]:
    """Build a PydanticAI agent for resolving contested items.

    Args:
        model: The LLM model to use (e.g., "anthropic:claude-opus-4-5").
        prompt_version: Version string for prompt tracking.
        retries: Number of retries for validation failures (default: 2, per ADR-001).

    Notes:
        The `retries` parameter handles Layer 1 (validation retries) of ADR-001's
        three-layer resilience strategy.
    """
    return Agent(
        model=model,
        output_type=JudgeItemResolution,
        retries=retries,
        model_settings=model_settings,
        system_prompt=build_judge_system_prompt(prompt_version),
    )
