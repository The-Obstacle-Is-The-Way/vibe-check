from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from aiolimiter import AsyncLimiter
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel

from vibe_check.schemas.scoring import PHQ8Assessment, PHQ8Report
from vibe_check.scoring.juror import JurorScorer
from vibe_check.scoring.prompting import build_juror_system_prompt

if TYPE_CHECKING:
    from types import TracebackType


def test_juror_scorer_end_to_end_with_testmodel() -> None:
    fixture_path = Path("tests/fixtures/juror_outputs/juror_ok.json")
    raw = json.loads(fixture_path.read_text(encoding="utf-8"))

    # Use custom_output_args for structured output simulation
    model = TestModel(custom_output_args=raw)

    agent = Agent(
        model=model, output_type=PHQ8Assessment, system_prompt=build_juror_system_prompt("v1")
    )
    scorer = JurorScorer(agent=agent, model_id="fake-model", run_number=1, prompt_version="v1")

    report = scorer.score("Client: I'm tired.\nTherapist: Tell me more.")
    assert isinstance(report, PHQ8Report)
    assert report.model_id == "fake-model"
    assert report.run_number == 1
    assert report.total_score == sum(report.item_scores.values())
    assert report.usage is not None


@pytest.mark.asyncio
async def test_juror_scorer_ascore_retries_transient_errors_and_rate_limits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture_path = Path("tests/fixtures/juror_outputs/juror_ok.json")
    raw = json.loads(fixture_path.read_text(encoding="utf-8"))

    model = TestModel(custom_output_args=raw)
    agent: Agent[None, PHQ8Assessment] = Agent(
        model=model, output_type=PHQ8Assessment, system_prompt=build_juror_system_prompt("v1")
    )

    class CountingLimiter(AsyncLimiter):
        def __init__(self) -> None:
            super().__init__(1_000_000, 60.0)
            self.entered = 0
            self.exited = 0

        async def __aenter__(self) -> None:
            self.entered += 1
            await super().__aenter__()

        async def __aexit__(
            self,
            exc_type: type[BaseException] | None,
            exc: BaseException | None,
            tb: TracebackType | None,
        ) -> None:
            self.exited += 1
            await super().__aexit__(exc_type, exc, tb)

    limiter = CountingLimiter()

    scorer = JurorScorer(
        agent=agent,
        model_id="fake-model",
        run_number=1,
        prompt_version="v1",
        rate_limiter=limiter,
        max_retries=2,
        retry_initial_wait=0.0,
        retry_max_wait=0.0,
        retry_jitter=0.0,
    )

    calls = 0
    original_run = agent.run

    async def flaky_run(scoring_text: str) -> object:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TimeoutError("transient")
        return await original_run(scoring_text)

    monkeypatch.setattr(agent, "run", flaky_run)
    report = await scorer.ascore("Client: I'm tired.\nTherapist: Tell me more.")

    assert calls == 2
    assert limiter.entered == 1
    assert limiter.exited == 1
    assert isinstance(report, PHQ8Report)
    assert report.usage is not None
