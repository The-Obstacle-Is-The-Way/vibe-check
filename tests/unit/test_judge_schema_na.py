"""Tests for NA-aware judge schema (SPEC-17)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from vibe_check.constants import PHQ8_ITEMS
from vibe_check.judge.schema import JudgeItemResolutionNA


class TestJudgeItemResolutionNAValid:
    """Test valid NA-aware judge schema constructions."""

    def test_valid_present_resolution(self) -> None:
        """present assertion with score 1-3 is valid."""
        resolution = JudgeItemResolutionNA(
            item="anhedonia",
            discussed=True,
            final_score=2,
            assertion="present",
            confidence=0.85,
            evidence=["Client: I can't enjoy anything."],
            rationale="Client clearly states loss of interest in activities.",
        )
        assert resolution.final_score == 2
        assert resolution.assertion == "present"

    def test_valid_denied_resolution(self) -> None:
        """denied assertion with score 0 is valid."""
        resolution = JudgeItemResolutionNA(
            item="guilt",
            discussed=True,
            final_score=0,
            assertion="denied",
            confidence=0.9,
            evidence=["Client: I don't blame myself."],
            rationale="Client explicitly denies feeling guilty.",
        )
        assert resolution.final_score == 0
        assert resolution.assertion == "denied"

    def test_valid_possible_resolution(self) -> None:
        """possible assertion defaults to score=1 (SSOT Q4)."""
        resolution = JudgeItemResolutionNA(
            item="sleep",
            discussed=True,
            final_score=1,
            assertion="possible",
            confidence=0.6,
            evidence=["Client: Maybe I've been sleeping a bit worse."],
            rationale="Evidence is ambiguous but suggests mild sleep issues.",
        )
        assert resolution.final_score == 1
        assert resolution.assertion == "possible"

    def test_valid_not_mentioned_resolution(self) -> None:
        """not_mentioned assertion with null score is valid."""
        resolution = JudgeItemResolutionNA(
            item="psychomotor",
            discussed=False,
            final_score=None,
            assertion="not_mentioned",
            confidence=None,
            evidence=[],
            rationale="Symptom never discussed in transcript.",
        )
        assert resolution.final_score is None
        assert resolution.discussed is False

    def test_all_valid_items_accepted(self) -> None:
        """All PHQ8_ITEMS are accepted as valid item names."""
        for item in PHQ8_ITEMS:
            resolution = JudgeItemResolutionNA(
                item=item,
                discussed=True,
                final_score=1,
                assertion="present",
                confidence=0.8,
                evidence=["Client: test"],
                rationale=f"Test for {item}",
            )
            assert resolution.item == item


class TestJudgeItemResolutionNAInvalid:
    """Test invalid NA-aware judge schema constructions."""

    def test_present_requires_score_1_to_3(self) -> None:
        """present with score=0 raises ValidationError."""
        with pytest.raises(ValidationError, match="present requires final_score in"):
            JudgeItemResolutionNA(
                item="anhedonia",
                discussed=True,
                final_score=0,
                assertion="present",
                confidence=0.8,
                evidence=["Client: ..."],
                rationale="...",
            )

    def test_denied_requires_score_0(self) -> None:
        """denied with score!=0 raises ValidationError."""
        with pytest.raises(ValidationError, match="denied requires final_score=0"):
            JudgeItemResolutionNA(
                item="guilt",
                discussed=True,
                final_score=2,
                assertion="denied",
                confidence=0.8,
                evidence=["Client: ..."],
                rationale="...",
            )

    def test_possible_requires_score_1(self) -> None:
        """possible with score!=1 raises ValidationError."""
        with pytest.raises(ValidationError, match="possible requires final_score=1"):
            JudgeItemResolutionNA(
                item="sleep",
                discussed=True,
                final_score=2,
                assertion="possible",
                confidence=0.8,
                evidence=["Client: ..."],
                rationale="...",
            )

    def test_not_mentioned_requires_discussed_false(self) -> None:
        """not_mentioned with discussed=True raises ValidationError."""
        with pytest.raises(ValidationError, match="not_mentioned requires discussed=False"):
            JudgeItemResolutionNA(
                item="psychomotor",
                discussed=True,
                final_score=None,
                assertion="not_mentioned",
                confidence=None,
                evidence=[],
                rationale="...",
            )

    def test_not_mentioned_requires_score_none(self) -> None:
        """not_mentioned with numeric score raises ValidationError."""
        with pytest.raises(ValidationError, match="not_mentioned requires final_score=None"):
            JudgeItemResolutionNA(
                item="psychomotor",
                discussed=False,
                final_score=0,
                assertion="not_mentioned",
                confidence=None,
                evidence=[],
                rationale="...",
            )

    def test_not_mentioned_requires_confidence_none(self) -> None:
        """not_mentioned with numeric confidence raises ValidationError."""
        with pytest.raises(ValidationError, match="not_mentioned requires confidence=None"):
            JudgeItemResolutionNA(
                item="psychomotor",
                discussed=False,
                final_score=None,
                assertion="not_mentioned",
                confidence=0.5,
                evidence=[],
                rationale="...",
            )

    def test_not_mentioned_requires_empty_evidence(self) -> None:
        """not_mentioned must not include evidence."""
        with pytest.raises(ValidationError, match="not_mentioned requires evidence="):
            JudgeItemResolutionNA(
                item="psychomotor",
                discussed=False,
                final_score=None,
                assertion="not_mentioned",
                confidence=None,
                evidence=["Client: ..."],
                rationale="...",
            )

    def test_invalid_item_name(self) -> None:
        """Invalid item name raises ValidationError."""
        with pytest.raises(ValidationError, match="must be one of"):
            JudgeItemResolutionNA(
                item="invalid_symptom",
                discussed=True,
                final_score=1,
                assertion="present",
                confidence=0.8,
                evidence=["test"],
                rationale="...",
            )

    def test_present_requires_discussed_true(self) -> None:
        """present with discussed=False raises ValidationError."""
        with pytest.raises(ValidationError, match="present requires discussed=True"):
            JudgeItemResolutionNA(
                item="anhedonia",
                discussed=False,
                final_score=2,
                assertion="present",
                confidence=0.8,
                evidence=["test"],
                rationale="...",
            )

    def test_present_requires_confidence(self) -> None:
        """present with confidence=None raises ValidationError."""
        with pytest.raises(ValidationError, match="present requires confidence != None"):
            JudgeItemResolutionNA(
                item="anhedonia",
                discussed=True,
                final_score=2,
                assertion="present",
                confidence=None,
                evidence=["test"],
                rationale="...",
            )

    def test_present_requires_evidence(self) -> None:
        """present with empty evidence raises ValidationError."""
        with pytest.raises(ValidationError, match="present requires at least one evidence"):
            JudgeItemResolutionNA(
                item="anhedonia",
                discussed=True,
                final_score=2,
                assertion="present",
                confidence=0.8,
                evidence=[],
                rationale="...",
            )
