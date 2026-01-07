"""Schemas for aggregated outputs."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from vibe_check.constants import SEVERITY_BUCKETS, SeverityBucket
from vibe_check.schemas.scoring import Assertion, PHQ8Report, PHQ8TotalScore, TokenUsage


class ItemAggregationNA(BaseModel):
    """Aggregated statistics for one PHQ-8 item with NA handling (SPEC-15)."""

    model_config = ConfigDict(extra="forbid")

    # Raw votes (including None for not_mentioned)
    votes: list[int | None]
    assertions: list[Assertion]

    # Numeric vote stats (excluding NA)
    numeric_votes: list[int]
    vote_counts: dict[str, int]  # "0","1","2","3"
    posterior: dict[str, float] | None  # None if all votes are NA

    # Aggregated stats (from numeric votes only)
    mode: int | None = Field(default=None, ge=0, le=3)
    expected: float | None = Field(default=None, ge=0.0, le=3.0)
    entropy: float | None = Field(default=None, ge=0.0)
    vote_range: int | None = Field(default=None, ge=0, le=3)
    clinical_prob: float | None = Field(default=None, ge=0.0, le=1.0, description="P(score >= 2)")

    # NA tracking
    na_count: int = Field(ge=0)
    p_not_mentioned: float = Field(ge=0.0, le=1.0)

    # Consensus
    consensus_score: int | None = Field(default=None, ge=0, le=3)
    consensus_assertion: Assertion

    needs_arbitration: bool = False
    arbitration_reason: str | None = None


class AggregatedPHQ8(BaseModel):
    """Final aggregated output for one dialogue (NA-aware; SPEC-15)."""

    model_config = ConfigDict(extra="forbid")

    file_id: str
    condition: Literal["mdd", "control"]

    items: dict[str, ItemAggregationNA]

    # Totals/provenance (SSOT §12.2)
    totals: PHQ8TotalScore

    total_mode: int = Field(ge=0, le=24)
    total_expected: float = Field(ge=0.0, le=24.0)
    total_std: float = Field(ge=0.0)
    total_posterior: dict[int, float]
    total_ci_90: tuple[int, int]

    severity_bucket: SeverityBucket
    severity_bucket_phq_like: SeverityBucket | None = None
    severity_bucket_probs: dict[str, float]

    final_item_scores: dict[str, int]
    final_total_score: int = Field(ge=0, le=24)
    final_severity_bucket: SeverityBucket
    final_source: Literal["jury_mode", "jury_expected", "judge_override"]

    triggered_arbitration: bool = False
    arbitration_items: list[str] = Field(default_factory=list)
    arbitration_reasons: dict[str, str] = Field(default_factory=dict)

    mentions_self_harm: bool = False
    self_harm_evidence: list[str] = Field(default_factory=list)

    juror_reports: list[PHQ8Report]
    judge_resolution: dict[str, Any] | None = None
    judge_usage: TokenUsage | None = None

    prompt_version: str
    scored_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def _validate_juror_reports(self) -> AggregatedPHQ8:
        if any(not isinstance(r, PHQ8Report) for r in self.juror_reports):
            raise TypeError("juror_reports must be PHQ8Report instances")
        expected_total = sum(self.final_item_scores.values())
        if self.final_total_score != expected_total:
            raise ValueError(
                f"final_total_score={self.final_total_score} does not match "
                f"sum(final_item_scores)={expected_total}"
            )
        if self.totals.imputed_total != self.final_total_score:
            raise ValueError(
                f"totals.imputed_total={self.totals.imputed_total} does not match "
                f"final_total_score={self.final_total_score}"
            )
        bucket = None
        for name, (lo, hi) in SEVERITY_BUCKETS.items():
            if lo <= self.final_total_score <= hi:
                bucket = name
                break
        if bucket is None or bucket != self.final_severity_bucket:
            raise ValueError("final_severity_bucket must match final_total_score bucket")
        return self
