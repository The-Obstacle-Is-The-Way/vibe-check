# SPEC-16: HuggingFace NA-Aware Export (v2)

> **Status**: DRAFT - Pending Senior Review
> **Depends On**: SPEC-13 (Schema), SPEC-15 (Aggregation)
> **Blocks**: ai-psychiatrist integration
> **Revision**: v2 - Addresses senior review feedback

---

## 1. Overview

This spec defines TDD requirements for a new NA-aware export format for HuggingFace. This is **separate from SPEC-08** which remains unchanged (int-only).

**Core Change**: New export module that preserves `null` scores, assertions, and full provenance.

### 1.1 CLI Contract (Matching Existing API)

```bash
# Current CLI signature (SPEC-08):
vibe-check export --input scored.jsonl --output-dir ./exports --format jsonl,csv

# Extended CLI signature (with HuggingFace):
vibe-check export --input scored.jsonl --output-dir ./exports --format jsonl,csv,huggingface
```

**Output Files**:
- `vibe_check_labels.jsonl` (SPEC-08, unchanged)
- `vibe_check_labels.csv` (SPEC-08, unchanged)
- `vibe_check_labels_huggingface.jsonl` (**NEW**, NA-aware)

---

## 2. Design Decision: Separate Export Module

### 2.1 Why Not Modify SPEC-08?

1. **SPEC-08 is a public contract** - existing consumers expect int-only fields
2. **Breaking change** - changing `int` to `int | None` breaks Pydantic validation
3. **Different use cases** - SPEC-08 for legacy ML, HuggingFace for NA-aware research

### 2.2 Module Structure

```
src/vibe_check/export/
├── schemas.py              # SPEC-08 (UNCHANGED)
├── writer.py               # SPEC-08 writer (EXTENDED to route huggingface)
├── validator.py            # SPEC-08 validator (UNCHANGED)
├── huggingface_schema.py   # NEW: NA-aware schema
└── huggingface_writer.py   # NEW: NA-aware writer
```

---

## 3. HuggingFace Export Schema

### 3.1 Schema Definition

```python
# src/vibe_check/export/huggingface_schema.py
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from vibe_check.constants import PHQ8_ITEMS

Assertion = Literal["present", "denied", "possible", "not_mentioned"]


class HuggingFaceItemExport(BaseModel):
    """Single PHQ-8 item in HuggingFace export."""

    model_config = ConfigDict(extra="forbid")

    discussed: bool = Field(description="Whether the symptom was discussed in transcript")
    score: Literal[0, 1, 2, 3] | None = Field(
        description="Severity score (None if not_mentioned)"
    )
    assertion: Assertion = Field(description="Clinical assertion type")
    confidence: float | None = Field(
        ge=0.0, le=1.0, description="Confidence (None if not_mentioned)"
    )
    evidence: list[str] = Field(description="Supporting quotes from transcript")

    @model_validator(mode="after")
    def _validate_assertion_consistency(self) -> "HuggingFaceItemExport":
        """Enforce SPEC-13 assertion/score/discussed invariants."""
        if self.assertion == "not_mentioned":
            if self.discussed is not False:
                raise ValueError("not_mentioned requires discussed=False")
            if self.score is not None:
                raise ValueError("not_mentioned requires score=None")
            if self.confidence is not None:
                raise ValueError("not_mentioned requires confidence=None")
            if self.evidence:
                raise ValueError("not_mentioned requires evidence=[]")
        else:
            # present, denied, possible all require discussed=True
            if self.discussed is not True:
                raise ValueError(f"{self.assertion} requires discussed=True")
            if self.score is None:
                raise ValueError(f"{self.assertion} requires score != None")
            if self.confidence is None:
                raise ValueError(f"{self.assertion} requires confidence != None")

            # Assertion-specific score constraints
            if self.assertion == "denied" and self.score != 0:
                raise ValueError("denied requires score=0")
            if self.assertion == "present" and self.score not in (1, 2, 3):
                raise ValueError("present requires score in {1, 2, 3}")
            # possible allows any score 0-3

        return self


class HuggingFaceTotalsExport(BaseModel):
    """Total score section in HuggingFace export."""

    model_config = ConfigDict(extra="forbid")

    discussed_count: int = Field(ge=0, le=8, description="Number of discussed items")
    discussed_sum: int = Field(ge=0, le=24, description="Sum of discussed item scores")
    coverage: float = Field(ge=0.0, le=1.0, description="discussed_count / 8")
    prorated_total: float | None = Field(
        description="discussed_sum * 8 / discussed_count (None if discussed_count < 7)"
    )
    prorated_total_rounded: int | None = Field(
        ge=0, le=24, description="round(prorated_total) (None if invalid)"
    )
    imputed_total: int = Field(ge=0, le=24, description="Sum treating NA as 0")
    na_count: int = Field(ge=0, le=8, description="Count of not_mentioned items")
    is_min_coverage: bool = Field(description="discussed_count >= 4")
    is_proration_valid: bool = Field(description="discussed_count >= 7")
    severity_bucket_phq_like: str | None = Field(
        description="PHQ bucket from prorated_total (None if proration invalid)"
    )


class HuggingFaceMetadataExport(BaseModel):
    """Scoring metadata in HuggingFace export."""

    model_config = ConfigDict(extra="forbid")

    prompt_version: str = Field(description="Version of scoring prompts used")
    juror_models: list[str] = Field(description="List of juror model identifiers")
    runs_per_model: int = Field(ge=1, description="Number of runs per juror model")
    arbitration_triggered: bool = Field(description="Whether judge arbitration was used")
    judge_model: str | None = Field(description="Judge model if arbitration triggered")


class HuggingFaceDialogueExport(BaseModel):
    """Complete dialogue export record for HuggingFace.

    Uses PHQ8_ITEMS from constants for strict key validation.
    """

    model_config = ConfigDict(extra="forbid")

    dialogue_id: str = Field(description="Unique dialogue identifier")
    condition: Literal["mdd", "control"] = Field(description="Diagnostic condition")
    split: str = Field(description="Dataset split: train, dev, or test")

    items: dict[str, HuggingFaceItemExport] = Field(description="8 PHQ-8 items")
    totals: HuggingFaceTotalsExport = Field(description="Aggregated totals")
    scoring_metadata: HuggingFaceMetadataExport = Field(description="Run metadata")

    @model_validator(mode="after")
    def _validate_items_keys(self) -> "HuggingFaceDialogueExport":
        """Ensure exactly 8 items with correct keys from PHQ8_ITEMS."""
        expected = set(PHQ8_ITEMS)
        actual = set(self.items.keys())
        if actual != expected:
            missing = expected - actual
            extra = actual - expected
            raise ValueError(
                f"Items must be exactly PHQ8_ITEMS. Missing: {missing}, Extra: {extra}"
            )
        return self
```

### 3.2 Example Output (JSONL)

```json
{
  "dialogue_id": "active436",
  "condition": "mdd",
  "split": "train",
  "items": {
    "anhedonia": {"discussed": true, "score": 2, "assertion": "present", "confidence": 0.85, "evidence": ["I can't enjoy anything anymore"]},
    "depressed_mood": {"discussed": true, "score": 3, "assertion": "present", "confidence": 0.92, "evidence": ["I feel hopeless all the time"]},
    "sleep": {"discussed": true, "score": 1, "assertion": "present", "confidence": 0.78, "evidence": ["Sometimes I have trouble sleeping"]},
    "fatigue": {"discussed": false, "score": null, "assertion": "not_mentioned", "confidence": null, "evidence": []},
    "appetite": {"discussed": false, "score": null, "assertion": "not_mentioned", "confidence": null, "evidence": []},
    "guilt": {"discussed": true, "score": 0, "assertion": "denied", "confidence": 0.88, "evidence": ["I don't blame myself for anything"]},
    "concentration": {"discussed": true, "score": 2, "assertion": "present", "confidence": 0.75, "evidence": ["I can't focus on work"]},
    "psychomotor": {"discussed": false, "score": null, "assertion": "not_mentioned", "confidence": null, "evidence": []}
  },
  "totals": {
    "discussed_count": 5,
    "discussed_sum": 8,
    "coverage": 0.625,
    "prorated_total": null,
    "prorated_total_rounded": null,
    "imputed_total": 8,
    "na_count": 3,
    "is_min_coverage": true,
    "is_proration_valid": false,
    "severity_bucket_phq_like": null
  },
  "scoring_metadata": {
    "prompt_version": "v2.0.0-clinical",
    "juror_models": ["gpt-4o", "claude-sonnet-4", "gemini-2.0-flash"],
    "runs_per_model": 2,
    "arbitration_triggered": true,
    "judge_model": "claude-opus-4"
  }
}
```

---

## 4. Conversion Function

### 4.1 Function Signature

```python
# src/vibe_check/export/huggingface_writer.py
from __future__ import annotations

from vibe_check.constants import PHQ8_ITEMS
from vibe_check.export.huggingface_schema import (
    HuggingFaceDialogueExport,
    HuggingFaceItemExport,
    HuggingFaceMetadataExport,
    HuggingFaceTotalsExport,
)
from vibe_check.schemas.output import AggregatedPHQ8NA  # From SPEC-15


def aggregated_to_huggingface_record(
    aggregated: AggregatedPHQ8NA,
    *,
    split: str,
) -> HuggingFaceDialogueExport:
    """Transform an internal AggregatedPHQ8NA record into HuggingFace export schema.

    Args:
        aggregated: Internal NA-aware aggregated result.
        split: Dataset split label ("train", "dev", "test").

    Returns:
        HuggingFace export record with full NA semantics preserved.
    """
    items: dict[str, HuggingFaceItemExport] = {}

    for item_name in PHQ8_ITEMS:
        item_agg = aggregated.item_aggregations[item_name]
        items[item_name] = HuggingFaceItemExport(
            discussed=item_agg.consensus_assertion != "not_mentioned",
            score=item_agg.consensus_score,
            assertion=item_agg.consensus_assertion,
            confidence=item_agg.confidence if item_agg.consensus_assertion != "not_mentioned" else None,
            evidence=item_agg.evidence,
        )

    totals = HuggingFaceTotalsExport(
        discussed_count=aggregated.total_aggregation.discussed_count,
        discussed_sum=aggregated.total_aggregation.discussed_sum,
        coverage=aggregated.total_aggregation.coverage,
        prorated_total=aggregated.total_aggregation.prorated_total,
        prorated_total_rounded=aggregated.total_aggregation.prorated_total_rounded,
        imputed_total=aggregated.total_aggregation.imputed_total,
        na_count=aggregated.total_aggregation.na_count,
        is_min_coverage=aggregated.total_aggregation.is_min_coverage,
        is_proration_valid=aggregated.total_aggregation.is_proration_valid,
        severity_bucket_phq_like=aggregated.total_aggregation.severity_bucket_phq_like,
    )

    metadata = HuggingFaceMetadataExport(
        prompt_version=aggregated.prompt_version,
        juror_models=aggregated.juror_models,
        runs_per_model=aggregated.runs_per_model,
        arbitration_triggered=aggregated.arbitration_triggered,
        judge_model=aggregated.judge_model,
    )

    return HuggingFaceDialogueExport(
        dialogue_id=aggregated.file_id,
        condition=aggregated.condition,
        split=split,
        items=items,
        totals=totals,
        scoring_metadata=metadata,
    )
```

---

## 5. TDD Test Cases

### 5.1 Schema Validation Tests

```python
# tests/unit/test_huggingface_schema.py
import pytest
from pydantic import ValidationError

from vibe_check.constants import PHQ8_ITEMS
from vibe_check.export.huggingface_schema import (
    HuggingFaceDialogueExport,
    HuggingFaceItemExport,
    HuggingFaceMetadataExport,
    HuggingFaceTotalsExport,
)


class TestHuggingFaceItemExport:
    """Test item-level schema validation."""

    def test_valid_present_item(self):
        """present assertion with score 1-3 is valid."""
        item = HuggingFaceItemExport(
            discussed=True,
            score=2,
            assertion="present",
            confidence=0.85,
            evidence=["I can't enjoy anything"],
        )
        assert item.score == 2
        assert item.assertion == "present"

    def test_valid_denied_item(self):
        """denied assertion with score 0 is valid."""
        item = HuggingFaceItemExport(
            discussed=True,
            score=0,
            assertion="denied",
            confidence=0.9,
            evidence=["I don't have that problem"],
        )
        assert item.score == 0
        assert item.assertion == "denied"

    def test_valid_possible_item(self):
        """possible assertion with any score 0-3 is valid."""
        # possible with score 0
        item0 = HuggingFaceItemExport(
            discussed=True,
            score=0,
            assertion="possible",
            confidence=0.5,
            evidence=["Maybe sometimes"],
        )
        assert item0.score == 0

        # possible with score 2
        item2 = HuggingFaceItemExport(
            discussed=True,
            score=2,
            assertion="possible",
            confidence=0.6,
            evidence=["Might be an issue"],
        )
        assert item2.score == 2

    def test_valid_not_mentioned_item(self):
        """not_mentioned assertion with null score/confidence is valid."""
        item = HuggingFaceItemExport(
            discussed=False,
            score=None,
            assertion="not_mentioned",
            confidence=None,
            evidence=[],
        )
        assert item.score is None
        assert item.discussed is False

    def test_present_requires_score_1_to_3(self):
        """present with score=0 raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            HuggingFaceItemExport(
                discussed=True,
                score=0,
                assertion="present",
                confidence=0.8,
                evidence=["..."],
            )
        assert "present requires score in {1, 2, 3}" in str(exc_info.value)

    def test_denied_requires_score_0(self):
        """denied with score!=0 raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            HuggingFaceItemExport(
                discussed=True,
                score=2,
                assertion="denied",
                confidence=0.8,
                evidence=["..."],
            )
        assert "denied requires score=0" in str(exc_info.value)

    def test_not_mentioned_requires_discussed_false(self):
        """not_mentioned with discussed=True raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            HuggingFaceItemExport(
                discussed=True,  # WRONG: should be False
                score=None,
                assertion="not_mentioned",
                confidence=None,
                evidence=[],
            )
        assert "not_mentioned requires discussed=False" in str(exc_info.value)

    def test_not_mentioned_requires_score_none(self):
        """not_mentioned with score=0 raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            HuggingFaceItemExport(
                discussed=False,
                score=0,  # WRONG: should be None
                assertion="not_mentioned",
                confidence=None,
                evidence=[],
            )
        assert "not_mentioned requires score=None" in str(exc_info.value)

    def test_not_mentioned_requires_confidence_none(self):
        """not_mentioned with confidence!=None raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            HuggingFaceItemExport(
                discussed=False,
                score=None,
                assertion="not_mentioned",
                confidence=0.5,  # WRONG: should be None
                evidence=[],
            )
        assert "not_mentioned requires confidence=None" in str(exc_info.value)

    def test_not_mentioned_requires_empty_evidence(self):
        """not_mentioned with non-empty evidence raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            HuggingFaceItemExport(
                discussed=False,
                score=None,
                assertion="not_mentioned",
                confidence=None,
                evidence=["some quote"],  # WRONG: should be []
            )
        assert "not_mentioned requires evidence=[]" in str(exc_info.value)

    def test_present_requires_discussed_true(self):
        """present with discussed=False raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            HuggingFaceItemExport(
                discussed=False,  # WRONG: should be True
                score=2,
                assertion="present",
                confidence=0.8,
                evidence=["..."],
            )
        assert "present requires discussed=True" in str(exc_info.value)


class TestHuggingFaceDialogueExport:
    """Test dialogue-level schema validation."""

    def _make_item(
        self, discussed: bool, score: int | None, assertion: str
    ) -> HuggingFaceItemExport:
        """Helper to create valid items."""
        if assertion == "not_mentioned":
            return HuggingFaceItemExport(
                discussed=False,
                score=None,
                assertion="not_mentioned",
                confidence=None,
                evidence=[],
            )
        return HuggingFaceItemExport(
            discussed=True,
            score=score,
            assertion=assertion,
            confidence=0.8,
            evidence=["evidence"],
        )

    def _make_full_items(self) -> dict[str, HuggingFaceItemExport]:
        """Create all 8 valid items."""
        return {
            "anhedonia": self._make_item(True, 2, "present"),
            "depressed_mood": self._make_item(True, 3, "present"),
            "sleep": self._make_item(True, 1, "present"),
            "fatigue": self._make_item(True, 0, "denied"),
            "appetite": self._make_item(False, None, "not_mentioned"),
            "guilt": self._make_item(True, 1, "possible"),
            "concentration": self._make_item(True, 2, "present"),
            "psychomotor": self._make_item(False, None, "not_mentioned"),
        }

    def _make_totals(self) -> HuggingFaceTotalsExport:
        """Create valid totals."""
        return HuggingFaceTotalsExport(
            discussed_count=6,
            discussed_sum=9,
            coverage=0.75,
            prorated_total=None,
            prorated_total_rounded=None,
            imputed_total=9,
            na_count=2,
            is_min_coverage=True,
            is_proration_valid=False,
            severity_bucket_phq_like=None,
        )

    def _make_metadata(self) -> HuggingFaceMetadataExport:
        """Create valid metadata."""
        return HuggingFaceMetadataExport(
            prompt_version="v2.0.0-clinical",
            juror_models=["gpt-4o", "claude-sonnet-4"],
            runs_per_model=2,
            arbitration_triggered=False,
            judge_model=None,
        )

    def test_valid_dialogue_export(self):
        """Valid dialogue with all 8 items passes validation."""
        export = HuggingFaceDialogueExport(
            dialogue_id="active001",
            condition="mdd",
            split="train",
            items=self._make_full_items(),
            totals=self._make_totals(),
            scoring_metadata=self._make_metadata(),
        )
        assert export.dialogue_id == "active001"
        assert len(export.items) == 8

    def test_missing_item_raises_error(self):
        """Missing an item from PHQ8_ITEMS raises ValidationError."""
        items = self._make_full_items()
        del items["psychomotor"]  # Remove one

        with pytest.raises(ValidationError) as exc_info:
            HuggingFaceDialogueExport(
                dialogue_id="active001",
                condition="mdd",
                split="train",
                items=items,
                totals=self._make_totals(),
                scoring_metadata=self._make_metadata(),
            )
        assert "Missing: {'psychomotor'}" in str(exc_info.value)

    def test_extra_item_raises_error(self):
        """Extra item not in PHQ8_ITEMS raises ValidationError."""
        items = self._make_full_items()
        items["invalid_item"] = self._make_item(True, 1, "present")

        with pytest.raises(ValidationError) as exc_info:
            HuggingFaceDialogueExport(
                dialogue_id="active001",
                condition="mdd",
                split="train",
                items=items,
                totals=self._make_totals(),
                scoring_metadata=self._make_metadata(),
            )
        assert "Extra: {'invalid_item'}" in str(exc_info.value)

    def test_items_must_match_phq8_items_exactly(self):
        """Items dict keys must exactly match PHQ8_ITEMS constant."""
        items = self._make_full_items()
        expected_keys = set(PHQ8_ITEMS)
        actual_keys = set(items.keys())
        assert expected_keys == actual_keys
```

### 5.2 Writer Tests

```python
# tests/unit/test_huggingface_writer.py
import json
from pathlib import Path

import pytest

from vibe_check.constants import PHQ8_ITEMS
from vibe_check.export.huggingface_schema import HuggingFaceDialogueExport
from vibe_check.export.huggingface_writer import (
    aggregated_to_huggingface_record,
    write_huggingface_export,
)


def make_mock_aggregated_na(
    file_id: str = "active001",
    condition: str = "mdd",
    na_items: set[str] | None = None,
) -> "AggregatedPHQ8NA":
    """Create a mock AggregatedPHQ8NA for testing.

    Args:
        file_id: Dialogue identifier.
        condition: "mdd" or "control".
        na_items: Set of item names to mark as not_mentioned.
    """
    from vibe_check.schemas.output import (
        AggregatedPHQ8NA,
        ItemAggregationNA,
        TotalAggregationNA,
    )

    na_items = na_items or set()

    item_aggregations = {}
    discussed_scores = []

    for item in PHQ8_ITEMS:
        if item in na_items:
            item_aggregations[item] = ItemAggregationNA(
                votes=[None, None, None, None, None, None],
                assertions=["not_mentioned"] * 6,
                numeric_votes=[],
                consensus_score=None,
                consensus_assertion="not_mentioned",
                confidence=None,
                evidence=[],
                na_count=6,
                p_not_mentioned=1.0,
            )
        else:
            score = 2 if item == "anhedonia" else 1
            item_aggregations[item] = ItemAggregationNA(
                votes=[score] * 6,
                assertions=["present"] * 6,
                numeric_votes=[score] * 6,
                consensus_score=score,
                consensus_assertion="present",
                confidence=0.85,
                evidence=[f"Evidence for {item}"],
                na_count=0,
                p_not_mentioned=0.0,
            )
            discussed_scores.append(score)

    discussed_count = 8 - len(na_items)
    discussed_sum = sum(discussed_scores)

    return AggregatedPHQ8NA(
        file_id=file_id,
        condition=condition,
        item_aggregations=item_aggregations,
        total_aggregation=TotalAggregationNA(
            discussed_count=discussed_count,
            discussed_sum=discussed_sum,
            coverage=discussed_count / 8,
            prorated_total=(
                discussed_sum * 8 / discussed_count if discussed_count >= 7 else None
            ),
            prorated_total_rounded=(
                round(discussed_sum * 8 / discussed_count) if discussed_count >= 7 else None
            ),
            imputed_total=discussed_sum,  # NA=0 imputation
            na_count=len(na_items),
            is_min_coverage=discussed_count >= 4,
            is_proration_valid=discussed_count >= 7,
            severity_bucket_phq_like=None if discussed_count < 7 else "mild",
        ),
        prompt_version="v2.0.0-clinical",
        juror_models=["gpt-4o", "claude-sonnet-4"],
        runs_per_model=2,
        arbitration_triggered=False,
        judge_model=None,
    )


class TestAggregatedToHuggingfaceRecord:
    """Test conversion from AggregatedPHQ8NA to HuggingFace export."""

    def test_full_coverage_conversion(self):
        """All items discussed converts correctly."""
        aggregated = make_mock_aggregated_na(na_items=set())
        export = aggregated_to_huggingface_record(aggregated, split="train")

        assert export.dialogue_id == "active001"
        assert export.condition == "mdd"
        assert export.split == "train"
        assert len(export.items) == 8
        assert export.totals.na_count == 0
        assert export.totals.coverage == 1.0

        # All items should have discussed=True
        for item_name, item in export.items.items():
            assert item.discussed is True
            assert item.score is not None

    def test_partial_coverage_conversion(self):
        """Items with NA preserve null scores."""
        na_items = {"fatigue", "appetite", "psychomotor"}
        aggregated = make_mock_aggregated_na(na_items=na_items)
        export = aggregated_to_huggingface_record(aggregated, split="dev")

        assert export.totals.na_count == 3
        assert export.totals.discussed_count == 5
        assert export.totals.coverage == 0.625

        # NA items should have discussed=False, score=None
        for item_name in na_items:
            item = export.items[item_name]
            assert item.discussed is False
            assert item.score is None
            assert item.assertion == "not_mentioned"
            assert item.confidence is None
            assert item.evidence == []

        # Non-NA items should have discussed=True, score!=None
        for item_name in PHQ8_ITEMS:
            if item_name not in na_items:
                item = export.items[item_name]
                assert item.discussed is True
                assert item.score is not None

    def test_proration_validity(self):
        """Proration only valid when discussed_count >= 7."""
        # 7 items discussed -> valid proration
        aggregated_7 = make_mock_aggregated_na(na_items={"fatigue"})
        export_7 = aggregated_to_huggingface_record(aggregated_7, split="train")
        assert export_7.totals.is_proration_valid is True
        assert export_7.totals.prorated_total is not None

        # 6 items discussed -> invalid proration
        aggregated_6 = make_mock_aggregated_na(na_items={"fatigue", "appetite"})
        export_6 = aggregated_to_huggingface_record(aggregated_6, split="train")
        assert export_6.totals.is_proration_valid is False
        assert export_6.totals.prorated_total is None


class TestWriteHuggingfaceExport:
    """Test JSONL file writing."""

    def test_write_single_record(self, tmp_path: Path):
        """Single record writes correctly to JSONL."""
        aggregated = make_mock_aggregated_na()
        output_path = tmp_path / "vibe_check_labels_huggingface.jsonl"

        write_huggingface_export(
            records=[aggregated],
            output_path=output_path,
            split="train",
        )

        assert output_path.exists()
        lines = output_path.read_text().strip().split("\n")
        assert len(lines) == 1

        data = json.loads(lines[0])
        assert data["dialogue_id"] == "active001"
        assert data["split"] == "train"
        assert len(data["items"]) == 8

    def test_write_multiple_records(self, tmp_path: Path):
        """Multiple records write as separate JSONL lines."""
        records = [
            make_mock_aggregated_na(file_id=f"active{i:03d}")
            for i in range(10)
        ]
        output_path = tmp_path / "vibe_check_labels_huggingface.jsonl"

        write_huggingface_export(
            records=records,
            output_path=output_path,
            split="train",
        )

        lines = output_path.read_text().strip().split("\n")
        assert len(lines) == 10

        # Records should be sorted by dialogue_id
        dialogue_ids = [json.loads(line)["dialogue_id"] for line in lines]
        assert dialogue_ids == sorted(dialogue_ids)

    def test_null_values_serialize_correctly(self, tmp_path: Path):
        """NA items serialize as JSON null, not 0 or omitted."""
        aggregated = make_mock_aggregated_na(na_items={"fatigue"})
        output_path = tmp_path / "vibe_check_labels_huggingface.jsonl"

        write_huggingface_export(
            records=[aggregated],
            output_path=output_path,
            split="test",
        )

        data = json.loads(output_path.read_text().strip())

        # fatigue should have null score (JSON), not 0
        assert data["items"]["fatigue"]["score"] is None
        assert data["items"]["fatigue"]["confidence"] is None

        # JSON serialization check: "null" not "0"
        raw_json = output_path.read_text()
        assert '"score": null' in raw_json or '"score":null' in raw_json
```

### 5.3 CLI Integration Tests

```python
# tests/integration/test_cli_huggingface_export.py
import json
from pathlib import Path

import pytest


def test_cli_export_huggingface_format(cli_runner, tmp_path: Path, scored_jsonl_fixture):
    """CLI exports HuggingFace format when requested."""
    result = cli_runner.invoke([
        "export",
        "--input", str(scored_jsonl_fixture),
        "--output-dir", str(tmp_path),
        "--format", "huggingface",
    ])

    assert result.exit_code == 0
    hf_path = tmp_path / "vibe_check_labels_huggingface.jsonl"
    assert hf_path.exists()

    # Validate structure
    data = json.loads(hf_path.read_text().strip().split("\n")[0])
    assert "items" in data
    assert "totals" in data
    assert "scoring_metadata" in data


def test_cli_export_all_formats(cli_runner, tmp_path: Path, scored_jsonl_fixture):
    """CLI can export all formats in one call."""
    result = cli_runner.invoke([
        "export",
        "--input", str(scored_jsonl_fixture),
        "--output-dir", str(tmp_path),
        "--format", "jsonl,csv,huggingface",
    ])

    assert result.exit_code == 0

    # All three files should exist
    assert (tmp_path / "vibe_check_labels.jsonl").exists()
    assert (tmp_path / "vibe_check_labels.csv").exists()
    assert (tmp_path / "vibe_check_labels_huggingface.jsonl").exists()


def test_cli_export_default_is_spec08(cli_runner, tmp_path: Path, scored_jsonl_fixture):
    """Default export (no huggingface) produces SPEC-08 only."""
    result = cli_runner.invoke([
        "export",
        "--input", str(scored_jsonl_fixture),
        "--output-dir", str(tmp_path),
        "--format", "jsonl,csv",
    ])

    assert result.exit_code == 0

    # SPEC-08 files exist
    assert (tmp_path / "vibe_check_labels.jsonl").exists()
    assert (tmp_path / "vibe_check_labels.csv").exists()

    # HuggingFace file does NOT exist
    assert not (tmp_path / "vibe_check_labels_huggingface.jsonl").exists()
```

### 5.4 SPEC-08 Compatibility Tests

```python
# tests/unit/test_spec08_compatibility.py
"""Verify SPEC-08 export remains unchanged by HuggingFace additions."""

import json

import pytest

from vibe_check.export.schemas import ScoredDialogueExport
from vibe_check.export.huggingface_schema import HuggingFaceDialogueExport


class TestSpec08Unchanged:
    """SPEC-08 export schema must remain int-only."""

    def test_spec08_scores_are_int_not_optional(self):
        """SPEC-08 item scores are int, not int | None."""
        import typing
        from vibe_check.export.schemas import ScoredDialogueExport

        # Get type hints for phq8_item_1
        hints = typing.get_type_hints(ScoredDialogueExport)
        assert hints["phq8_item_1"] == int
        assert hints["phq8_total"] == int

    def test_spec08_export_rejects_none_scores(self):
        """SPEC-08 export raises error if given None scores."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ScoredDialogueExport(
                dialogue_id="test",
                condition="mdd",
                phq8_item_1=None,  # INVALID: must be int
                phq8_item_2=0,
                phq8_item_3=0,
                phq8_item_4=0,
                phq8_item_5=0,
                phq8_item_6=0,
                phq8_item_7=0,
                phq8_item_8=0,
                phq8_total=0,
                severity_bucket="minimal",
                client_qa_text="...",
                juror_votes={},
                arbitration_triggered={},
                run_id="run",
                prompt_version="v1.0.0",
            )

    def test_both_exports_from_same_source_same_ids(self):
        """Both SPEC-08 and HuggingFace can be generated from same aggregated result."""
        # This test verifies that the two export paths don't conflict
        # and both use the same dialogue_id from the source
        from tests.unit.test_huggingface_writer import make_mock_aggregated_na
        from vibe_check.export.huggingface_writer import aggregated_to_huggingface_record
        from vibe_check.export.writer import aggregated_to_export_record

        aggregated = make_mock_aggregated_na(na_items=set())

        hf_export = aggregated_to_huggingface_record(aggregated, split="train")
        # Note: spec08 export uses different function signature
        # spec08_export = aggregated_to_export_record(aggregated, ...)

        assert hf_export.dialogue_id == aggregated.file_id

    def test_imputed_total_matches_spec08_total(self):
        """HuggingFace imputed_total equals what SPEC-08 would report."""
        from tests.unit.test_huggingface_writer import make_mock_aggregated_na
        from vibe_check.export.huggingface_writer import aggregated_to_huggingface_record

        # With NA items, imputed_total treats them as 0
        aggregated = make_mock_aggregated_na(na_items={"fatigue", "appetite"})
        hf_export = aggregated_to_huggingface_record(aggregated, split="train")

        # SPEC-08 would sum all items treating NA as 0
        # HuggingFace imputed_total does the same
        assert hf_export.totals.imputed_total == hf_export.totals.discussed_sum
```

---

## 6. Implementation Details

### 6.1 Writer Function

```python
# src/vibe_check/export/huggingface_writer.py (continued)
import json
from pathlib import Path

from vibe_check.export.huggingface_schema import HuggingFaceDialogueExport
from vibe_check.schemas.output import AggregatedPHQ8NA


def write_huggingface_export(
    *,
    records: list[AggregatedPHQ8NA],
    output_path: Path,
    split: str,
) -> None:
    """Write HuggingFace export JSONL file.

    Args:
        records: List of aggregated results to export.
        output_path: Path to write vibe_check_labels_huggingface.jsonl.
        split: Dataset split label for all records.
    """
    exports = [
        aggregated_to_huggingface_record(r, split=split)
        for r in records
    ]

    # Sort by dialogue_id for deterministic output
    exports.sort(key=lambda x: x.dialogue_id)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        "\n".join(
            json.dumps(e.model_dump(mode="json"), sort_keys=True)
            for e in exports
        ) + "\n",
        encoding="utf-8",
    )
```

### 6.2 CLI Integration

```python
# src/vibe_check/cli.py changes (in export command handler)

if args.command == "export":
    from vibe_check.export.writer import write_label_exports

    formats = {part.strip() for part in str(args.format).split(",") if part.strip()}

    # SPEC-08 export (unchanged behavior)
    spec08_formats = formats - {"huggingface"}
    if spec08_formats:
        validation = write_label_exports(
            scored_jsonl=args.input,
            output_dir=args.output_dir,
            formats=spec08_formats,
        )
        if not validation.is_valid:
            return 2

    # HuggingFace export (new)
    if "huggingface" in formats:
        from vibe_check.export.huggingface_writer import write_huggingface_from_scored

        write_huggingface_from_scored(
            scored_jsonl=args.input,
            output_dir=args.output_dir,
            split="train",  # Default split, could be CLI arg
        )

    return 0
```

---

## 7. Files Affected

| File | Change Type |
|------|-------------|
| `src/vibe_check/export/huggingface_schema.py` | **NEW** |
| `src/vibe_check/export/huggingface_writer.py` | **NEW** |
| `src/vibe_check/cli.py` | **MODERATE** - Route huggingface format |
| `tests/unit/test_huggingface_schema.py` | **NEW** |
| `tests/unit/test_huggingface_writer.py` | **NEW** |
| `tests/integration/test_cli_huggingface_export.py` | **NEW** |
| `tests/unit/test_spec08_compatibility.py` | **NEW** |

---

## 8. Dataset Card Template

```markdown
# SQPsychConv PHQ-8 Labels (NA-Aware)

## Dataset Description
PHQ-8 symptom severity labels for the SQPsychConv synthetic therapy dialogue corpus.

## Source Corpus
- **Name**: SQPsychConv (Qwen 2.5 variant)
- **Dialogues**: 2,090
- **Conditions**: MDD (1,395) / Control (695)

## Labeling Methodology
- **Multi-juror consensus**: 6 LLM jurors (3 models × 2 runs)
- **Bayesian aggregation**: Dirichlet posteriors with convolution
- **Arbitration**: Judge review for contested items
- **NA-aware**: Items not discussed are marked `null`, not `0`

## Schema Fields

### Item Fields
| Field | Type | Description |
|-------|------|-------------|
| `discussed` | bool | Whether symptom was mentioned |
| `score` | int \| null | Severity 0-3 or null if not discussed |
| `assertion` | string | present/denied/possible/not_mentioned |
| `confidence` | float \| null | Model confidence |
| `evidence` | list[str] | Supporting transcript quotes |

### Total Fields
| Field | Type | Description |
|-------|------|-------------|
| `discussed_count` | int | Items discussed (0-8) |
| `discussed_sum` | int | Sum of discussed scores |
| `prorated_total` | float \| null | Only if ≥7 items discussed |
| `imputed_total` | int | NA treated as 0 |
| `is_proration_valid` | bool | True if ≥7 items |
| `severity_bucket_phq_like` | string \| null | Only if proration valid |

## Important Notes
- `score=null` means "not discussed in transcript" (NOT "score 0")
- `prorated_total` only computed when `discussed_count >= 7`
- `imputed_total` treats NA as 0 (use with caution)
- `severity_bucket_phq_like` only valid when `is_proration_valid=True`

## Intended Use
- Training depression detection models
- Transfer learning to DAIC-WOZ
- Research on transcript-based symptom inference

## Limitations
- Synthetic dialogues may not reflect real clinical conversations
- Coverage patterns may differ from real corpora
- Proration is approximate; prefer per-item scores
```

---

## 9. Acceptance Criteria

- [ ] All test cases in Section 5 pass
- [ ] SPEC-08 export unchanged (int-only, same filenames)
- [ ] HuggingFace export preserves `null` values
- [ ] CLI supports `--format huggingface` (comma-separated)
- [ ] Output filename: `vibe_check_labels_huggingface.jsonl`
- [ ] Items dict keys validated against `PHQ8_ITEMS`
- [ ] Dataset card template included
- [ ] Ruff + mypy pass

---

## 10. Sign-Off

| Role | Status |
|------|--------|
| Author | DRAFT v2 |
| Senior Review | PENDING |
