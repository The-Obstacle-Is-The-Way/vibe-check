from __future__ import annotations

import pytest
from tests.fixtures.sample_votes import create_mock_report

from vibe_check.aggregation.aggregate import aggregate_reports, aggregate_votes


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
    assert set(result.final_item_scores.keys()) == {
        "anhedonia",
        "depressed_mood",
        "sleep",
        "fatigue",
        "appetite",
        "guilt",
        "concentration",
        "psychomotor",
    }
    assert result.final_total_score == sum(result.final_item_scores.values())
    assert result.final_severity_bucket in ["0-4", "5-9", "10-14", "15-19", "20-24"]


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


def test_insufficient_evidence_triggers_item_arbitration() -> None:
    reports = [
        create_mock_report(i, insufficient_evidence_item="fatigue")
        if i < 2
        else create_mock_report(i)
        for i in range(6)
    ]
    result = aggregate_reports(
        reports,
        file_id="test_file",
        condition="mdd",
        prompt_version="v1.0.0",
    )
    assert "fatigue" in result.arbitration_items


def test_aggregate_votes_raises_on_missing_items() -> None:
    votes = {
        "depressed_mood": [1, 1, 1, 1, 1, 1],
        "sleep": [2, 2, 2, 2, 2, 2],
        "fatigue": [2, 2, 2, 2, 2, 2],
        "appetite": [1, 1, 1, 1, 1, 1],
        "guilt": [1, 1, 1, 1, 1, 1],
        "concentration": [2, 2, 2, 2, 2, 2],
        "psychomotor": [1, 1, 1, 1, 1, 1],
    }
    with pytest.raises(ValueError, match="Missing PHQ-8 items"):
        aggregate_votes(votes)


def test_aggregate_reports_raises_on_empty_reports() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        aggregate_reports([], file_id="x", condition="mdd", prompt_version="v1")
