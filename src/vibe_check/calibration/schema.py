"""Schemas for human calibration reports (SPEC-09)."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field


class ClassMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    precision: float
    recall: float
    f1: float
    support: int = Field(ge=0)


class AgreementMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cohens_kappa: float
    quadratic_weighted_kappa: float
    accuracy: float
    confusion_matrix: list[list[int]]


class CalibrationReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Meta
    system_version: str
    computed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    human_annotator_ids: list[str]
    sample_size: int = Field(ge=0)
    sampling_strategy: str

    # Performance
    overall_agreement: AgreementMetrics
    per_severity_class: dict[str, ClassMetrics]

    # Safety
    self_harm_recall: float

    # Drift
    system_bias: float
