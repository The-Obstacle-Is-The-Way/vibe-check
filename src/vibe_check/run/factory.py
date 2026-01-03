"""Factory for creating scoring actors (real or fake)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from vibe_check.scoring.agent import build_juror_agent
from vibe_check.scoring.fakes import DeterministicFakeJuror, deterministic_fake_judge_item
from vibe_check.scoring.juror import JurorScorer

if TYPE_CHECKING:
    from collections.abc import Sequence

    from vibe_check.judge.schema import JudgeItemResolution
    from vibe_check.schemas.scoring import PHQ8Report
    from vibe_check.settings import Settings


class Juror(Protocol):
    def score(self, scoring_text: str) -> PHQ8Report: ...


class JudgeItemFn(Protocol):
    def __call__(
        self,
        scoring_text: str,
        item: str,
        juror_reports: list[PHQ8Report],
        prompt_version: str,
    ) -> JudgeItemResolution: ...


def build_fake_jury(
    models: list[str] | None = None,
    runs_per_model: int = 2,
) -> Sequence[Juror]:
    """Build a list of deterministic fake jurors."""
    if models is None:
        models = ["gpt-5.2", "claude-sonnet", "gemini-pro"]
    jurors: list[Juror] = []
    for model_id in models:
        for run_no in range(1, runs_per_model + 1):
            jurors.append(DeterministicFakeJuror(model_id, run_no))
    return jurors


def build_fake_judge_item() -> JudgeItemFn:
    """Return the deterministic fake judge function."""
    return deterministic_fake_judge_item


def build_real_jury(settings: Settings) -> Sequence[Juror]:
    """Build a list of real PydanticAI-backed jurors using settings."""
    # PydanticAI provider prefixes: openai, anthropic, google-gla (not "google")
    configs = [
        ("openai", settings.juror_gpt_model),
        ("anthropic", settings.juror_claude_model),
        ("google-gla", settings.juror_gemini_model),
    ]

    jurors: list[Juror] = []

    for provider, model_id in configs:
        # PydanticAI model identifier e.g. "openai:gpt-5.2"
        full_model_name = f"{provider}:{model_id}"

        for run_no in range(1, settings.runs_per_model + 1):
            agent = build_juror_agent(
                model=full_model_name,
                prompt_version=settings.prompt_version,
                view_name=settings.scoring_dialogue_view,
            )
            scorer = JurorScorer(
                agent=agent,
                model_id=model_id,
                run_number=run_no,
                prompt_version=settings.prompt_version,
            )
            jurors.append(scorer)

    return jurors


def build_real_judge_item(settings: Settings) -> JudgeItemFn:
    """Build a real judge function backed by an Agent."""
    from typing import cast

    from vibe_check.judge.agent import build_judge_agent
    from vibe_check.judge.prompting import build_judge_item_prompt

    full_model_name = f"anthropic:{settings.judge_model}"
    agent = build_judge_agent(model=full_model_name, prompt_version=settings.prompt_version)

    def judge_fn(
        scoring_text: str,
        item: str,
        juror_reports: list[PHQ8Report],
        prompt_version: str,
    ) -> JudgeItemResolution:
        _ = prompt_version
        evidence_pool: list[str] = []
        votes: list[int] = []
        for r in juror_reports:
            item_score = getattr(r, item)
            votes.append(int(item_score.score))
            evidence_pool.extend(item_score.evidence)

        prompt = build_judge_item_prompt(
            scoring_text=scoring_text,
            item=item,
            juror_votes=votes,
            juror_evidence=evidence_pool,
        )

        result = agent.run_sync(prompt)
        # PydanticAI v1+ puts structured output in .data
        output = getattr(result, "data", getattr(result, "output", None))
        return cast("JudgeItemResolution", output)

    return judge_fn
