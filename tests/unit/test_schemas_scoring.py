"""Tests for juror scoring schemas (evidence + usage constraints)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from tests.fixtures.sample_votes import create_mock_report

from vibe_check.schemas.scoring import PHQ8ItemScore, PHQ8Report


def test_item_evidence_enforces_word_limit() -> None:
    long_snippet = "word " * 51
    with pytest.raises(ValidationError):
        PHQ8ItemScore(score=1, confidence=0.5, evidence=[long_snippet])


def test_item_evidence_enforces_char_limit() -> None:
    long_snippet = "x" * 401
    with pytest.raises(ValidationError):
        PHQ8ItemScore(score=1, confidence=0.5, evidence=[long_snippet])


def test_self_harm_evidence_enforces_limits() -> None:
    base = create_mock_report(0, self_harm=True).model_dump()
    base["self_harm_evidence"] = ["word " * 51]
    with pytest.raises(ValidationError):
        PHQ8Report(**base)


def test_usage_is_optional_and_validates() -> None:
    base = create_mock_report(0).model_dump()
    base["usage"] = {
        "input_tokens": 10,
        "output_tokens": 20,
        "reasoning_tokens": 5,
        "total_tokens": 35,
    }
    report = PHQ8Report(**base)
    assert report.usage is not None
    assert report.usage.total_tokens == 35
