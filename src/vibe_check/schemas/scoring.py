"""Schemas for individual juror outputs (per-model PHQ-8 scoring)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from vibe_check.constants import MAX_EVIDENCE_SNIPPET_CHARS, MAX_EVIDENCE_SNIPPET_WORDS

if TYPE_CHECKING:
    from collections.abc import Mapping


class TokenUsage(BaseModel):
    """Token usage metadata for a single model call."""

    model_config = ConfigDict(extra="forbid")

    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    reasoning_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)


# NA-Aware Assertion type (SPEC-13 / SSOT §12.1)
Assertion = Literal["present", "denied", "possible", "not_mentioned"]


class PHQ8ItemScore(BaseModel):
    """Single PHQ-8 item score with clinical assertion semantics (SSOT §12.1)."""

    model_config = ConfigDict(extra="forbid")

    # NEW: Was this symptom domain mentioned for CLIENT+timeframe?
    discussed: bool = Field(
        description="True if there is evidence about the CLIENT's recent status for this item"
    )

    score: Literal[0, 1, 2, 3] | None = Field(description="0-3 severity; None if not_mentioned")

    assertion: Assertion = Field(
        description="Clinical-NLP-inspired assertion label (extended with not_mentioned)"
    )

    confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Model confidence; None when score is None",
    )

    evidence: list[str] = Field(
        default_factory=list,
        max_length=3,
        description="Up to 3 supporting quotes (empty for not_mentioned)",
    )

    @field_validator("discussed", mode="before")
    @classmethod
    def _validate_discussed_type(cls, value: Any) -> Any:
        if not isinstance(value, bool):
            raise ValueError("discussed must be a boolean (true/false), not a string or number")
        return value

    @field_validator("score", mode="before")
    @classmethod
    def _reject_boolean_score(cls, value: Any) -> Any:
        if isinstance(value, bool):
            raise ValueError("score must be an integer 0-3 (not boolean)")
        return value

    @field_validator("confidence", mode="before")
    @classmethod
    def _reject_boolean_confidence(cls, value: Any) -> Any:
        if isinstance(value, bool):
            raise ValueError("confidence must be a number 0.0-1.0 (not boolean)")
        return value

    @field_validator("evidence")
    @classmethod
    def _validate_evidence_snippets(cls, value: list[str]) -> list[str]:
        for snippet in value:
            cleaned = snippet.strip()
            if not cleaned:
                raise ValueError("evidence snippets must be non-empty after stripping whitespace")
            if len(cleaned) > MAX_EVIDENCE_SNIPPET_CHARS:
                raise ValueError(f"evidence snippet exceeds {MAX_EVIDENCE_SNIPPET_CHARS} chars")
            if len(cleaned.split()) > MAX_EVIDENCE_SNIPPET_WORDS:
                raise ValueError(f"evidence snippet exceeds {MAX_EVIDENCE_SNIPPET_WORDS} words")
        return value

    @model_validator(mode="after")
    def _validate_assertion_consistency(self) -> PHQ8ItemScore:
        """Enforce SSOT §12.1 assertion semantics."""
        if self.assertion == "not_mentioned":
            if self.discussed is not False:
                raise ValueError("not_mentioned requires discussed=False")
            if self.score is not None:
                raise ValueError("not_mentioned requires score=None")
            if self.confidence is not None:
                raise ValueError("not_mentioned requires confidence=None")
            if self.evidence:
                raise ValueError("not_mentioned requires evidence=[]")
        elif self.assertion == "denied":
            if self.discussed is not True:
                raise ValueError("denied requires discussed=True")
            if self.score != 0:
                raise ValueError("denied requires score=0")
            if self.confidence is None:
                raise ValueError("denied requires confidence (not None)")
            if not self.evidence:
                raise ValueError("denied requires at least one evidence snippet")
        elif self.assertion == "possible":
            if self.discussed is not True:
                raise ValueError("possible requires discussed=True")
            if self.score != 1:
                raise ValueError("possible requires score=1 (SSOT Q4 answer)")
            if self.confidence is None:
                raise ValueError("possible requires confidence (not None)")
            if not self.evidence:
                raise ValueError("possible requires at least one evidence snippet")
        elif self.assertion == "present":
            if self.discussed is not True:
                raise ValueError("present requires discussed=True")
            if self.score not in (1, 2, 3):
                raise ValueError("present requires score in {1, 2, 3}")
            if self.confidence is None:
                raise ValueError("present requires confidence (not None)")
            if not self.evidence:
                raise ValueError("present requires at least one evidence snippet")
        return self


class PHQ8TotalScore(BaseModel):
    """Total score with full provenance (SSOT §12.2)."""

    model_config = ConfigDict(extra="forbid")

    # Source data
    discussed_count: int = Field(ge=0, le=8)
    discussed_sum: int = Field(ge=0, le=24)

    # Derived (validated by model_validator)
    coverage: float = Field(ge=0.0, le=1.0)  # discussed_count / 8
    na_count: int = Field(ge=0, le=8)  # 8 - discussed_count

    # Prorated (only when discussed_count >= 7)
    prorated_total: float | None = Field(default=None, ge=0.0, le=24.0)
    prorated_total_rounded: int | None = Field(default=None, ge=0, le=24)

    # Imputed (NA→0)
    imputed_total: int = Field(ge=0, le=24)

    # Validity flags
    is_min_coverage: bool  # discussed_count >= 4
    is_proration_valid: bool  # discussed_count >= 7

    @classmethod
    def from_item_scores(cls, item_scores: Mapping[str, int | None]) -> PHQ8TotalScore:
        """Canonical constructor from item scores dict."""
        if len(item_scores) != 8:
            raise ValueError("item_scores must have exactly 8 items")

        discussed_scores = [s for s in item_scores.values() if s is not None]
        discussed_count = len(discussed_scores)
        discussed_sum = sum(discussed_scores)
        na_count = 8 - discussed_count

        coverage = discussed_count / 8.0
        imputed_total = discussed_sum  # NA items contribute 0

        is_min_coverage = discussed_count >= 4
        is_proration_valid = discussed_count >= 7

        prorated_total: float | None = None
        prorated_total_rounded: int | None = None
        if is_proration_valid and discussed_count > 0:
            prorated_total = (discussed_sum / discussed_count) * 8
            # Round half up (SSOT/APA convention)
            prorated_total_rounded = int(
                Decimal(str(prorated_total)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
            )

        return cls(
            discussed_count=discussed_count,
            discussed_sum=discussed_sum,
            coverage=coverage,
            na_count=na_count,
            prorated_total=prorated_total,
            prorated_total_rounded=prorated_total_rounded,
            imputed_total=imputed_total,
            is_min_coverage=is_min_coverage,
            is_proration_valid=is_proration_valid,
        )

    @model_validator(mode="after")
    def _validate_consistency(self) -> PHQ8TotalScore:
        """Enforce internal consistency."""
        if self.na_count != 8 - self.discussed_count:
            raise ValueError("na_count must equal 8 - discussed_count")
        if abs(self.coverage - self.discussed_count / 8.0) > 1e-9:
            raise ValueError("coverage must equal discussed_count / 8")
        if self.is_min_coverage != (self.discussed_count >= 4):
            raise ValueError("is_min_coverage inconsistent with discussed_count")
        if self.is_proration_valid != (self.discussed_count >= 7):
            raise ValueError("is_proration_valid inconsistent with discussed_count")
        if not self.is_proration_valid and (
            self.prorated_total is not None or self.prorated_total_rounded is not None
        ):
            raise ValueError("proration fields must be None when is_proration_valid=False")
        return self


class PHQ8Assessment(BaseModel):
    """The raw output from the LLM (items + total + safety)."""

    model_config = ConfigDict(extra="forbid")

    anhedonia: PHQ8ItemScore
    depressed_mood: PHQ8ItemScore
    sleep: PHQ8ItemScore
    fatigue: PHQ8ItemScore
    appetite: PHQ8ItemScore
    guilt: PHQ8ItemScore
    concentration: PHQ8ItemScore
    psychomotor: PHQ8ItemScore

    # Computed fields (imputed: NA→0)
    total_score: int = Field(ge=0, le=24, description="Sum of item scores; NA items contribute 0")
    discussed_count: int = Field(ge=0, le=8, description="Count of items with discussed=True")

    # Safety fields (unchanged)
    mentions_self_harm: bool = False
    self_harm_evidence: list[str] = Field(default_factory=list, max_length=3)

    @property
    def item_scores(self) -> dict[str, int | None]:
        """Return item scores (None for not_mentioned)."""
        return {
            "anhedonia": self.anhedonia.score,
            "depressed_mood": self.depressed_mood.score,
            "sleep": self.sleep.score,
            "fatigue": self.fatigue.score,
            "appetite": self.appetite.score,
            "guilt": self.guilt.score,
            "concentration": self.concentration.score,
            "psychomotor": self.psychomotor.score,
        }

    @model_validator(mode="before")
    @classmethod
    def _canonicalize_computed_fields(cls, data: Any) -> Any:
        """Compute total_score and discussed_count from items."""
        if not isinstance(data, dict):
            return data

        item_keys = (
            "anhedonia",
            "depressed_mood",
            "sleep",
            "fatigue",
            "appetite",
            "guilt",
            "concentration",
            "psychomotor",
        )

        total = 0
        discussed = 0
        for key in item_keys:
            item = data.get(key)
            if item is None:
                continue
            score = item.get("score") if isinstance(item, dict) else getattr(item, "score", None)
            disc = (
                item.get("discussed")
                if isinstance(item, dict)
                else getattr(item, "discussed", None)
            )

            if score is not None:
                total += int(score)
            if disc is True:
                discussed += 1

        # Canonicalize (overwrite if inconsistent)
        data["total_score"] = total
        data["discussed_count"] = discussed
        return data

    @model_validator(mode="after")
    def _check_computed_fields(self) -> PHQ8Assessment:
        """Validate computed fields match actual items."""
        expected_total = sum(s if s is not None else 0 for s in self.item_scores.values())
        expected_discussed = sum(
            1
            for item in [
                self.anhedonia,
                self.depressed_mood,
                self.sleep,
                self.fatigue,
                self.appetite,
                self.guilt,
                self.concentration,
                self.psychomotor,
            ]
            if item.discussed
        )
        if self.total_score != expected_total:
            raise ValueError(f"total_score={self.total_score} != computed {expected_total}")
        if self.discussed_count != expected_discussed:
            raise ValueError(
                f"discussed_count={self.discussed_count} != computed {expected_discussed}"
            )
        return self

    @field_validator("self_harm_evidence")
    @classmethod
    def _validate_self_harm_evidence(cls, value: list[str]) -> list[str]:
        for snippet in value:
            cleaned = snippet.strip()
            if not cleaned:
                raise ValueError("self_harm_evidence snippets must be non-empty strings")
            if len(cleaned) > MAX_EVIDENCE_SNIPPET_CHARS:
                raise ValueError(
                    f"self_harm_evidence snippet exceeds {MAX_EVIDENCE_SNIPPET_CHARS} characters"
                )
            if len(cleaned.split()) > MAX_EVIDENCE_SNIPPET_WORDS:
                raise ValueError(
                    f"self_harm_evidence snippet exceeds {MAX_EVIDENCE_SNIPPET_WORDS} words"
                )
        return value


class PHQ8Report(PHQ8Assessment):
    """Complete PHQ-8 assessment with metadata (provenance)."""

    model_id: str = Field(min_length=1, description="e.g., 'gpt-5.2'")
    run_number: int = Field(ge=1, le=2, description="Run 1 or 2")
    usage: TokenUsage | None = None
    scored_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
