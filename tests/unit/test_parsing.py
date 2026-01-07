"""Tests for parsing/canonicalization of juror outputs into PHQ-8 schemas."""

from __future__ import annotations

from tests.fixtures.sample_votes import create_mock_report

from vibe_check.schemas.scoring import PHQ8Assessment, PHQ8Report


def test_phq8assessment_canonicalizes_total_score_from_items() -> None:
    report = create_mock_report(0)
    data = report.model_dump(exclude={"model_id", "run_number", "usage", "scored_at"})
    data["total_score"] = 0

    assessment = PHQ8Assessment(**data)
    expected_total = sum(score or 0 for score in assessment.item_scores.values())
    assert assessment.total_score == expected_total


def test_phq8report_canonicalizes_total_score_from_items() -> None:
    base = create_mock_report(0).model_dump()
    base["total_score"] = 0

    report = PHQ8Report(**base)
    expected_total = sum(score or 0 for score in report.item_scores.values())
    assert report.total_score == expected_total


def test_phq8assessment_canonicalizes_missing_total_score() -> None:
    report = create_mock_report(0)
    data = report.model_dump(exclude={"model_id", "run_number", "usage", "scored_at"})
    data.pop("total_score", None)

    assessment = PHQ8Assessment(**data)
    expected_total = sum(score or 0 for score in assessment.item_scores.values())
    assert assessment.total_score == expected_total
