"""Utilities for extracting token usage from PydanticAI results."""

from __future__ import annotations

from typing import TYPE_CHECKING

from vibe_check.schemas.scoring import TokenUsage

if TYPE_CHECKING:
    from pydantic_ai.usage import RunUsage


def token_usage_from_run_usage(usage: RunUsage | None) -> TokenUsage | None:
    """Convert a PydanticAI RunUsage into our TokenUsage schema."""
    if usage is None:
        return None
    input_tokens = getattr(usage, "input_tokens", None)
    output_tokens = getattr(usage, "output_tokens", None)
    reasoning_tokens = getattr(usage, "reasoning_tokens", None)
    total_tokens = getattr(usage, "total_tokens", None)
    if total_tokens is None and (input_tokens is not None or output_tokens is not None):
        total_tokens = (input_tokens or 0) + (output_tokens or 0)
    return TokenUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        reasoning_tokens=reasoning_tokens,
        total_tokens=total_tokens,
    )
