"""Schemas for judge arbitration outputs."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class JudgeItemResolution(BaseModel):
    """Judge decision for a single contested PHQ-8 item."""

    model_config = ConfigDict(extra="forbid")

    item: str = Field(min_length=1)
    final_score: Literal[0, 1, 2, 3]
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str = Field(min_length=1)
