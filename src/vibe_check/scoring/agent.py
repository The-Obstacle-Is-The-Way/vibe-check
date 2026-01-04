"""PydanticAI agent builders for juror scoring."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic_ai import Agent

from vibe_check.schemas.scoring import PHQ8Assessment
from vibe_check.scoring.prompting import build_juror_system_prompt

if TYPE_CHECKING:
    from pydantic_ai.models import KnownModelName, Model
    from pydantic_ai.settings import ModelSettings


def build_juror_agent(
    *,
    model: Model | KnownModelName | str | None,
    prompt_version: str,
    view_name: str = "client_qa",
    instructions: str | None = None,
    model_settings: ModelSettings | None = None,
    retries: int = 2,
) -> Agent[None, PHQ8Assessment]:
    """Build a PydanticAI agent configured for PHQ-8 juror scoring.

    Args:
        model: The LLM model to use (e.g., "openai:gpt-5.2").
        prompt_version: Version string for prompt tracking.
        view_name: Dialogue view used for scoring context.
        instructions: Additional instructions to append to the system prompt.
        retries: Number of retries for validation failures (default: 2, per ADR-001).

    Notes:
    - We use `output_type=PHQ8Assessment` to leverage PydanticAI's built-in schema validation
      and retry logic (fixing BUG-006/009). The `JurorScorer` then upgrades this to `PHQ8Report`.
    - The `retries` parameter handles Layer 1 (validation retries) of ADR-001's
      three-layer resilience strategy.
    """

    return Agent(
        model=model,
        output_type=PHQ8Assessment,
        retries=retries,
        model_settings=model_settings,
        system_prompt=build_juror_system_prompt(
            prompt_version=prompt_version,
            view_name=view_name,
            extra_instructions=instructions,
        ),
    )
