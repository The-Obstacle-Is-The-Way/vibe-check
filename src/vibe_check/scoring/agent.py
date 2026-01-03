"""PydanticAI agent builders for juror scoring."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic_ai import Agent

from vibe_check.scoring.prompting import build_juror_system_prompt

if TYPE_CHECKING:
    from pydantic_ai.models import KnownModelName, Model


def build_juror_agent(
    *,
    model: Model | KnownModelName | str | None,
    prompt_version: str,
    view_name: str = "client_qa",
    instructions: str | None = None,
) -> Agent[None, dict[str, Any]]:
    """Build a PydanticAI agent configured for PHQ-8 juror scoring.

    Notes:
    - `model` may be a provider model name (e.g., "openai:gpt-5.2") or a PydanticAI model
      instance (e.g., `TestModel`) depending on the PydanticAI adapter in use.
    - The agent output type is `dict` so we can canonicalize totals and enforce bounds
      before constructing `PHQ8Report`.
    """

    return Agent(
        model=model,
        output_type=dict[str, Any],
        system_prompt=build_juror_system_prompt(
            prompt_version=prompt_version,
            view_name=view_name,
            extra_instructions=instructions,
        ),
    )
