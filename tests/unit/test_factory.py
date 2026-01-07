"""Tests for run/factory.py - BUG-027 fix validation.

Ensures CLI args for prompt_version and dialogue_view flow through to agents,
not hardcoded from Settings.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from vibe_check.run.factory import build_real_judge_item, build_real_jury
from vibe_check.settings import Settings


@pytest.fixture
def mock_settings() -> Settings:
    """Create a Settings object with specific values we can verify against."""
    # We'll set settings to DIFFERENT values than what we pass to the factory
    # to verify the factory uses the passed params, not settings
    settings = Settings(
        prompt_version="settings_version",
        scoring_dialogue_view="client_only",
        openai_api_key="test-openai",
        anthropic_api_key="test-anthropic",
        google_api_key="test-google",
        llm_temperature=0.12,
        llm_top_p=0.9,
        llm_max_tokens=1234,
        llm_timeout=12.5,
        llm_seed=42,
    )
    return settings


class TestBuildRealJury:
    """Tests for build_real_jury with explicit prompt_version and dialogue_view."""

    def test_uses_passed_prompt_version_not_settings(self, mock_settings: Settings) -> None:
        """BUG-027: build_real_jury must use passed prompt_version, not settings."""
        passed_version = "v2.0.0-clinical"

        with patch("vibe_check.run.factory.build_juror_agent") as mock_build_agent:
            mock_build_agent.return_value = MagicMock()

            # Call with explicit prompt_version different from settings
            build_real_jury(
                mock_settings,
                prompt_version=passed_version,
                dialogue_view="client_qa",
            )

            # Verify build_juror_agent was called with the PASSED version
            # not settings.prompt_version ("settings_version")
            for call in mock_build_agent.call_args_list:
                assert call.kwargs["prompt_version"] == passed_version
                assert call.kwargs["prompt_version"] != "settings_version"
                model_settings = call.kwargs["model_settings"]
                assert model_settings["temperature"] == pytest.approx(0.12)
                assert model_settings["top_p"] == pytest.approx(0.9)
                assert model_settings["max_tokens"] == 1234
                assert model_settings["timeout"] == pytest.approx(12.5)
                assert model_settings["seed"] == 42

    def test_uses_passed_dialogue_view_not_settings(self, mock_settings: Settings) -> None:
        """BUG-027: build_real_jury must use passed dialogue_view, not settings."""
        passed_view = "client_qa"  # Different from settings ("client_only")

        with patch("vibe_check.run.factory.build_juror_agent") as mock_build_agent:
            mock_build_agent.return_value = MagicMock()

            build_real_jury(
                mock_settings,
                prompt_version="v2.0.0-clinical",
                dialogue_view=passed_view,
            )

            # Verify build_juror_agent was called with the PASSED view
            # not settings.scoring_dialogue_view ("client_only")
            for call in mock_build_agent.call_args_list:
                assert call.kwargs["view_name"] == passed_view
                assert call.kwargs["view_name"] != "client_only"
                model_settings = call.kwargs["model_settings"]
                assert model_settings["temperature"] == pytest.approx(0.12)
                assert model_settings["top_p"] == pytest.approx(0.9)
                assert model_settings["max_tokens"] == 1234
                assert model_settings["timeout"] == pytest.approx(12.5)
                assert model_settings["seed"] == 42

    def test_creates_six_jurors(self, mock_settings: Settings) -> None:
        """Verify we still get 6 jurors (3 models x 2 runs each)."""
        with patch("vibe_check.run.factory.build_juror_agent") as mock_build_agent:
            mock_build_agent.return_value = MagicMock()

            jurors = build_real_jury(
                mock_settings,
                prompt_version="v2.0.0-clinical",
                dialogue_view="client_qa",
            )

            assert len(jurors) == 6
            assert mock_build_agent.call_count == 6
            for call in mock_build_agent.call_args_list:
                model_settings = call.kwargs["model_settings"]
                assert model_settings["temperature"] == pytest.approx(0.12)
                assert model_settings["top_p"] == pytest.approx(0.9)
                assert model_settings["max_tokens"] == 1234
                assert model_settings["timeout"] == pytest.approx(12.5)
                assert model_settings["seed"] == 42


class TestBuildRealJudgeItem:
    """Tests for build_real_judge_item with explicit prompt_version."""

    def test_uses_passed_prompt_version_not_settings(self, mock_settings: Settings) -> None:
        """BUG-027: build_real_judge_item must use passed prompt_version."""
        passed_version = "v2.0.0-clinical"

        # Patch at the source module since it's imported inside the function
        with patch("vibe_check.judge.agent.build_judge_agent_v2") as mock_build_agent:
            mock_build_agent.return_value = MagicMock()

            build_real_judge_item(
                mock_settings,
                prompt_version=passed_version,
            )

            # Verify build_judge_agent was called with the PASSED version
            mock_build_agent.assert_called_once()
            call_kwargs = mock_build_agent.call_args.kwargs
            assert call_kwargs["prompt_version"] == passed_version
            assert call_kwargs["prompt_version"] != "settings_version"
            model_settings = call_kwargs["model_settings"]
            assert model_settings["temperature"] == pytest.approx(0.12)
            assert model_settings["top_p"] == pytest.approx(0.9)
            assert model_settings["max_tokens"] == 1234
            assert model_settings["timeout"] == pytest.approx(12.5)
            assert model_settings["seed"] == 42

    def test_rejects_v1_prompt_version(self, mock_settings: Settings) -> None:
        with pytest.raises(ValueError, match="v2\\.\\* prompt_version"):
            build_real_judge_item(mock_settings, prompt_version="v1.0.0")


class TestLivePromptVersionGuards:
    def test_real_jury_rejects_v1_prompt_version(self, mock_settings: Settings) -> None:
        with pytest.raises(ValueError, match="v2\\.\\* prompt_version"):
            build_real_jury(mock_settings, prompt_version="v1.0.0", dialogue_view="client_qa")


class TestBackwardsCompatibility:
    """Ensure we don't break existing code that doesn't pass the new params."""

    def test_build_real_jury_requires_prompt_version(self, mock_settings: Settings) -> None:
        """prompt_version is required - no default from settings."""
        with pytest.raises(TypeError, match="prompt_version"):
            build_real_jury(mock_settings)  # type: ignore[call-arg]

    def test_build_real_jury_requires_dialogue_view(self, mock_settings: Settings) -> None:
        """dialogue_view is required - no default from settings."""
        with pytest.raises(TypeError, match="dialogue_view"):
            build_real_jury(mock_settings, prompt_version="v1.0.0")  # type: ignore[call-arg]

    def test_build_real_judge_item_requires_prompt_version(self, mock_settings: Settings) -> None:
        """prompt_version is required - no default from settings."""
        with pytest.raises(TypeError, match="prompt_version"):
            build_real_judge_item(mock_settings)  # type: ignore[call-arg]
