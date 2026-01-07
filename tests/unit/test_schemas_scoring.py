"""Tests for juror scoring schemas (SPEC-13 NA-aware schema)."""

from __future__ import annotations

from typing import Literal

import pytest
from pydantic import ValidationError

from vibe_check.schemas.scoring import (
    Assertion,
    PHQ8Assessment,
    PHQ8ItemScore,
    PHQ8Report,
    PHQ8TotalScore,
    TokenUsage,
)

# =============================================================================
# Section 4.1: PHQ8ItemScore Valid Constructions
# =============================================================================


class TestPHQ8ItemScoreValid:
    """Valid construction tests."""

    def test_present_score_2(self) -> None:
        item = PHQ8ItemScore(
            discussed=True,
            score=2,
            assertion="present",
            confidence=0.85,
            evidence=["I've been really tired lately"],
        )
        assert item.discussed is True
        assert item.score == 2
        assert item.assertion == "present"
        assert item.confidence == 0.85

    def test_present_score_1(self) -> None:
        item = PHQ8ItemScore(
            discussed=True,
            score=1,
            assertion="present",
            confidence=0.70,
            evidence=["Sometimes I feel down"],
        )
        assert item.score == 1

    def test_present_score_3(self) -> None:
        item = PHQ8ItemScore(
            discussed=True,
            score=3,
            assertion="present",
            confidence=0.95,
            evidence=["Every single day I can't sleep"],
        )
        assert item.score == 3

    def test_denied(self) -> None:
        item = PHQ8ItemScore(
            discussed=True,
            score=0,
            assertion="denied",
            confidence=0.92,
            evidence=["My sleep has been fine"],
        )
        assert item.score == 0
        assert item.assertion == "denied"

    def test_possible(self) -> None:
        item = PHQ8ItemScore(
            discussed=True,
            score=1,
            assertion="possible",
            confidence=0.55,
            evidence=["Maybe I've been a bit tired"],
        )
        assert item.score == 1
        assert item.assertion == "possible"

    def test_not_mentioned(self) -> None:
        item = PHQ8ItemScore(
            discussed=False,
            score=None,
            assertion="not_mentioned",
            confidence=None,
            evidence=[],
        )
        assert item.discussed is False
        assert item.score is None
        assert item.assertion == "not_mentioned"
        assert item.confidence is None
        assert item.evidence == []

    def test_confidence_boundary_zero(self) -> None:
        item = PHQ8ItemScore(
            discussed=True,
            score=0,
            assertion="denied",
            confidence=0.0,
            evidence=["no issues"],
        )
        assert item.confidence == 0.0

    def test_confidence_boundary_one(self) -> None:
        item = PHQ8ItemScore(
            discussed=True,
            score=3,
            assertion="present",
            confidence=1.0,
            evidence=["severe symptoms"],
        )
        assert item.confidence == 1.0

    def test_max_evidence_snippets(self) -> None:
        item = PHQ8ItemScore(
            discussed=True,
            score=2,
            assertion="present",
            confidence=0.8,
            evidence=["quote 1", "quote 2", "quote 3"],
        )
        assert len(item.evidence) == 3


# =============================================================================
# Section 4.2: PHQ8ItemScore Invalid Constructions (ValidationError)
# =============================================================================


class TestPHQ8ItemScoreInvalid:
    """Invalid construction tests - must raise ValidationError."""

    # --- Type strictness (avoid boolean coercion) ---

    def test_discussed_must_be_boolean(self) -> None:
        with pytest.raises(ValidationError, match="discussed must be a boolean"):
            PHQ8ItemScore(
                discussed="true",  # type: ignore[arg-type]
                score=2,
                assertion="present",
                confidence=0.80,
                evidence=["feeling down"],
            )

    def test_score_must_not_be_boolean(self) -> None:
        with pytest.raises(ValidationError, match="score must be an integer 0-3"):
            PHQ8ItemScore(
                discussed=True,
                score=True,  # type: ignore[arg-type]
                assertion="present",
                confidence=0.80,
                evidence=["feeling down"],
            )

    def test_confidence_must_not_be_boolean(self) -> None:
        with pytest.raises(ValidationError, match=r"confidence must be a number 0\.0-1\.0"):
            PHQ8ItemScore(
                discussed=True,
                score=2,
                assertion="present",
                confidence=True,
                evidence=["feeling down"],
            )

    # --- Assertion/score consistency ---

    def test_present_requires_score_1_2_3_not_0(self) -> None:
        with pytest.raises(ValidationError, match="present requires score in"):
            PHQ8ItemScore(
                discussed=True,
                score=0,
                assertion="present",
                confidence=0.80,
                evidence=["feeling down"],
            )

    def test_denied_requires_score_0(self) -> None:
        with pytest.raises(ValidationError, match="denied requires score=0"):
            PHQ8ItemScore(
                discussed=True,
                score=2,
                assertion="denied",
                confidence=0.90,
                evidence=["I'm sleeping fine"],
            )

    def test_possible_requires_score_1(self) -> None:
        with pytest.raises(ValidationError, match="possible requires score=1"):
            PHQ8ItemScore(
                discussed=True,
                score=2,
                assertion="possible",
                confidence=0.55,
                evidence=["maybe tired"],
            )

    def test_possible_requires_score_1_not_0(self) -> None:
        with pytest.raises(ValidationError, match="possible requires score=1"):
            PHQ8ItemScore(
                discussed=True,
                score=0,
                assertion="possible",
                confidence=0.55,
                evidence=["maybe not"],
            )

    def test_not_mentioned_requires_score_none(self) -> None:
        with pytest.raises(ValidationError, match="not_mentioned requires score=None"):
            PHQ8ItemScore(
                discussed=False,
                score=0,
                assertion="not_mentioned",
                confidence=None,
                evidence=[],
            )

    # --- Assertion/discussed consistency ---

    def test_not_mentioned_requires_discussed_false(self) -> None:
        with pytest.raises(ValidationError, match="not_mentioned requires discussed=False"):
            PHQ8ItemScore(
                discussed=True,
                score=None,
                assertion="not_mentioned",
                confidence=None,
                evidence=[],
            )

    def test_present_requires_discussed_true(self) -> None:
        with pytest.raises(ValidationError, match="present requires discussed=True"):
            PHQ8ItemScore(
                discussed=False,
                score=2,
                assertion="present",
                confidence=0.80,
                evidence=["feeling down"],
            )

    def test_denied_requires_discussed_true(self) -> None:
        with pytest.raises(ValidationError, match="denied requires discussed=True"):
            PHQ8ItemScore(
                discussed=False,
                score=0,
                assertion="denied",
                confidence=0.90,
                evidence=["I'm fine"],
            )

    # --- Assertion/confidence consistency ---

    def test_not_mentioned_requires_confidence_none(self) -> None:
        with pytest.raises(ValidationError, match="not_mentioned requires confidence=None"):
            PHQ8ItemScore(
                discussed=False,
                score=None,
                assertion="not_mentioned",
                confidence=0.50,
                evidence=[],
            )

    def test_present_requires_confidence(self) -> None:
        with pytest.raises(ValidationError, match="present requires confidence"):
            PHQ8ItemScore(
                discussed=True,
                score=2,
                assertion="present",
                confidence=None,
                evidence=["feeling down"],
            )

    def test_denied_requires_confidence(self) -> None:
        with pytest.raises(ValidationError, match="denied requires confidence"):
            PHQ8ItemScore(
                discussed=True,
                score=0,
                assertion="denied",
                confidence=None,
                evidence=["I'm fine"],
            )

    # --- Assertion/evidence consistency ---

    def test_not_mentioned_requires_empty_evidence(self) -> None:
        with pytest.raises(ValidationError, match="not_mentioned requires evidence="):
            PHQ8ItemScore(
                discussed=False,
                score=None,
                assertion="not_mentioned",
                confidence=None,
                evidence=["some quote"],
            )

    def test_present_requires_evidence(self) -> None:
        with pytest.raises(ValidationError, match="present requires at least one evidence"):
            PHQ8ItemScore(
                discussed=True,
                score=2,
                assertion="present",
                confidence=0.80,
                evidence=[],
            )

    def test_denied_requires_evidence(self) -> None:
        with pytest.raises(ValidationError, match="denied requires at least one evidence"):
            PHQ8ItemScore(
                discussed=True,
                score=0,
                assertion="denied",
                confidence=0.90,
                evidence=[],
            )

    def test_possible_requires_evidence(self) -> None:
        with pytest.raises(ValidationError, match="possible requires at least one evidence"):
            PHQ8ItemScore(
                discussed=True,
                score=1,
                assertion="possible",
                confidence=0.60,
                evidence=[],
            )

    # --- Evidence constraint tests ---

    def test_evidence_snippet_max_chars(self) -> None:
        long_snippet = "x" * 401  # Exceeds MAX_EVIDENCE_SNIPPET_CHARS (400)
        with pytest.raises(ValidationError, match="exceeds 400 chars"):
            PHQ8ItemScore(
                discussed=True,
                score=1,
                assertion="present",
                confidence=0.70,
                evidence=[long_snippet],
            )

    def test_evidence_snippet_max_words(self) -> None:
        many_words = " ".join(["word"] * 51)  # Exceeds MAX_EVIDENCE_SNIPPET_WORDS (50)
        with pytest.raises(ValidationError, match="exceeds 50 words"):
            PHQ8ItemScore(
                discussed=True,
                score=1,
                assertion="present",
                confidence=0.70,
                evidence=[many_words],
            )

    def test_evidence_snippet_whitespace_only(self) -> None:
        with pytest.raises(ValidationError, match="non-empty after stripping"):
            PHQ8ItemScore(
                discussed=True,
                score=1,
                assertion="present",
                confidence=0.70,
                evidence=["   \t\n  "],
            )

    def test_evidence_snippet_empty_string(self) -> None:
        with pytest.raises(ValidationError, match="non-empty after stripping"):
            PHQ8ItemScore(
                discussed=True,
                score=1,
                assertion="present",
                confidence=0.70,
                evidence=[""],
            )

    def test_evidence_exceeds_max_length(self) -> None:
        with pytest.raises(ValidationError, match="at most 3 items"):
            PHQ8ItemScore(
                discussed=True,
                score=2,
                assertion="present",
                confidence=0.80,
                evidence=["a", "b", "c", "d"],
            )

    # --- Confidence range tests ---

    def test_confidence_above_one(self) -> None:
        with pytest.raises(ValidationError, match="less than or equal to 1"):
            PHQ8ItemScore(
                discussed=True,
                score=1,
                assertion="present",
                confidence=1.1,
                evidence=["quote"],
            )

    def test_confidence_below_zero(self) -> None:
        with pytest.raises(ValidationError, match="greater than or equal to 0"):
            PHQ8ItemScore(
                discussed=True,
                score=1,
                assertion="present",
                confidence=-0.1,
                evidence=["quote"],
            )


# =============================================================================
# Section 5.3: PHQ8Assessment with NA items
# =============================================================================


class TestPHQ8AssessmentNA:
    """PHQ8Assessment tests with NA items."""

    def _make_item(self, score: int | None, assertion: Assertion) -> PHQ8ItemScore:
        if assertion == "not_mentioned":
            return PHQ8ItemScore(
                discussed=False,
                score=None,
                assertion="not_mentioned",
                confidence=None,
                evidence=[],
            )
        if assertion == "denied":
            return PHQ8ItemScore(
                discussed=True,
                score=0,
                assertion="denied",
                confidence=0.9,
                evidence=["I'm fine"],
            )
        return PHQ8ItemScore(
            discussed=True,
            score=score,  # type: ignore[arg-type]
            assertion=assertion,
            confidence=0.8,
            evidence=["quote"],
        )

    def test_all_items_discussed(self) -> None:
        assessment = PHQ8Assessment(
            anhedonia=self._make_item(2, "present"),
            depressed_mood=self._make_item(3, "present"),
            sleep=self._make_item(1, "present"),
            fatigue=self._make_item(2, "present"),
            appetite=self._make_item(0, "denied"),
            guilt=self._make_item(1, "present"),
            concentration=self._make_item(2, "present"),
            psychomotor=self._make_item(0, "denied"),
            total_score=11,
            discussed_count=8,
        )
        assert assessment.total_score == 11  # 2+3+1+2+0+1+2+0
        assert assessment.discussed_count == 8

    def test_with_na_items(self) -> None:
        assessment = PHQ8Assessment(
            anhedonia=self._make_item(2, "present"),
            depressed_mood=self._make_item(3, "present"),
            sleep=self._make_item(None, "not_mentioned"),
            fatigue=self._make_item(2, "present"),
            appetite=self._make_item(None, "not_mentioned"),
            guilt=self._make_item(None, "not_mentioned"),
            concentration=self._make_item(1, "possible"),
            psychomotor=self._make_item(None, "not_mentioned"),
            total_score=8,
            discussed_count=4,
        )
        # total_score = 2+3+0+2+0+0+1+0 = 8 (NA→0)
        assert assessment.total_score == 8
        assert assessment.discussed_count == 4

    def test_all_na(self) -> None:
        assessment = PHQ8Assessment(
            anhedonia=self._make_item(None, "not_mentioned"),
            depressed_mood=self._make_item(None, "not_mentioned"),
            sleep=self._make_item(None, "not_mentioned"),
            fatigue=self._make_item(None, "not_mentioned"),
            appetite=self._make_item(None, "not_mentioned"),
            guilt=self._make_item(None, "not_mentioned"),
            concentration=self._make_item(None, "not_mentioned"),
            psychomotor=self._make_item(None, "not_mentioned"),
            total_score=0,
            discussed_count=0,
        )
        assert assessment.total_score == 0
        assert assessment.discussed_count == 0

    def test_item_scores_property_returns_none_for_na(self) -> None:
        assessment = PHQ8Assessment(
            anhedonia=self._make_item(2, "present"),
            depressed_mood=self._make_item(None, "not_mentioned"),
            sleep=self._make_item(1, "present"),
            fatigue=self._make_item(None, "not_mentioned"),
            appetite=self._make_item(0, "denied"),
            guilt=self._make_item(None, "not_mentioned"),
            concentration=self._make_item(2, "present"),
            psychomotor=self._make_item(None, "not_mentioned"),
            total_score=5,
            discussed_count=4,
        )
        scores = assessment.item_scores
        assert scores["anhedonia"] == 2
        assert scores["depressed_mood"] is None
        assert scores["sleep"] == 1
        assert scores["fatigue"] is None
        assert scores["appetite"] == 0
        assert scores["guilt"] is None
        assert scores["concentration"] == 2
        assert scores["psychomotor"] is None


class TestPHQ8AssessmentInvalidTypes:
    def _valid_item_dict(
        self, *, score: int | None, discussed: bool, assertion: Assertion
    ) -> dict[str, object]:
        if assertion == "not_mentioned":
            return {
                "discussed": False,
                "score": None,
                "assertion": "not_mentioned",
                "confidence": None,
                "evidence": [],
            }
        return {
            "discussed": discussed,
            "score": score,
            "assertion": assertion,
            "confidence": 0.8,
            "evidence": ["quote"],
        }

    def test_model_validate_rejects_discussed_string(self) -> None:
        payload: dict[str, object] = {
            "anhedonia": {
                **self._valid_item_dict(score=1, discussed=True, assertion="present"),
                "discussed": "true",
            },
            "depressed_mood": self._valid_item_dict(score=1, discussed=True, assertion="present"),
            "sleep": self._valid_item_dict(score=1, discussed=True, assertion="present"),
            "fatigue": self._valid_item_dict(score=1, discussed=True, assertion="present"),
            "appetite": self._valid_item_dict(score=0, discussed=True, assertion="denied"),
            "guilt": self._valid_item_dict(score=1, discussed=True, assertion="present"),
            "concentration": self._valid_item_dict(score=1, discussed=True, assertion="present"),
            "psychomotor": self._valid_item_dict(score=0, discussed=True, assertion="denied"),
        }

        with pytest.raises(ValidationError, match="discussed must be a boolean"):
            PHQ8Assessment.model_validate(payload)


# =============================================================================
# Section 6.2: PHQ8TotalScore Tests
# =============================================================================


class TestPHQ8TotalScore:
    """PHQ8TotalScore tests."""

    def test_full_coverage(self) -> None:
        scores = {
            "anhedonia": 2,
            "depressed_mood": 3,
            "sleep": 1,
            "fatigue": 2,
            "appetite": 0,
            "guilt": 1,
            "concentration": 2,
            "psychomotor": 0,
        }
        total = PHQ8TotalScore.from_item_scores(scores)
        assert total.discussed_count == 8
        assert total.discussed_sum == 11
        assert total.coverage == 1.0
        assert total.na_count == 0
        assert total.imputed_total == 11
        assert total.prorated_total == 11.0
        assert total.prorated_total_rounded == 11
        assert total.is_min_coverage is True
        assert total.is_proration_valid is True

    def test_high_coverage_7_items(self) -> None:
        # 7 items, sum=14, one NA
        scores = {
            "anhedonia": 2,
            "depressed_mood": 3,
            "sleep": 1,
            "fatigue": 2,
            "appetite": None,
            "guilt": 2,
            "concentration": 2,
            "psychomotor": 2,
        }
        total = PHQ8TotalScore.from_item_scores(scores)
        assert total.discussed_count == 7
        assert total.discussed_sum == 14
        assert total.na_count == 1
        assert total.coverage == 0.875
        assert total.imputed_total == 14
        # prorated = (14/7) * 8 = 16.0
        assert total.prorated_total == 16.0
        assert total.prorated_total_rounded == 16
        assert total.is_proration_valid is True

    def test_proration_rounding_half_up(self) -> None:
        # 7 items, sum=13 → prorated = (13/7)*8 = 14.857... → 15
        scores = {
            "anhedonia": 2,
            "depressed_mood": 2,
            "sleep": 2,
            "fatigue": 2,
            "appetite": None,
            "guilt": 2,
            "concentration": 2,
            "psychomotor": 1,
        }
        total = PHQ8TotalScore.from_item_scores(scores)
        assert abs(total.prorated_total - 14.857142857142858) < 0.001  # type: ignore[operator]
        assert total.prorated_total_rounded == 15  # Round half up

    def test_low_coverage_6_items(self) -> None:
        # 6 items, proration NOT valid (< 7)
        scores = {
            "anhedonia": 2,
            "depressed_mood": 3,
            "sleep": None,
            "fatigue": None,
            "appetite": 1,
            "guilt": 2,
            "concentration": 2,
            "psychomotor": 1,
        }
        total = PHQ8TotalScore.from_item_scores(scores)
        assert total.discussed_count == 6
        assert total.na_count == 2
        assert total.is_min_coverage is True  # 6 >= 4
        assert total.is_proration_valid is False  # 6 < 7
        assert total.prorated_total is None
        assert total.prorated_total_rounded is None

    def test_below_min_coverage_3_items(self) -> None:
        scores = {
            "anhedonia": 2,
            "depressed_mood": 3,
            "sleep": None,
            "fatigue": None,
            "appetite": None,
            "guilt": None,
            "concentration": None,
            "psychomotor": 1,
        }
        total = PHQ8TotalScore.from_item_scores(scores)
        assert total.discussed_count == 3
        assert total.is_min_coverage is False  # 3 < 4
        assert total.is_proration_valid is False

    def test_all_na(self) -> None:
        scores = dict.fromkeys(
            [
                "anhedonia",
                "depressed_mood",
                "sleep",
                "fatigue",
                "appetite",
                "guilt",
                "concentration",
                "psychomotor",
            ]
        )
        total = PHQ8TotalScore.from_item_scores(scores)
        assert total.discussed_count == 0
        assert total.discussed_sum == 0
        assert total.imputed_total == 0
        assert total.is_min_coverage is False
        assert total.is_proration_valid is False

    def test_consistency_validator_catches_bad_na_count(self) -> None:
        with pytest.raises(ValidationError, match="na_count must equal"):
            PHQ8TotalScore(
                discussed_count=5,
                discussed_sum=10,
                coverage=0.625,
                na_count=2,  # Wrong! Should be 3
                imputed_total=10,
                is_min_coverage=True,
                is_proration_valid=False,
            )

    def test_consistency_validator_catches_bad_coverage(self) -> None:
        with pytest.raises(ValidationError, match="coverage must equal"):
            PHQ8TotalScore(
                discussed_count=5,
                discussed_sum=10,
                coverage=0.5,  # Wrong! Should be 0.625
                na_count=3,
                imputed_total=10,
                is_min_coverage=True,
                is_proration_valid=False,
            )

    def test_consistency_validator_catches_proration_when_invalid(self) -> None:
        with pytest.raises(ValidationError, match="proration fields must be None"):
            PHQ8TotalScore(
                discussed_count=5,
                discussed_sum=10,
                coverage=0.625,
                na_count=3,
                prorated_total=16.0,
                prorated_total_rounded=16,  # Invalid!
                imputed_total=10,
                is_min_coverage=True,
                is_proration_valid=False,
            )

    def test_from_item_scores_requires_8_items(self) -> None:
        with pytest.raises(ValueError, match="must have exactly 8 items"):
            PHQ8TotalScore.from_item_scores({"anhedonia": 2, "depressed_mood": 1})


# =============================================================================
# PHQ8Report Tests (inherits PHQ8Assessment)
# =============================================================================


class TestPHQ8Report:
    """PHQ8Report with NA-aware schema."""

    def _make_item(self, score: Literal[0, 1, 2, 3] | None, assertion: Assertion) -> PHQ8ItemScore:
        if assertion == "not_mentioned":
            return PHQ8ItemScore(
                discussed=False,
                score=None,
                assertion="not_mentioned",
                confidence=None,
                evidence=[],
            )
        if assertion == "denied":
            return PHQ8ItemScore(
                discussed=True,
                score=0,
                assertion="denied",
                confidence=0.9,
                evidence=["I'm fine"],
            )
        return PHQ8ItemScore(
            discussed=True,
            score=score,  # validated by PHQ8ItemScore for assertion semantics
            assertion=assertion,
            confidence=0.8,
            evidence=["quote"],
        )

    def test_report_with_na_items(self) -> None:
        report = PHQ8Report(
            model_id="gpt-5.2",
            run_number=1,
            anhedonia=self._make_item(2, "present"),
            depressed_mood=self._make_item(3, "present"),
            sleep=self._make_item(None, "not_mentioned"),
            fatigue=self._make_item(2, "present"),
            appetite=self._make_item(None, "not_mentioned"),
            guilt=self._make_item(1, "present"),
            concentration=self._make_item(None, "not_mentioned"),
            psychomotor=self._make_item(0, "denied"),
            total_score=8,
            discussed_count=5,
        )
        assert report.total_score == 8  # 2+3+0+2+0+1+0+0
        assert report.discussed_count == 5
        assert report.model_id == "gpt-5.2"
        assert report.run_number == 1

    def test_self_harm_evidence_enforces_limits(self) -> None:
        with pytest.raises(ValidationError):
            PHQ8Report(
                model_id="gpt-5.2",
                run_number=1,
                anhedonia=self._make_item(0, "denied"),
                depressed_mood=self._make_item(0, "denied"),
                sleep=self._make_item(0, "denied"),
                fatigue=self._make_item(0, "denied"),
                appetite=self._make_item(0, "denied"),
                guilt=self._make_item(0, "denied"),
                concentration=self._make_item(0, "denied"),
                psychomotor=self._make_item(0, "denied"),
                total_score=0,
                discussed_count=8,
                mentions_self_harm=True,
                self_harm_evidence=["word " * 51],
            )

    def test_usage_is_optional_and_validates(self) -> None:
        report = PHQ8Report(
            model_id="gpt-5.2",
            run_number=1,
            anhedonia=self._make_item(2, "present"),
            depressed_mood=self._make_item(1, "present"),
            sleep=self._make_item(2, "present"),
            fatigue=self._make_item(2, "present"),
            appetite=self._make_item(1, "present"),
            guilt=self._make_item(1, "present"),
            concentration=self._make_item(2, "present"),
            psychomotor=self._make_item(1, "present"),
            total_score=12,
            discussed_count=8,
            usage=TokenUsage(
                input_tokens=10, output_tokens=20, reasoning_tokens=5, total_tokens=35
            ),
        )
        assert report.usage is not None
        assert report.usage.total_tokens == 35


# =============================================================================
# Assertion Type Alias
# =============================================================================


class TestAssertionType:
    """Test the Assertion type alias."""

    def test_assertion_literal_values(self) -> None:
        # This just verifies the type exists and matches expected values
        valid_assertions: list[Assertion] = ["present", "denied", "possible", "not_mentioned"]
        for assertion in valid_assertions:
            item = PHQ8ItemScore(
                discussed=assertion != "not_mentioned",
                score=1
                if assertion in ("present", "possible")
                else (0 if assertion == "denied" else None),
                assertion=assertion,
                confidence=0.8 if assertion != "not_mentioned" else None,
                evidence=["test"] if assertion != "not_mentioned" else [],
            )
            assert item.assertion == assertion
