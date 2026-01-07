"""Schema parsing tests for V2 prompts (SPEC-14 Section 5.2)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from vibe_check.schemas.scoring import PHQ8Assessment


class TestV2SchemaParsing:
    """Test that V2 schema parses correctly with fixed outputs."""

    def test_parse_full_coverage_response(self) -> None:
        """Parse a complete V2-style response."""
        raw_json = {
            "anhedonia": {
                "discussed": True,
                "score": 2,
                "assertion": "present",
                "confidence": 0.85,
                "evidence": ["can't enjoy anything"],
            },
            "depressed_mood": {
                "discussed": True,
                "score": 3,
                "assertion": "present",
                "confidence": 0.90,
                "evidence": ["feeling hopeless"],
            },
            "sleep": {
                "discussed": True,
                "score": 1,
                "assertion": "present",
                "confidence": 0.75,
                "evidence": ["sometimes trouble sleeping"],
            },
            "fatigue": {
                "discussed": True,
                "score": 2,
                "assertion": "present",
                "confidence": 0.80,
                "evidence": ["exhausted"],
            },
            "appetite": {
                "discussed": True,
                "score": 0,
                "assertion": "denied",
                "confidence": 0.88,
                "evidence": ["eating fine"],
            },
            "guilt": {
                "discussed": True,
                "score": 1,
                "assertion": "present",
                "confidence": 0.70,
                "evidence": ["feel bad sometimes"],
            },
            "concentration": {
                "discussed": True,
                "score": 2,
                "assertion": "present",
                "confidence": 0.78,
                "evidence": ["can't focus"],
            },
            "psychomotor": {
                "discussed": True,
                "score": 0,
                "assertion": "denied",
                "confidence": 0.82,
                "evidence": ["moving normally"],
            },
            "total_score": 11,
            "discussed_count": 8,
            "mentions_self_harm": False,
            "self_harm_evidence": [],
        }
        assessment = PHQ8Assessment.model_validate(raw_json)
        assert assessment.total_score == 11
        assert assessment.discussed_count == 8

    def test_parse_partial_coverage_response(self) -> None:
        """Parse a response with NA items."""
        raw_json = {
            "anhedonia": {
                "discussed": True,
                "score": 2,
                "assertion": "present",
                "confidence": 0.85,
                "evidence": ["no interest"],
            },
            "depressed_mood": {
                "discussed": True,
                "score": 3,
                "assertion": "present",
                "confidence": 0.90,
                "evidence": ["hopeless"],
            },
            "sleep": {
                "discussed": False,
                "score": None,
                "assertion": "not_mentioned",
                "confidence": None,
                "evidence": [],
            },
            "fatigue": {
                "discussed": True,
                "score": 2,
                "assertion": "present",
                "confidence": 0.80,
                "evidence": ["tired"],
            },
            "appetite": {
                "discussed": False,
                "score": None,
                "assertion": "not_mentioned",
                "confidence": None,
                "evidence": [],
            },
            "guilt": {
                "discussed": False,
                "score": None,
                "assertion": "not_mentioned",
                "confidence": None,
                "evidence": [],
            },
            "concentration": {
                "discussed": True,
                "score": 1,
                "assertion": "possible",
                "confidence": 0.55,
                "evidence": ["maybe trouble focusing"],
            },
            "psychomotor": {
                "discussed": False,
                "score": None,
                "assertion": "not_mentioned",
                "confidence": None,
                "evidence": [],
            },
            "total_score": 8,  # 2+3+2+1
            "discussed_count": 4,
            "mentions_self_harm": False,
            "self_harm_evidence": [],
        }
        assessment = PHQ8Assessment.model_validate(raw_json)
        assert assessment.total_score == 8
        assert assessment.discussed_count == 4
        assert assessment.sleep.score is None
        assert assessment.sleep.assertion == "not_mentioned"

    def test_parse_all_na_response(self) -> None:
        """Parse a response where nothing was discussed."""
        raw_json = {
            "anhedonia": {
                "discussed": False,
                "score": None,
                "assertion": "not_mentioned",
                "confidence": None,
                "evidence": [],
            },
            "depressed_mood": {
                "discussed": False,
                "score": None,
                "assertion": "not_mentioned",
                "confidence": None,
                "evidence": [],
            },
            "sleep": {
                "discussed": False,
                "score": None,
                "assertion": "not_mentioned",
                "confidence": None,
                "evidence": [],
            },
            "fatigue": {
                "discussed": False,
                "score": None,
                "assertion": "not_mentioned",
                "confidence": None,
                "evidence": [],
            },
            "appetite": {
                "discussed": False,
                "score": None,
                "assertion": "not_mentioned",
                "confidence": None,
                "evidence": [],
            },
            "guilt": {
                "discussed": False,
                "score": None,
                "assertion": "not_mentioned",
                "confidence": None,
                "evidence": [],
            },
            "concentration": {
                "discussed": False,
                "score": None,
                "assertion": "not_mentioned",
                "confidence": None,
                "evidence": [],
            },
            "psychomotor": {
                "discussed": False,
                "score": None,
                "assertion": "not_mentioned",
                "confidence": None,
                "evidence": [],
            },
            "total_score": 0,
            "discussed_count": 0,
            "mentions_self_harm": False,
            "self_harm_evidence": [],
        }
        assessment = PHQ8Assessment.model_validate(raw_json)
        assert assessment.total_score == 0
        assert assessment.discussed_count == 0


class TestV2SchemaRejection:
    """Test that invalid V2 responses are rejected."""

    def _valid_assessment_json(self) -> dict:  # type: ignore[type-arg]
        """Return a fully-valid PHQ8Assessment JSON payload (SPEC-13)."""
        item = {
            "discussed": True,
            "score": 1,
            "assertion": "present",
            "confidence": 0.8,
            "evidence": ["Client: ..."],
        }
        return {
            "anhedonia": dict(item),
            "depressed_mood": dict(item),
            "sleep": dict(item),
            "fatigue": dict(item),
            "appetite": dict(item),
            "guilt": dict(item),
            "concentration": dict(item),
            "psychomotor": dict(item),
            "total_score": 8,
            "discussed_count": 8,
            "mentions_self_harm": False,
            "self_harm_evidence": [],
        }

    def test_reject_score_0_with_present_assertion(self) -> None:
        """present assertion cannot have score=0."""
        raw_json = self._valid_assessment_json()
        raw_json["anhedonia"]["score"] = 0
        with pytest.raises(ValidationError, match="present requires score in"):
            PHQ8Assessment.model_validate(raw_json)

    def test_reject_score_2_with_not_mentioned(self) -> None:
        """not_mentioned must have score=None."""
        raw_json = self._valid_assessment_json()
        raw_json["anhedonia"] = {
            "discussed": False,
            "score": 2,  # INVALID: must be None
            "assertion": "not_mentioned",
            "confidence": None,
            "evidence": [],
        }
        with pytest.raises(ValidationError, match="not_mentioned requires score=None"):
            PHQ8Assessment.model_validate(raw_json)

    def test_reject_discussed_true_with_not_mentioned(self) -> None:
        """not_mentioned requires discussed=False."""
        raw_json = self._valid_assessment_json()
        raw_json["anhedonia"] = {
            "discussed": True,  # INVALID: must be False
            "score": None,
            "assertion": "not_mentioned",
            "confidence": None,
            "evidence": [],
        }
        with pytest.raises(ValidationError, match="not_mentioned requires discussed=False"):
            PHQ8Assessment.model_validate(raw_json)
