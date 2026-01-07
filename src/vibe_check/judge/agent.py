"""PydanticAI agent for the Judge (Arbitrator)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic_ai import Agent

from vibe_check.judge.prompting import build_judge_system_prompt, build_judge_system_prompt_v2
from vibe_check.judge.schema import JudgeItemResolution, JudgeItemResolutionNA

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


def build_judge_agent_v2(
    *,
    model: Model | KnownModelName | str | None,
    prompt_version: str,
    model_settings: ModelSettings | None = None,
    retries: int = 2,
) -> Agent[None, JudgeItemResolutionNA]:
    """Build a PydanticAI agent for NA-aware judge arbitration (SPEC-17).

    Args:
        model: The LLM model to use (e.g., "anthropic:claude-opus-4-5").
        prompt_version: Version string for prompt tracking (must be v2.*).
        model_settings: Optional model settings for temperature, top_p, etc.
        retries: Number of retries for validation failures (default: 2, per ADR-001).

    Returns:
        Agent configured with JudgeItemResolutionNA for NA-aware resolution.

    Notes:
        The `retries` parameter handles Layer 1 (validation retries) of ADR-001's
        three-layer resilience strategy. This agent supports not_mentioned assertions
        with null scores per SPEC-13 assertion/score invariants.
    """
    return Agent(
        model=model,
        output_type=JudgeItemResolutionNA,
        retries=retries,
        model_settings=model_settings,
        system_prompt=build_judge_system_prompt_v2(prompt_version),
    )
