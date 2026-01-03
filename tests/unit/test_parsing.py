from __future__ import annotations

import json

import pytest

from vibe_check.scoring.parsing import ParseError, parse_phq8_report


def test_parse_canonicalizes_total_score_when_missing() -> None:
    raw = {
        "anhedonia": {"score": 1, "confidence": 0.9, "evidence": ["x"]},
        "depressed_mood": {"score": 1, "confidence": 0.9, "evidence": ["x"]},
        "sleep": {"score": 1, "confidence": 0.9, "evidence": ["x"]},
        "fatigue": {"score": 1, "confidence": 0.9, "evidence": ["x"]},
        "appetite": {"score": 1, "confidence": 0.9, "evidence": ["x"]},
        "guilt": {"score": 1, "confidence": 0.9, "evidence": ["x"]},
        "concentration": {"score": 1, "confidence": 0.9, "evidence": ["x"]},
        "psychomotor": {"score": 1, "confidence": 0.9, "evidence": ["x"]},
        "mentions_self_harm": False,
        "self_harm_evidence": [],
    }

    report = parse_phq8_report(raw, model_id="fake", run_number=1)
    assert report.total_score == 8


def test_parse_fixes_incorrect_total_score() -> None:
    raw = {
        "anhedonia": {"score": 0, "confidence": 0.9, "evidence": ["x"]},
        "depressed_mood": {"score": 0, "confidence": 0.9, "evidence": ["x"]},
        "sleep": {"score": 0, "confidence": 0.9, "evidence": ["x"]},
        "fatigue": {"score": 0, "confidence": 0.9, "evidence": ["x"]},
        "appetite": {"score": 0, "confidence": 0.9, "evidence": ["x"]},
        "guilt": {"score": 0, "confidence": 0.9, "evidence": ["x"]},
        "concentration": {"score": 0, "confidence": 0.9, "evidence": ["x"]},
        "psychomotor": {"score": 0, "confidence": 0.9, "evidence": ["x"]},
        "total_score": 24,
        "mentions_self_harm": False,
        "self_harm_evidence": [],
    }

    report = parse_phq8_report(raw, model_id="fake", run_number=1)
    assert report.total_score == 0


def test_parse_handles_wrapped_json() -> None:
    payload = {
        "anhedonia": {"score": 1, "confidence": 0.9, "evidence": ["x"]},
        "depressed_mood": {"score": 1, "confidence": 0.9, "evidence": ["x"]},
        "sleep": {"score": 1, "confidence": 0.9, "evidence": ["x"]},
        "fatigue": {"score": 1, "confidence": 0.9, "evidence": ["x"]},
        "appetite": {"score": 1, "confidence": 0.9, "evidence": ["x"]},
        "guilt": {"score": 1, "confidence": 0.9, "evidence": ["x"]},
        "concentration": {"score": 1, "confidence": 0.9, "evidence": ["x"]},
        "psychomotor": {"score": 1, "confidence": 0.9, "evidence": ["x"]},
        "mentions_self_harm": False,
        "self_harm_evidence": [],
    }
    wrapped = f"Here you go:\\n{json.dumps(payload)}\\nThanks!"
    report = parse_phq8_report(wrapped, model_id="fake", run_number=1)
    assert report.total_score == 8


def test_parse_raises_on_missing_item() -> None:
    raw = {
        "anhedonia": {"score": 1, "confidence": 0.9, "evidence": ["x"]},
        "depressed_mood": {"score": 1, "confidence": 0.9, "evidence": ["x"]},
        "sleep": {"score": 1, "confidence": 0.9, "evidence": ["x"]},
        "fatigue": {"score": 1, "confidence": 0.9, "evidence": ["x"]},
        "appetite": {"score": 1, "confidence": 0.9, "evidence": ["x"]},
        "guilt": {"score": 1, "confidence": 0.9, "evidence": ["x"]},
        "concentration": {"score": 1, "confidence": 0.9, "evidence": ["x"]},
        # psychomotor missing
        "mentions_self_harm": False,
        "self_harm_evidence": [],
    }

    with pytest.raises(ParseError, match="Missing PHQ-8 items"):
        parse_phq8_report(raw, model_id="fake", run_number=1)
