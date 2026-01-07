"""Schemas for judge arbitration outputs."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from vibe_check.constants import PHQ8_ITEMS
from vibe_check.schemas.scoring import Assertion, TokenUsage  # noqa: TC001

# === V1 Schema (PRESERVED - DO NOT MODIFY) ===


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


# === V2 Schema (NA-Aware) - SPEC-17 ===


class JudgeItemResolutionNA(BaseModel):
    """NA-aware judge decision for a single contested PHQ-8 item.

    Follows SPEC-13 assertion/score invariants.
    """

    model_config = ConfigDict(extra="forbid")

    item: str = Field(min_length=1, description="PHQ-8 item name")
    discussed: bool = Field(description="Whether symptom was discussed in transcript")
    final_score: Literal[0, 1, 2, 3] | None = Field(
        description="Severity score (None if not_mentioned)"
    )
    assertion: Assertion = Field(description="Clinical assertion type")
    confidence: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Confidence (None if not_mentioned)"
    )
    evidence: list[str] = Field(
        default_factory=list,
        max_length=3,
        description="Up to 3 supporting quotes (empty for not_mentioned)",
    )
    rationale: str = Field(min_length=1, description="Reasoning for decision")

    @field_validator("discussed", mode="before")
    @classmethod
    def _validate_discussed_type(cls, value: Any) -> Any:
        if not isinstance(value, bool):
            raise ValueError("discussed must be a boolean (true/false), not a string or number")
        return value

    @field_validator("final_score", mode="before")
    @classmethod
    def _reject_boolean_final_score(cls, value: Any) -> Any:
        if isinstance(value, bool):
            raise ValueError("final_score must be an integer 0-3 or null (not boolean)")
        return value

    @field_validator("confidence", mode="before")
    @classmethod
    def _reject_boolean_confidence(cls, value: Any) -> Any:
        if isinstance(value, bool):
            raise ValueError("confidence must be a number 0.0-1.0 (not boolean)")
        return value

    @model_validator(mode="after")
    def _validate_item_name(self) -> JudgeItemResolutionNA:
        """Validate item is a valid PHQ-8 item."""
        if self.item not in PHQ8_ITEMS:
            raise ValueError(f"item must be one of {PHQ8_ITEMS}, got {self.item!r}")
        return self

    @model_validator(mode="after")
    def _validate_assertion_consistency(self) -> JudgeItemResolutionNA:
        """Enforce SPEC-13 assertion/score/discussed invariants."""
        if self.assertion == "not_mentioned":
            if self.discussed is not False:
                raise ValueError("not_mentioned requires discussed=False")
            if self.final_score is not None:
                raise ValueError("not_mentioned requires final_score=None")
            if self.confidence is not None:
                raise ValueError("not_mentioned requires confidence=None")
            if self.evidence:
                raise ValueError("not_mentioned requires evidence=[]")
        else:
            # present, denied, possible all require discussed=True
            if self.discussed is not True:
                raise ValueError(f"{self.assertion} requires discussed=True")
            if self.final_score is None:
                raise ValueError(f"{self.assertion} requires final_score != None")
            if self.confidence is None:
                raise ValueError(f"{self.assertion} requires confidence != None")
            if not self.evidence:
                raise ValueError(f"{self.assertion} requires at least one evidence snippet")

            # Assertion-specific score constraints
            if self.assertion == "denied" and self.final_score != 0:
                raise ValueError("denied requires final_score=0")
            if self.assertion == "present" and self.final_score not in (1, 2, 3):
                raise ValueError("present requires final_score in {1, 2, 3}")
            if self.assertion == "possible" and self.final_score != 1:
                raise ValueError("possible requires final_score=1 (SSOT Q4 answer)")

        return self


class JudgeItemReportNA(JudgeItemResolutionNA):
    """NA-aware judge decision plus token usage metadata."""

    usage: TokenUsage | None = None
