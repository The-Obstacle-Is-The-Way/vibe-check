from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest
from tests.fixtures.sample_votes import create_mock_report

from vibe_check.graph.single_dialogue import (
    build_single_dialogue_graph,
    invoke_with_checkpoint_resume,
)
from vibe_check.judge.schema import JudgeItemReport
from vibe_check.schemas.scoring import TokenUsage
from vibe_check.sqlite import open_async_sqlite_saver

if TYPE_CHECKING:
    from pathlib import Path

    from vibe_check.graph.state import ScoringState
    from vibe_check.schemas.scoring import PHQ8Report


class FakeJuror:
    def __init__(self, report: PHQ8Report, *, fail_first: bool = False) -> None:
        self._report = report
        self._fail_first = fail_first
        self.calls = 0

    def score(self, _text: str) -> PHQ8Report:
        self.calls += 1
        if self._fail_first and self.calls == 1:
            raise RuntimeError("juror boom")
        return self._report

    async def ascore(self, text: str) -> PHQ8Report:
        return self.score(text)


def _base_state(*, file_id: str = "active82") -> ScoringState:
    return {
        "file_id": file_id,
        "condition": "mdd",
        "dialogue": "Therapist: Hi\nClient: I feel tired.",
        "scoring_text": "Therapist: Hi\nClient: I feel tired.",
        "prompt_version": "v1",
        "jury_results": [],
        "needs_arbitration": False,
        "final_output": None,
    }


@pytest.mark.asyncio
async def test_graph_arbitration_branch_overrides_final_scores(tmp_path: Path) -> None:
    reports = [create_mock_report(i, force_disagreement="sleep") for i in range(6)]
    jurors = [FakeJuror(r) for r in reports]

    def judge(
        scoring_text: str,
        item: str,
        juror_reports: list[PHQ8Report],
        prompt_version: str,
    ) -> JudgeItemReport:
        assert scoring_text
        assert prompt_version == "v1"
        assert item == "sleep"
        assert len(juror_reports) == 6
        return JudgeItemReport(
            item=item,
            final_score=2,
            confidence=0.9,
            rationale="Judge override for test.",
            usage=TokenUsage(input_tokens=7, output_tokens=3, reasoning_tokens=2, total_tokens=12),
        )

    graph = build_single_dialogue_graph(jurors=jurors, judge_item=judge)
    checkpoint_path = tmp_path / "graph.sqlite"

    async with open_async_sqlite_saver(checkpoint_path) as saver:
        app = graph.compile(checkpointer=saver)
        out = await invoke_with_checkpoint_resume(
            app,
            checkpointer=saver,
            initial_state=_base_state(),
            thread_id="active82",
            graph_max_concurrency=len(jurors),
        )

    final = out["final_output"]
    assert final is not None
    assert final.final_source == "judge_override"
    assert final.final_item_scores["sleep"] == 2
    assert final.judge_usage is not None
    assert final.judge_usage.total_tokens == 12


@pytest.mark.asyncio
async def test_graph_uses_async_juror_path(tmp_path: Path) -> None:
    class AsyncJuror:
        def __init__(self, report: PHQ8Report) -> None:
            self.calls = 0
            self._report = report

        def score(self, _text: str) -> PHQ8Report:
            raise AssertionError("sync score() should not be called")

        async def ascore(self, _text: str) -> PHQ8Report:
            self.calls += 1
            return self._report

    jurors = [AsyncJuror(create_mock_report(i)) for i in range(6)]

    def judge(
        _scoring_text: str,
        _item: str,
        _juror_reports: list[PHQ8Report],
        _prompt_version: str,
    ) -> JudgeItemReport:
        raise AssertionError("judge should not be called for unanimous reports")

    graph = build_single_dialogue_graph(jurors=jurors, judge_item=judge)
    checkpoint_path = tmp_path / "async_graph.sqlite"

    async with open_async_sqlite_saver(checkpoint_path) as saver:
        app = graph.compile(checkpointer=saver)
        out = await invoke_with_checkpoint_resume(
            app,
            checkpointer=saver,
            initial_state=_base_state(file_id="async1"),
            thread_id="async1",
            graph_max_concurrency=len(jurors),
        )

    assert [j.calls for j in jurors] == [1, 1, 1, 1, 1, 1]
    assert out["final_output"] is not None


@pytest.mark.asyncio
async def test_graph_runs_jurors_in_parallel(tmp_path: Path) -> None:
    class _Stats:
        def __init__(self) -> None:
            self.in_flight = 0
            self.max_in_flight = 0

    class BlockingJuror:
        def __init__(
            self,
            report: PHQ8Report,
            *,
            started: asyncio.Event,
            proceed: asyncio.Event,
            stats: _Stats,
        ) -> None:
            self._report = report
            self._started = started
            self._proceed = proceed
            self._stats = stats

        def score(self, _text: str) -> PHQ8Report:
            raise AssertionError("sync score() should not be called")

        async def ascore(self, _text: str) -> PHQ8Report:
            self._stats.in_flight += 1
            self._stats.max_in_flight = max(self._stats.max_in_flight, self._stats.in_flight)
            try:
                self._started.set()
                await self._proceed.wait()
                return self._report
            finally:
                self._stats.in_flight -= 1

    started_events = [asyncio.Event() for _ in range(6)]
    proceed = asyncio.Event()
    stats = _Stats()
    reports = [create_mock_report(i) for i in range(6)]
    jurors = [
        BlockingJuror(r, started=started_events[idx], proceed=proceed, stats=stats)
        for idx, r in enumerate(reports)
    ]

    def judge(
        _scoring_text: str,
        _item: str,
        _juror_reports: list[PHQ8Report],
        _prompt_version: str,
    ) -> JudgeItemReport:
        raise AssertionError("judge should not be called for unanimous reports")

    graph = build_single_dialogue_graph(jurors=jurors, judge_item=judge)
    checkpoint_path = tmp_path / "parallel.sqlite"

    async with open_async_sqlite_saver(checkpoint_path) as saver:
        app = graph.compile(checkpointer=saver)
        task = asyncio.create_task(
            invoke_with_checkpoint_resume(
                app,
                checkpointer=saver,
                initial_state=_base_state(file_id="parallel1"),
                thread_id="parallel1",
                graph_max_concurrency=len(jurors),
            )
        )

        try:
            await asyncio.wait_for(
                asyncio.gather(*(ev.wait() for ev in started_events)),
                timeout=2.0,
            )
        except TimeoutError:
            task.cancel()
            proceed.set()
            with pytest.raises(asyncio.CancelledError):
                await task
            raise
        else:
            proceed.set()
            out = await task

    assert stats.max_in_flight == 6
    assert out["final_output"] is not None


@pytest.mark.asyncio
async def test_checkpoint_resume_does_not_duplicate_reports(tmp_path: Path) -> None:
    reports = [create_mock_report(i) for i in range(6)]
    jurors = [
        FakeJuror(reports[0]),
        FakeJuror(reports[1]),
        FakeJuror(reports[2], fail_first=True),
        FakeJuror(reports[3]),
        FakeJuror(reports[4]),
        FakeJuror(reports[5]),
    ]

    def judge(
        _scoring_text: str,
        _item: str,
        _juror_reports: list[PHQ8Report],
        _prompt_version: str,
    ) -> JudgeItemReport:
        raise AssertionError("judge should not be called for unanimous reports")

    graph = build_single_dialogue_graph(jurors=jurors, judge_item=judge)
    checkpoint_path = tmp_path / "resume.sqlite"

    async with open_async_sqlite_saver(checkpoint_path) as saver:
        app = graph.compile(checkpointer=saver)
        with pytest.raises(RuntimeError, match="juror boom"):
            await invoke_with_checkpoint_resume(
                app,
                checkpointer=saver,
                initial_state=_base_state(file_id="resume1"),
                thread_id="resume1",
                graph_max_concurrency=len(jurors),
            )

        out = await invoke_with_checkpoint_resume(
            app,
            checkpointer=saver,
            initial_state=_base_state(file_id="resume1"),
            thread_id="resume1",
            graph_max_concurrency=len(jurors),
        )

    assert out["final_output"] is not None
    assert len(out["jury_results"]) == 6
    assert jurors[2].calls == 2
