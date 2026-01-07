from __future__ import annotations

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
    def test_not_mentioned_is_strict_nulls(self) -> None:
        item = HuggingFaceItemExport(
            assertion="not_mentioned",
            score=None,
            confidence=None,
            evidence=[],
        )
        assert item.score is None

    def test_present_requires_score_1_to_3(self) -> None:
        with pytest.raises(ValidationError, match="present requires score"):
            HuggingFaceItemExport(
                assertion="present",
                score=0,
                confidence=0.8,
                evidence=["..."],
            )

    def test_denied_requires_score_0(self) -> None:
        with pytest.raises(ValidationError, match="denied requires score=0"):
            HuggingFaceItemExport(
                assertion="denied",
                score=2,
                confidence=0.8,
                evidence=["..."],
            )

    def test_possible_requires_score_1(self) -> None:
        with pytest.raises(ValidationError, match="possible requires score=1"):
            HuggingFaceItemExport(
                assertion="possible",
                score=2,
                confidence=0.6,
                evidence=["Maybe..."],
            )

    def test_non_na_requires_evidence(self) -> None:
        with pytest.raises(ValidationError, match="requires at least one evidence"):
            HuggingFaceItemExport(
                assertion="present",
                score=1,
                confidence=0.6,
                evidence=[],
            )


class TestHuggingFaceDialogueExport:
    def _make_items(self) -> dict[str, HuggingFaceItemExport]:
        items: dict[str, HuggingFaceItemExport] = {}
        for item in PHQ8_ITEMS:
            items[item] = HuggingFaceItemExport(
                assertion="present",
                score=1,
                confidence=0.8,
                evidence=["evidence"],
            )
        return items

    def _make_totals(self) -> HuggingFaceTotalsExport:
        return HuggingFaceTotalsExport(
            discussed_count=8,
            discussed_sum=8,
            coverage=1.0,
            prorated_total=8.0,
            prorated_total_rounded=8,
            imputed_total=8,
            na_count=0,
            is_min_coverage=True,
            is_proration_valid=True,
        )

    def _make_metadata(self) -> HuggingFaceMetadataExport:
        return HuggingFaceMetadataExport(
            prompt_version="v2.0.0-clinical",
            juror_models=["gpt-5.2"],
            runs_per_model=2,
            arbitration_triggered=False,
            judge_model=None,
        )

    def test_items_keys_must_match(self) -> None:
        items = self._make_items()
        del items["psychomotor"]
        with pytest.raises(ValidationError, match="Missing="):
            HuggingFaceDialogueExport(
                dialogue_id="d1",
                condition="mdd",
                split="train",
                items=items,
                totals=self._make_totals(),
                scoring_metadata=self._make_metadata(),
            )
