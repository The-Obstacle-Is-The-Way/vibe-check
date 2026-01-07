"""Tests for PHQ-8 juror prompt builders (SPEC-14)."""

from __future__ import annotations

from vibe_check.constants import (
    PHQ8_JSON_SKELETON_V2,
    PHQ8_RUBRIC,
    PHQ8_SCORE_SCALE,
    PHQ8_TIME_FRAME,
    PHQ8_TIME_FRAME_V2,
)
from vibe_check.scoring.prompting import build_juror_system_prompt

# =============================================================================
# V1 Prompt Tests (Legacy)
# =============================================================================


class TestV1PromptStructure:
    """V1 prompt structure tests (legacy, for comparison)."""

    def test_v1_includes_legacy_timeframe(self) -> None:
        prompt = build_juror_system_prompt("v1.0.0")
        assert "Over the last 2 weeks" in prompt

    def test_v1_includes_legacy_frequency_scale(self) -> None:
        prompt = build_juror_system_prompt("v1.0.0")
        assert "Several days" in prompt
        assert "More than half the days" in prompt
        assert "Nearly every day" in prompt

    def test_v1_does_not_include_assertion_rules(self) -> None:
        prompt = build_juror_system_prompt("v1.0.0")
        # V1 has insufficient_evidence, not assertion
        assert '"assertion":' not in prompt
        assert "not_mentioned" not in prompt

    def test_v1_includes_insufficient_evidence(self) -> None:
        prompt = build_juror_system_prompt("v1.0.0")
        assert "insufficient_evidence" in prompt

    def test_v1_prompt_invariants(self) -> None:
        prompt = build_juror_system_prompt(prompt_version="v1", view_name="client_qa")

        assert "PHQ-8" in prompt
        assert "PHQ-9" not in prompt
        assert "JSON" in prompt
        assert "insufficient_evidence" in prompt
        assert "mentions_self_harm" in prompt

        assert PHQ8_TIME_FRAME in prompt
        for line in PHQ8_SCORE_SCALE.splitlines():
            assert line in prompt

        for item, definition in PHQ8_RUBRIC.items():
            assert item in prompt
            assert definition in prompt


# =============================================================================
# V2 Prompt Tests (Clinical Inference)
# =============================================================================


class TestV2PromptStructure:
    """V2 prompt structure tests (deterministic)."""

    def test_v2_includes_clinical_timeframe(self) -> None:
        prompt = build_juror_system_prompt("v2.0.0")
        assert PHQ8_TIME_FRAME_V2 in prompt
        # V1 timeframe should NOT appear (unless as part of ~last 2 weeks)
        assert "Over the last 2 weeks" not in prompt or "~last 2 weeks" in prompt

    def test_v2_includes_severity_table(self) -> None:
        prompt = build_juror_system_prompt("v2.0.0")
        assert "Mild / intermittent" in prompt
        assert "Frequent/persistent" in prompt
        assert "Near-daily/persistent" in prompt

    def test_v2_includes_context_rules(self) -> None:
        prompt = build_juror_system_prompt("v2.0.0")
        assert "Experiencer" in prompt
        assert "Temporality" in prompt
        assert "Hypothetical" in prompt
        assert "Negation" in prompt

    def test_v2_includes_assertion_rules(self) -> None:
        prompt = build_juror_system_prompt("v2.0.0")
        assert "not_mentioned" in prompt
        assert "denied" in prompt
        assert "possible" in prompt
        assert "present" in prompt

    def test_v2_includes_json_skeleton(self) -> None:
        prompt = build_juror_system_prompt("v2.0.0")
        # Skeleton must be present (key parts of it)
        assert '"discussed": true' in prompt or '"discussed":true' in prompt
        assert '"assertion": "not_mentioned"' in prompt or '"assertion":"not_mentioned"' in prompt
        assert '"score": null' in prompt or '"score":null' in prompt

    def test_v2_emphasizes_na_vs_denied(self) -> None:
        prompt = build_juror_system_prompt("v2.0.0")
        assert "DO NOT score 0 for items that are simply not mentioned" in prompt

    def test_v2_includes_evidence_constraints(self) -> None:
        prompt = build_juror_system_prompt("v2.0.0")
        assert "50 words" in prompt
        assert "400 characters" in prompt
        assert "3 snippets" in prompt or "Maximum 3" in prompt

    def test_v2_no_legacy_frequency_scale_definition(self) -> None:
        """V2 should not have legacy scale as the PRIMARY definition."""
        prompt = build_juror_system_prompt("v2.0.0")
        # "Several days" can appear as a CUE, but not as "1 = Several days"
        assert "1 = Several days" not in prompt
        assert "2 = More than half the days" not in prompt

    def test_v2_allows_frequency_cues(self) -> None:
        """V2 may mention 'every day' as a severity cue."""
        prompt = build_juror_system_prompt("v2.0.0")
        # These are cues in the severity table, which is fine
        assert "every day" in prompt.lower() or "nearly every day" in prompt.lower()

    def test_v2_includes_all_item_definitions(self) -> None:
        prompt = build_juror_system_prompt("v2.0.0")
        for item, definition in PHQ8_RUBRIC.items():
            assert item in prompt
            assert definition in prompt

    def test_v2_does_not_include_insufficient_evidence(self) -> None:
        """V2 uses assertion, not insufficient_evidence."""
        prompt = build_juror_system_prompt("v2.0.0")
        assert "insufficient_evidence" not in prompt


# =============================================================================
# Version Routing Tests
# =============================================================================


class TestPromptVersionRouting:
    """Prompt version routing tests."""

    def test_v1_routing(self) -> None:
        prompt = build_juror_system_prompt("v1.0.0")
        assert "Several days" in prompt  # V1 indicator
        assert "insufficient_evidence" in prompt  # V1 uses this

    def test_v1_1_routing(self) -> None:
        prompt = build_juror_system_prompt("v1.1.0")
        assert "Several days" in prompt  # Still V1

    def test_v2_routing(self) -> None:
        prompt = build_juror_system_prompt("v2.0.0")
        assert "not_mentioned" in prompt  # V2 indicator
        assert '"discussed":' in prompt or '"discussed": ' in prompt  # V2 uses this

    def test_v2_1_routing(self) -> None:
        prompt = build_juror_system_prompt("v2.1.0")
        assert "not_mentioned" in prompt  # Still V2


# =============================================================================
# Extra Instructions Tests
# =============================================================================


class TestExtraInstructions:
    """extra_instructions parameter tests."""

    def test_extra_instructions_appended_v1(self) -> None:
        prompt = build_juror_system_prompt("v1.0.0", extra_instructions="CUSTOM RULE")
        assert "CUSTOM RULE" in prompt

    def test_extra_instructions_appended_v2(self) -> None:
        prompt = build_juror_system_prompt("v2.0.0", extra_instructions="CUSTOM RULE")
        assert "CUSTOM RULE" in prompt

    def test_none_extra_instructions(self) -> None:
        prompt = build_juror_system_prompt("v2.0.0", extra_instructions=None)
        assert "CUSTOM" not in prompt

    def test_empty_extra_instructions(self) -> None:
        prompt_none = build_juror_system_prompt("v2.0.0", extra_instructions=None)
        prompt_blank = build_juror_system_prompt("v2.0.0", extra_instructions="  ")
        assert prompt_blank == prompt_none


# =============================================================================
# Constants Inclusion Tests
# =============================================================================


class TestConstantsInclusion:
    """Test that prompts include the expected constants."""

    def test_v2_includes_time_frame_v2(self) -> None:
        prompt = build_juror_system_prompt("v2.0.0")
        assert PHQ8_TIME_FRAME_V2 in prompt

    def test_v2_includes_score_scale_v2(self) -> None:
        prompt = build_juror_system_prompt("v2.0.0")
        # The scale should be present (check key parts)
        assert "Evidence Pattern" in prompt
        assert "Mild / intermittent" in prompt

    def test_v2_includes_assertion_rules_v2(self) -> None:
        prompt = build_juror_system_prompt("v2.0.0")
        # Check parts of PHQ8_ASSERTION_RULES_V2
        assert "present (score 1-3)" in prompt
        assert "denied (score 0)" in prompt

    def test_v2_includes_context_rules_v2(self) -> None:
        prompt = build_juror_system_prompt("v2.0.0")
        # Check parts of PHQ8_CONTEXT_RULES_V2
        assert "Experiencer:" in prompt
        assert "Temporality:" in prompt

    def test_v2_includes_evidence_constraints_v2(self) -> None:
        prompt = build_juror_system_prompt("v2.0.0")
        # Check parts of PHQ8_EVIDENCE_CONSTRAINTS_V2
        assert "Maximum 3 snippets" in prompt
        assert "≤50 words" in prompt

    def test_v2_includes_json_skeleton_v2(self) -> None:
        prompt = build_juror_system_prompt("v2.0.0")
        # The skeleton should appear in the prompt
        assert PHQ8_JSON_SKELETON_V2 in prompt
