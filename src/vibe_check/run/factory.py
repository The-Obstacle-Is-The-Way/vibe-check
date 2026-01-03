"""Factory functions to build real jurors and judges from Settings (SPEC-06)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from vibe_check.run.runner import DeterministicFakeJuror, deterministic_fake_judge_item
from vibe_check.scoring.agent import build_juror_agent
from vibe_check.scoring.juror import JurorScorer

if TYPE_CHECKING:
    from vibe_check.graph.single_dialogue import JudgeItemFn, Juror
    from vibe_check.judge.schema import JudgeItemResolution
    from vibe_check.schemas.scoring import PHQ8Report
    from vibe_check.settings import Settings


def build_real_jury(settings: Settings, *, prompt_version: str) -> list[Juror]:
    """Build a heterogeneous jury of real JurorScorer instances from Settings.

    Creates 3 models x 2 runs = 6 jurors per SSOT spec.

    Raises:
        ValueError: If required API keys are missing for any configured model.
    """
    jurors: list[Juror] = []

    model_configs = [
        (f"openai:{settings.juror_gpt_model}", settings.openai_api_key, "openai"),
        (f"anthropic:{settings.juror_claude_model}", settings.anthropic_api_key, "anthropic"),
        (f"google-gla:{settings.juror_gemini_model}", settings.google_api_key, "google"),
    ]

    for model_name, api_key, provider in model_configs:
        if api_key is None:
            raise ValueError(
                f"Missing {provider.upper()}_API_KEY for model {model_name}. "
                "Set it in .env or use --dry-run for deterministic fakes."
            )

        for run_number in range(1, settings.runs_per_model + 1):
            agent = build_juror_agent(
                model=model_name,
                prompt_version=prompt_version,
            )
            scorer = JurorScorer(
                agent=agent,
                model_id=model_name,
                run_number=run_number,
                prompt_version=prompt_version,
            )
            jurors.append(scorer)

    return jurors


def build_real_judge_item(settings: Settings, *, prompt_version: str) -> JudgeItemFn:
    """Build a real judge function that calls the judge model.

    Raises:
        ValueError: If ANTHROPIC_API_KEY is missing (judge uses Claude Opus).
    """
    from vibe_check.judge.agent import build_judge_agent
    from vibe_check.judge.prompting import build_judge_item_prompt

    if settings.anthropic_api_key is None:
        raise ValueError(
            "Missing ANTHROPIC_API_KEY for judge model. "
            "Set it in .env or use --dry-run for deterministic fakes."
        )

    agent = build_judge_agent(
        model=f"anthropic:{settings.judge_model}",
        prompt_version=prompt_version,
    )

    def real_judge_item(
        scoring_text: str,
        item: str,
        juror_reports: list[PHQ8Report],
        _prompt_version: str,
    ) -> JudgeItemResolution:
        juror_votes = [int(getattr(r, item).score) for r in juror_reports]
        juror_evidence = []
        for r in juror_reports:
            item_data = getattr(r, item)
            juror_evidence.extend(item_data.evidence)

        prompt = build_judge_item_prompt(
            scoring_text=scoring_text,
            item=item,
            juror_votes=juror_votes,
            juror_evidence=juror_evidence,
        )

        result = agent.run_sync(prompt)
        return result.output

    return real_judge_item


def build_fake_jury() -> list[Juror]:
    """Build the default deterministic fake jury for dry-run testing."""
    return [
        DeterministicFakeJuror("gpt-5.2", 1),
        DeterministicFakeJuror("gpt-5.2", 2),
        DeterministicFakeJuror("claude-sonnet", 1),
        DeterministicFakeJuror("claude-sonnet", 2),
        DeterministicFakeJuror("gemini-flash", 1),
        DeterministicFakeJuror("gemini-flash", 2),
    ]


def build_fake_judge_item() -> JudgeItemFn:
    """Build the deterministic fake judge for dry-run testing."""
    return deterministic_fake_judge_item
