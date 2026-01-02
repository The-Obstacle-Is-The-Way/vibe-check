"""Schemas for individual juror outputs (per-model PHQ-8 scoring)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PHQ8ItemScore(BaseModel):
    """Single PHQ-8 item score from one model run."""

    model_config = ConfigDict(extra="forbid")

    score: Literal[0, 1, 2, 3] = Field(
        description="0=Not at all, 1=Several days, 2=More than half, 3=Nearly every day",
    )
    confidence: float = Field(ge=0.0, le=1.0, description="Model's self-reported confidence")
    evidence: list[str] = Field(default_factory=list, max_length=3)
    insufficient_evidence: bool = Field(default=False)


class PHQ8Report(BaseModel):
    """Complete PHQ-8 assessment from one model run."""

    model_config = ConfigDict(extra="forbid")

    model_id: str = Field(min_length=1, description="e.g., 'gpt-5.2'")
    run_number: int = Field(ge=1, le=2, description="Run 1 or 2")

    anhedonia: PHQ8ItemScore
    depressed_mood: PHQ8ItemScore
    sleep: PHQ8ItemScore
    fatigue: PHQ8ItemScore
    appetite: PHQ8ItemScore
    guilt: PHQ8ItemScore
    concentration: PHQ8ItemScore
    psychomotor: PHQ8ItemScore

    total_score: int = Field(ge=0, le=24)

    mentions_self_harm: bool = False
    self_harm_evidence: list[str] = Field(default_factory=list)

    scored_at: datetime = Field(default_factory=datetime.utcnow)

    @property
    def item_scores(self) -> dict[str, int]:
        return {
            "anhedonia": int(self.anhedonia.score),
            "depressed_mood": int(self.depressed_mood.score),
            "sleep": int(self.sleep.score),
            "fatigue": int(self.fatigue.score),
            "appetite": int(self.appetite.score),
            "guilt": int(self.guilt.score),
            "concentration": int(self.concentration.score),
            "psychomotor": int(self.psychomotor.score),
        }

    @model_validator(mode="after")
    def _check_total_score(self) -> PHQ8Report:
        expected = sum(self.item_scores.values())
        if self.total_score != expected:
            raise ValueError(f"total_score={self.total_score} does not match item sum={expected}")
        return self
