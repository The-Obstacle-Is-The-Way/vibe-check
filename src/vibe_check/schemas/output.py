"""Schemas for aggregated outputs."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from vibe_check.schemas.scoring import PHQ8Report


class ItemAggregation(BaseModel):
    """Aggregated statistics for one PHQ-8 item."""

    model_config = ConfigDict(extra="forbid")

    votes: list[int]
    vote_counts: dict[str, int]
    posterior: dict[str, float]

    mode: int = Field(ge=0, le=3)
    expected: float = Field(ge=0.0, le=3.0)
    entropy: float = Field(ge=0.0)
    vote_range: int = Field(ge=0, le=3)
    clinical_prob: float = Field(ge=0.0, le=1.0, description="P(score >= 2)")

    needs_arbitration: bool = False
    arbitration_reason: str | None = None


class AggregatedPHQ8(BaseModel):
    """Final aggregated output for one dialogue."""

    model_config = ConfigDict(extra="forbid")

    file_id: str
    condition: Literal["mdd", "control"]

    items: dict[str, ItemAggregation]

    total_mode: int = Field(ge=0, le=24)
    total_expected: float = Field(ge=0.0, le=24.0)
    total_std: float = Field(ge=0.0)
    total_posterior: dict[int, float]
    total_ci_90: tuple[int, int]

    severity_bucket: Literal["0-4", "5-9", "10-14", "15-19", "20-24"]
    severity_bucket_probs: dict[str, float]

    triggered_arbitration: bool = False
    arbitration_items: list[str] = Field(default_factory=list)
    arbitration_reasons: dict[str, str] = Field(default_factory=dict)

    mentions_self_harm: bool = False
    self_harm_evidence: list[str] = Field(default_factory=list)

    juror_reports: list[PHQ8Report]
    judge_resolution: dict[str, Any] | None = None

    prompt_version: str
    scored_at: datetime = Field(default_factory=datetime.utcnow)

    @model_validator(mode="after")
    def _validate_juror_reports(self) -> AggregatedPHQ8:
        if any(not isinstance(r, PHQ8Report) for r in self.juror_reports):
            raise TypeError("juror_reports must be PHQ8Report instances")
        return self
