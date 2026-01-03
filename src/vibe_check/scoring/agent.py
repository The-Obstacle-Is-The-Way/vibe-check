"""PydanticAI agent builders for juror scoring."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic_ai import Agent

from vibe_check.schemas.scoring import PHQ8Assessment
from vibe_check.scoring.prompting import build_juror_system_prompt

if TYPE_CHECKING:
    from pydantic_ai.models import KnownModelName, Model


def build_juror_agent(
    *,
    model: Model | KnownModelName | str | None,
    prompt_version: str,
    view_name: str = "client_qa",
    instructions: str | None = None,
) -> Agent[None, PHQ8Assessment]:
    """Build a PydanticAI agent configured for PHQ-8 juror scoring.

    Notes:
    - We use `output_type=PHQ8Assessment` to leverage PydanticAI's built-in schema validation
      and retry logic (fixing BUG-006/009). The `JurorScorer` then upgrades this to `PHQ8Report`.
    """

    return Agent(
        model=model,
        output_type=PHQ8Assessment,
        system_prompt=build_juror_system_prompt(
            prompt_version=prompt_version,
            view_name=view_name,
            extra_instructions=instructions,
        ),
    )
