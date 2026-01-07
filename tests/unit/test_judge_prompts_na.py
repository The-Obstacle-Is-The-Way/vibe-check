"""Tests for NA-aware judge prompts (SPEC-17)."""

from __future__ import annotations

import pytest

from vibe_check.constants import PHQ8_ITEMS, PHQ8_RUBRIC
from vibe_check.judge.prompting import build_judge_item_prompt_v2, build_judge_system_prompt_v2


class TestBuildJudgeSystemPromptV2:
    """Test NA-aware judge system prompt builder."""

    def test_contains_version_string(self) -> None:
        """System prompt includes version string."""
        prompt = build_judge_system_prompt_v2("v2.0.0-clinical")
        assert "v2.0.0-clinical" in prompt

    def test_contains_all_phq8_items(self) -> None:
        """System prompt includes all PHQ-8 item definitions."""
        prompt = build_judge_system_prompt_v2("v2.0.0")
        for item in PHQ8_ITEMS:
            assert item in prompt
            assert PHQ8_RUBRIC[item] in prompt

    def test_contains_assertion_guidance(self) -> None:
        """System prompt includes assertion type guidance."""
        prompt = build_judge_system_prompt_v2("v2.0.0")
        assert "present" in prompt
        assert "denied" in prompt
        assert "possible" in prompt
        assert "not_mentioned" in prompt

    def test_contains_na_handling_guidance(self) -> None:
        """System prompt includes NA vote handling guidance."""
        prompt = build_judge_system_prompt_v2("v2.0.0")
        assert "MAJORITY" in prompt or "majority" in prompt
        assert "MINORITY" in prompt or "minority" in prompt

    def test_contains_json_skeleton(self) -> None:
        """System prompt includes JSON response skeleton."""
        prompt = build_judge_system_prompt_v2("v2.0.0")
        assert '"discussed"' in prompt
        assert '"assertion"' in prompt
        assert '"evidence"' in prompt

    def test_no_frequency_anchors(self) -> None:
        """v2 prompt avoids frequency-based scoring language."""
        prompt = build_judge_system_prompt_v2("v2.0.0")
        # Should NOT contain v1 frequency anchors
        assert "Several days" not in prompt
        assert "More than half the days" not in prompt
        assert "Nearly every day" not in prompt

    def test_includes_clinical_timeframe(self) -> None:
        """v2 prompt uses clinical timeframe."""
        prompt = build_judge_system_prompt_v2("v2.0.0")
        assert "~last 2 weeks" in prompt

    def test_includes_evidence_constraints(self) -> None:
        """v2 prompt includes evidence constraints."""
        prompt = build_judge_system_prompt_v2("v2.0.0")
        assert "50" in prompt  # words
        assert "400" in prompt  # characters


class TestBuildJudgeItemPromptV2:
    """Test NA-aware judge item prompt builder."""

    def test_valid_item_accepted(self) -> None:
        """Valid PHQ-8 item generates prompt."""
        prompt = build_judge_item_prompt_v2(
            scoring_text="Test transcript",
            item="anhedonia",
            juror_votes=[2, 2, 1, None, 2, 1],
            juror_assertions=[
                "present",
                "present",
                "present",
                "not_mentioned",
                "present",
                "present",
            ],
            juror_evidence=["Evidence 1", "Evidence 2"],
        )
        assert "anhedonia" in prompt
        assert "Test transcript" in prompt

    def test_invalid_item_raises_error(self) -> None:
        """Invalid item name raises ValueError."""
        with pytest.raises(ValueError, match="Unknown PHQ-8 item"):
            build_judge_item_prompt_v2(
                scoring_text="Test",
                item="invalid_item",
                juror_votes=[1, 2],
                juror_assertions=["present", "present"],
                juror_evidence=[],
            )

    def test_na_votes_displayed_as_not_mentioned(self) -> None:
        """None votes display as 'not_mentioned' in prompt."""
        prompt = build_judge_item_prompt_v2(
            scoring_text="Test",
            item="fatigue",
            juror_votes=[None, 2, None, 1],
            juror_assertions=["not_mentioned", "present", "not_mentioned", "present"],
            juror_evidence=["Some evidence"],
        )
        assert "not_mentioned" in prompt

    def test_vote_breakdown_calculated(self) -> None:
        """Prompt includes NA vs numeric vote breakdown."""
        prompt = build_judge_item_prompt_v2(
            scoring_text="Test",
            item="sleep",
            juror_votes=[None, None, None, 1, 2, None],  # 4 NA, 2 numeric
            juror_assertions=[
                "not_mentioned",
                "not_mentioned",
                "not_mentioned",
                "present",
                "present",
                "not_mentioned",
            ],
            juror_evidence=["Evidence from numeric jurors"],
        )
        assert "2 numeric" in prompt
        assert "4 not_mentioned" in prompt

    def test_empty_evidence_handled(self) -> None:
        """All-NA votes with no evidence handled gracefully."""
        prompt = build_judge_item_prompt_v2(
            scoring_text="Test",
            item="psychomotor",
            juror_votes=[None, None, None, None, None, None],
            juror_assertions=["not_mentioned"] * 6,
            juror_evidence=[],  # No evidence when all NA
        )
        assert "No evidence provided" in prompt

    def test_includes_item_definition(self) -> None:
        """Prompt includes v2 item definition."""
        prompt = build_judge_item_prompt_v2(
            scoring_text="Test",
            item="concentration",
            juror_votes=[1, 2, 1],
            juror_assertions=["present", "present", "present"],
            juror_evidence=["Hard to focus"],
        )
        assert PHQ8_RUBRIC["concentration"] in prompt

    def test_includes_juror_assertions(self) -> None:
        """Prompt includes juror assertions list."""
        prompt = build_judge_item_prompt_v2(
            scoring_text="Test",
            item="guilt",
            juror_votes=[0, 1, 0],
            juror_assertions=["denied", "present", "denied"],
            juror_evidence=["test evidence"],
        )
        assert "denied" in prompt
        assert "present" in prompt

    def test_includes_response_instructions(self) -> None:
        """Prompt includes response format instructions."""
        prompt = build_judge_item_prompt_v2(
            scoring_text="Test",
            item="appetite",
            juror_votes=[1, 2],
            juror_assertions=["present", "present"],
            juror_evidence=["test"],
        )
        assert "discussed" in prompt
        assert "assertion" in prompt
        assert "evidence" in prompt
        assert "rationale" in prompt
