"""Schemas for judge arbitration outputs."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from vibe_check.constants import PHQ8_ITEMS
from vibe_check.schemas.scoring import TokenUsage  # noqa: TC001


class JudgeItemResolution(BaseModel):
    """Judge decision for a single contested PHQ-8 item."""

    model_config = ConfigDict(extra="forbid")

    item: str = Field(min_length=1)
    final_score: Literal[0, 1, 2, 3]
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str = Field(min_length=1)

    @field_validator("item")
    @classmethod
    def _validate_item_name(cls, v: str) -> str:
        if v not in PHQ8_ITEMS:
            raise ValueError(f"item must be one of {PHQ8_ITEMS}, got {v!r}")
        return v


class JudgeItemReport(JudgeItemResolution):
    """Judge decision plus token usage metadata."""

    usage: TokenUsage | None = None
