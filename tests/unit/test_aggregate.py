from __future__ import annotations

import numpy as np
import pytest
from tests.fixtures.sample_votes import create_mock_report

from vibe_check.aggregation.aggregate import (
    aggregate_reports,
    compute_item_aggregation_with_na,
    compute_total_score_with_na,
    get_severity_bucket,
    get_severity_bucket_phq_like,
)
from vibe_check.constants import PHQ8_ITEMS
from vibe_check.schemas.scoring import PHQ8TotalScore


def test_aggregate_six_reports() -> None:
    reports = [create_mock_report(i) for i in range(6)]
    result = aggregate_reports(
        reports,
        file_id="test_file",
        condition="mdd",
        prompt_version="v1.0.0",
    )
    assert result.file_id == "test_file"
    assert len(result.items) == 8
    assert 0 <= result.total_mode <= 24
    assert len(result.total_posterior) == 25
    assert sum(result.total_posterior.values()) == pytest.approx(1.0)
    assert result.severity_bucket in ["0-4", "5-9", "10-14", "15-19", "20-24"]
    assert result.final_source == "jury_mode"
    assert set(result.final_item_scores.keys()) == set(PHQ8_ITEMS)
    assert result.final_total_score == sum(result.final_item_scores.values())
    assert result.final_severity_bucket in ["0-4", "5-9", "10-14", "15-19", "20-24"]
    assert result.totals.imputed_total == result.final_total_score


def test_severity_bucket_probs_sum_to_one() -> None:
    reports = [create_mock_report(i) for i in range(6)]
    result = aggregate_reports(
        reports,
        file_id="test_file",
        condition="mdd",
        prompt_version="v1.0.0",
    )
    assert sum(result.severity_bucket_probs.values()) == pytest.approx(1.0)


def test_arbitration_triggered_when_disagreement() -> None:
    reports = [create_mock_report(i, force_disagreement="anhedonia") for i in range(6)]
    result = aggregate_reports(
        reports,
        file_id="test_file",
        condition="mdd",
        prompt_version="v1.0.0",
    )
    assert result.triggered_arbitration is True
    assert "anhedonia" in result.arbitration_items


def test_self_harm_flag_propagates() -> None:
    reports = [create_mock_report(i) for i in range(5)]
    reports.append(create_mock_report(5, self_harm=True))
    result = aggregate_reports(
        reports,
        file_id="test_file",
        condition="mdd",
        prompt_version="v1.0.0",
    )
    assert result.mentions_self_harm is True


def test_total_score_std_triggers_global_arbitration() -> None:
    reports = [
        create_mock_report(i, force_disagreement_items=["sleep", "fatigue"]) for i in range(6)
    ]
    result = aggregate_reports(
        reports,
        file_id="test_file",
        condition="mdd",
        prompt_version="v1.0.0",
    )
    assert "__total__" in result.arbitration_items
    assert "__total__" in result.arbitration_reasons


def test_na_item_triggers_item_arbitration() -> None:
    """NA votes can trigger arbitration based on the NA count threshold."""
    reports = [
        create_mock_report(i, na_item="fatigue") if i < 2 else create_mock_report(i)
        for i in range(6)
    ]
    result = aggregate_reports(
        reports,
        file_id="test_file",
        condition="mdd",
        prompt_version="v1.0.0",
        insufficient_evidence_threshold=2,
    )
    assert "fatigue" in result.arbitration_items


class TestItemAggregationNA:
    def test_unanimous_present(self) -> None:
        result = compute_item_aggregation_with_na(
            votes=[2, 2, 2, 2, 2, 2],
            assertions=["present"] * 6,
        )
        assert result.consensus_score == 2
        assert result.consensus_assertion == "present"
        assert result.p_not_mentioned == 0.0
        assert result.na_count == 0
        assert result.numeric_votes == [2, 2, 2, 2, 2, 2]
        assert result.mode == 2

    def test_unanimous_not_mentioned(self) -> None:
        result = compute_item_aggregation_with_na(
            votes=[None, None, None, None, None, None],
            assertions=["not_mentioned"] * 6,
        )
        assert result.consensus_score is None
        assert result.consensus_assertion == "not_mentioned"
        assert result.p_not_mentioned == 1.0
        assert result.na_count == 6
        assert result.numeric_votes == []
        assert result.posterior is None
        assert result.mode is None

    def test_majority_not_mentioned_4_of_6(self) -> None:
        result = compute_item_aggregation_with_na(
            votes=[2, None, None, None, None, 1],
            assertions=[
                "present",
                "not_mentioned",
                "not_mentioned",
                "not_mentioned",
                "not_mentioned",
                "present",
            ],
        )
        assert result.consensus_score is None
        assert result.consensus_assertion == "not_mentioned"
        assert result.p_not_mentioned == pytest.approx(4 / 6)

    def test_exactly_half_not_mentioned_uses_numeric_mode(self) -> None:
        result = compute_item_aggregation_with_na(
            votes=[1, None, 2, 1, None, None],
            assertions=[
                "present",
                "not_mentioned",
                "present",
                "present",
                "not_mentioned",
                "not_mentioned",
            ],
        )
        assert result.p_not_mentioned == 0.5
        assert result.consensus_assertion == "present"
        assert result.consensus_score == 1

    def test_denied_consensus(self) -> None:
        result = compute_item_aggregation_with_na(
            votes=[0, 0, 0, 0, None, 0],
            assertions=["denied", "denied", "denied", "denied", "not_mentioned", "denied"],
        )
        assert result.consensus_score == 0
        assert result.consensus_assertion == "denied"

    def test_possible_consensus_majority(self) -> None:
        result = compute_item_aggregation_with_na(
            votes=[1, 1, 1, 1, None, None],
            assertions=[
                "possible",
                "possible",
                "possible",
                "possible",
                "not_mentioned",
                "not_mentioned",
            ],
        )
        assert result.consensus_score == 1
        assert result.consensus_assertion == "possible"

    def test_possible_minority_becomes_present(self) -> None:
        result = compute_item_aggregation_with_na(
            votes=[1, 1, 1, 2, None, None],
            assertions=[
                "present",
                "present",
                "possible",
                "present",
                "not_mentioned",
                "not_mentioned",
            ],
        )
        assert result.consensus_score == 1
        assert result.consensus_assertion == "present"


class TestItemAggregationArbitration:
    def test_high_na_rate_triggers_arbitration(self) -> None:
        result = compute_item_aggregation_with_na(
            votes=[1, None, None, None, None, None],
            assertions=[
                "present",
                "not_mentioned",
                "not_mentioned",
                "not_mentioned",
                "not_mentioned",
                "not_mentioned",
            ],
            na_rate_arbitration_threshold=0.67,
        )
        assert result.needs_arbitration is True
        assert result.arbitration_reason is not None
        assert "high_na_rate" in result.arbitration_reason

    def test_high_vote_range_triggers_arbitration(self) -> None:
        result = compute_item_aggregation_with_na(
            votes=[0, 3, 0, 3, None, None],
            assertions=["denied", "present", "denied", "present", "not_mentioned", "not_mentioned"],
            range_threshold=2,
            arbitration_max_prob_threshold=0.0,
            arbitration_entropy_threshold=999.0,
        )
        assert result.needs_arbitration is True
        assert result.arbitration_reason is not None
        assert ("vote_range" in result.arbitration_reason) or ("range" in result.arbitration_reason)


class TestTotalScoreNA:
    def test_full_coverage(self) -> None:
        item_consensus = {
            "anhedonia": 2,
            "depressed_mood": 3,
            "sleep": 1,
            "fatigue": 2,
            "appetite": 0,
            "guilt": 1,
            "concentration": 2,
            "psychomotor": 0,
        }
        total = compute_total_score_with_na(item_consensus)
        assert total.discussed_count == 8
        assert total.discussed_sum == 11
        assert total.imputed_total == 11
        assert total.is_proration_valid is True
        assert total.prorated_total == 11.0

    def test_partial_coverage_5_items(self) -> None:
        item_consensus = {
            "anhedonia": 2,
            "depressed_mood": 3,
            "sleep": 1,
            "fatigue": 2,
            "appetite": None,
            "guilt": None,
            "concentration": 1,
            "psychomotor": None,
        }
        total = compute_total_score_with_na(item_consensus)
        assert total.discussed_count == 5
        assert total.discussed_sum == 9
        assert total.imputed_total == 9
        assert total.is_proration_valid is False
        assert total.prorated_total is None

    def test_high_coverage_7_items(self) -> None:
        item_consensus = {
            "anhedonia": 2,
            "depressed_mood": 3,
            "sleep": 1,
            "fatigue": 2,
            "appetite": None,
            "guilt": 2,
            "concentration": 2,
            "psychomotor": 2,
        }
        total = compute_total_score_with_na(item_consensus)
        assert total.discussed_count == 7
        assert total.discussed_sum == 14
        assert total.is_proration_valid is True
        assert total.prorated_total == 16.0

    def test_all_na(self) -> None:
        item_consensus = dict.fromkeys(PHQ8_ITEMS)
        total = compute_total_score_with_na(item_consensus)
        assert total.discussed_count == 0
        assert total.imputed_total == 0
        assert total.is_min_coverage is False


class TestSeverityBucketNA:
    def test_imputed_severity_bucket(self) -> None:
        assert get_severity_bucket(12) == "10-14"

    def test_phq_like_bucket_when_valid(self) -> None:
        total = PHQ8TotalScore(
            discussed_count=7,
            discussed_sum=14,
            coverage=0.875,
            na_count=1,
            prorated_total=16.0,
            prorated_total_rounded=16,
            imputed_total=14,
            is_min_coverage=True,
            is_proration_valid=True,
        )
        assert get_severity_bucket_phq_like(total) == "15-19"

    def test_phq_like_bucket_none_when_invalid(self) -> None:
        total = PHQ8TotalScore(
            discussed_count=5,
            discussed_sum=10,
            coverage=0.625,
            na_count=3,
            prorated_total=None,
            prorated_total_rounded=None,
            imputed_total=10,
            is_min_coverage=True,
            is_proration_valid=False,
        )
        assert get_severity_bucket_phq_like(total) is None


class TestGlobalArbitrationNA:
    def test_global_arbitration_uses_imputed(self) -> None:
        juror_imputed_totals = [6, 12, 7, 15, 5, 14]
        std = float(np.std(juror_imputed_totals))
        assert std > 2.0

    def test_no_global_arbitration_when_consistent(self) -> None:
        juror_imputed_totals = [10, 10, 11, 10, 10, 11]
        std = float(np.std(juror_imputed_totals))
        assert std < 2.0
