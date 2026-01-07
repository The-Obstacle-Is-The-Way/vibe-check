"""NA-aware HuggingFace export schemas (SSOT §12.4 / SPEC-16)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from vibe_check.constants import PHQ8_ITEMS

Assertion = Literal["present", "denied", "possible", "not_mentioned"]
Split = Literal["train", "dev", "test"]


class HuggingFaceItemExport(BaseModel):
    """Single PHQ-8 item in HuggingFace export (final label; NA-aware)."""

    model_config = ConfigDict(extra="forbid")

    score: Literal[0, 1, 2, 3] | None = Field(
        description="Severity score; null iff assertion=='not_mentioned'",
    )
    assertion: Assertion
    confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="null iff assertion=='not_mentioned'",
    )
    evidence: list[str] = Field(
        default_factory=list,
        max_length=3,
        description="[] iff assertion=='not_mentioned'; otherwise 1-3 snippets",
    )

    @model_validator(mode="after")
    def _validate_semantics(self) -> HuggingFaceItemExport:
        if self.assertion == "not_mentioned":
            if self.score is not None:
                raise ValueError("not_mentioned requires score=None")
            if self.confidence is not None:
                raise ValueError("not_mentioned requires confidence=None")
            if self.evidence:
                raise ValueError("not_mentioned requires evidence=[]")
            return self

        if self.score is None:
            raise ValueError(f"{self.assertion} requires score != None")
        if self.confidence is None:
            raise ValueError(f"{self.assertion} requires confidence != None")
        if not self.evidence:
            raise ValueError(f"{self.assertion} requires at least one evidence snippet")

        if self.assertion == "denied" and self.score != 0:
            raise ValueError("denied requires score=0")
        if self.assertion == "present" and self.score not in (1, 2, 3):
            raise ValueError("present requires score in {1, 2, 3}")
        if self.assertion == "possible" and self.score != 1:
            raise ValueError("possible requires score=1")
        return self


class HuggingFaceTotalsExport(BaseModel):
    """Totals/provenance section for HuggingFace export (SSOT §12.2/§12.4)."""

    model_config = ConfigDict(extra="forbid")

    discussed_count: int = Field(ge=0, le=8)
    discussed_sum: int = Field(ge=0, le=24)
    coverage: float = Field(ge=0.0, le=1.0)

    prorated_total: float | None = None
    prorated_total_rounded: int | None = Field(default=None, ge=0, le=24)

    imputed_total: int = Field(ge=0, le=24)
    na_count: int = Field(ge=0, le=8)

    is_min_coverage: bool
    is_proration_valid: bool

    @model_validator(mode="after")
    def _validate_consistency(self) -> HuggingFaceTotalsExport:
        if self.na_count != 8 - self.discussed_count:
            raise ValueError("na_count must equal 8 - discussed_count")
        if abs(self.coverage - (self.discussed_count / 8.0)) > 1e-9:
            raise ValueError("coverage must equal discussed_count / 8")
        if self.is_min_coverage != (self.discussed_count >= 4):
            raise ValueError("is_min_coverage inconsistent with discussed_count")
        if self.is_proration_valid != (self.discussed_count >= 7):
            raise ValueError("is_proration_valid inconsistent with discussed_count")

        if not self.is_proration_valid:
            if self.prorated_total is not None or self.prorated_total_rounded is not None:
                raise ValueError("proration fields must be None when is_proration_valid=False")
        else:
            if self.prorated_total is None or self.prorated_total_rounded is None:
                raise ValueError("proration fields must be set when is_proration_valid=True")
        return self


class HuggingFaceMetadataExport(BaseModel):
    """Run metadata (SSOT §12.4)."""

    model_config = ConfigDict(extra="forbid")

    prompt_version: str = Field(min_length=1)
    juror_models: list[str] = Field(min_length=1)
    runs_per_model: int = Field(ge=1)
    arbitration_triggered: bool
    judge_model: str | None = None

    @model_validator(mode="after")
    def _validate_judge_model(self) -> HuggingFaceMetadataExport:
        if not self.arbitration_triggered and self.judge_model is not None:
            raise ValueError("judge_model must be None when arbitration_triggered=False")
        return self


class HuggingFaceDialogueExport(BaseModel):
    """One exported record (1 row in JSONL)."""

    model_config = ConfigDict(extra="forbid")

    dialogue_id: str = Field(min_length=1)
    condition: Literal["mdd", "control"]
    split: Split

    items: dict[str, HuggingFaceItemExport]
    totals: HuggingFaceTotalsExport
    scoring_metadata: HuggingFaceMetadataExport

    @model_validator(mode="after")
    def _validate_item_keys(self) -> HuggingFaceDialogueExport:
        expected = set(PHQ8_ITEMS)
        actual = set(self.items.keys())
        if actual != expected:
            missing = expected - actual
            extra = actual - expected
            raise ValueError(f"items must match PHQ8_ITEMS. Missing={missing}, Extra={extra}")
        return self
