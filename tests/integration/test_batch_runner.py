from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING

import pytest
from tests.fixtures.hf_disk_dataset import write_sqpsychconv_like_dataset
from tests.fixtures.sample_votes import create_mock_report

from vibe_check.constants import phq8_rubric_hash
from vibe_check.run.factory import build_fake_judge_item
from vibe_check.run.ledger import JobLedger
from vibe_check.run.runner import score_corpus
from vibe_check.schemas.scoring import TokenUsage

if TYPE_CHECKING:
    from pathlib import Path

    from vibe_check.schemas.scoring import PHQ8Report


def test_batch_runner_writes_outputs_and_resumes(tmp_path: Path) -> None:
    output_dir = tmp_path / "run"
    checkpoint_db = str(tmp_path / "checkpoints.sqlite")
    dataset_dir = write_sqpsychconv_like_dataset(tmp_path, n_train=8, n_test=0)

    class StaticJuror:
        def __init__(self, idx: int) -> None:
            base = create_mock_report(idx, force_disagreement="sleep")
            self._report = base.model_copy(
                update={
                    "usage": TokenUsage(
                        input_tokens=10,
                        output_tokens=5,
                        reasoning_tokens=1,
                        total_tokens=16,
                    )
                }
            )

        def score(self, _scoring_text: str) -> PHQ8Report:
            return self._report

        async def ascore(self, scoring_text: str) -> PHQ8Report:
            return self.score(scoring_text)

    jurors = [StaticJuror(i) for i in range(6)]

    score_corpus(
        input_path=dataset_dir,
        output_dir=output_dir,
        checkpoint_db=checkpoint_db,
        limit=5,
        prompt_version="v1",
        dialogue_view="client_qa",
        jurors=jurors,
        judge_item=build_fake_judge_item(),
    )

    scored_path = output_dir / "scored.jsonl"
    manifest_path = output_dir / "run_manifest.json"
    assert scored_path.exists()
    assert manifest_path.exists()

    lines = scored_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 5
    row = json.loads(lines[0])
    assert "file_id" in row
    assert "final_total_score" in row
    assert "final_item_scores" in row
    assert row["truncated_utterance_count"] == 0
    assert row["triggered_arbitration"] is True

    with JobLedger(output_dir / "ledger.sqlite") as ledger:
        attempts_before = {file_id: ledger.get_attempts(file_id) for file_id in ledger.list_all()}

    manifest_1 = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_hash = phq8_rubric_hash()
    assert manifest_1["phq8_rubric_hash"] == expected_hash
    assert manifest_1["run_config"]["phq8_rubric_hash"] == expected_hash
    assert manifest_1["arbitration_rate"] > 0.0

    score_corpus(
        input_path=dataset_dir,
        output_dir=output_dir,
        checkpoint_db=checkpoint_db,
        limit=5,
        prompt_version="v1",
        dialogue_view="client_qa",
        jurors=jurors,
        judge_item=build_fake_judge_item(),
    )

    with JobLedger(output_dir / "ledger.sqlite") as ledger:
        attempts_after = {file_id: ledger.get_attempts(file_id) for file_id in ledger.list_all()}
    assert attempts_after == attempts_before

    manifest_2 = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest_2["arbitration_rate"] == manifest_1["arbitration_rate"]

    # Verify token usage is present in manifest
    token_totals = manifest_2["token_usage_totals"]
    # 5 dialogues, 6 jurors each (16 tokens per juror report) + 1 judge call (80 tokens) per dialogue.
    assert token_totals == {
        "input_tokens": 550,
        "output_tokens": 275,
        "reasoning_tokens": 55,
        "total_tokens": 880,
    }


def test_batch_runner_supports_parallel_dialogues(tmp_path: Path) -> None:
    output_dir = tmp_path / "run"
    checkpoint_db = str(tmp_path / "checkpoints.sqlite")
    dataset_dir = write_sqpsychconv_like_dataset(tmp_path, n_train=4, n_test=0)

    class SlowJuror:
        def __init__(self, idx: int) -> None:
            self._report = create_mock_report(idx)

        def score(self, _scoring_text: str) -> PHQ8Report:
            return self._report

        async def ascore(self, scoring_text: str) -> PHQ8Report:
            await asyncio.sleep(0.01)
            return self.score(scoring_text)

    jurors = [SlowJuror(i) for i in range(6)]

    score_corpus(
        input_path=dataset_dir,
        output_dir=output_dir,
        checkpoint_db=checkpoint_db,
        limit=4,
        prompt_version="v1",
        dialogue_view="client_qa",
        max_concurrency=2,
        jurors=jurors,
        judge_item=build_fake_judge_item(),
    )

    scored_path = output_dir / "scored.jsonl"
    assert scored_path.exists()
    assert len(scored_path.read_text(encoding="utf-8").splitlines()) == 4

    with JobLedger(output_dir / "ledger.sqlite") as ledger:
        statuses = {file_id: ledger.get_status(file_id) for file_id in ledger.list_all()}
    assert set(statuses.values()) == {"done"}


def test_batch_runner_refuses_config_mismatch_without_force(tmp_path: Path) -> None:
    output_dir = tmp_path / "run"
    checkpoint_db = str(tmp_path / "checkpoints.sqlite")
    dataset_dir = write_sqpsychconv_like_dataset(tmp_path, n_train=3, n_test=0)

    class StaticJuror:
        def __init__(self, idx: int) -> None:
            base = create_mock_report(idx, force_disagreement="sleep")
            self._report = base.model_copy(
                update={
                    "usage": TokenUsage(
                        input_tokens=10,
                        output_tokens=5,
                        reasoning_tokens=1,
                        total_tokens=16,
                    )
                }
            )

        def score(self, _scoring_text: str) -> PHQ8Report:
            return self._report

        async def ascore(self, scoring_text: str) -> PHQ8Report:
            return self.score(scoring_text)

    jurors = [StaticJuror(i) for i in range(6)]

    score_corpus(
        input_path=dataset_dir,
        output_dir=output_dir,
        checkpoint_db=checkpoint_db,
        limit=2,
        prompt_version="v1",
        dialogue_view="client_qa",
        jurors=jurors,
        judge_item=build_fake_judge_item(),
    )

    with pytest.raises(ValueError, match="run configuration mismatch"):
        score_corpus(
            input_path=dataset_dir,
            output_dir=output_dir,
            checkpoint_db=checkpoint_db,
            limit=2,
            prompt_version="v2",
            dialogue_view="client_qa",
            jurors=jurors,
            judge_item=build_fake_judge_item(),
        )


def test_batch_runner_marks_failed_and_continues_when_fail_fast_false(tmp_path: Path) -> None:
    output_dir = tmp_path / "run"
    checkpoint_db = str(tmp_path / "checkpoints.sqlite")
    dataset_dir = write_sqpsychconv_like_dataset(tmp_path, n_train=3, n_test=0)

    class StaticJuror:
        def __init__(self, idx: int) -> None:
            base = create_mock_report(idx)
            self._report = base.model_copy(
                update={
                    "usage": TokenUsage(
                        input_tokens=10,
                        output_tokens=5,
                        reasoning_tokens=1,
                        total_tokens=16,
                    )
                }
            )
            self.calls = 0

        def score(self, _scoring_text: str) -> PHQ8Report:
            self.calls += 1
            return self._report

        async def ascore(self, scoring_text: str) -> PHQ8Report:
            return self.score(scoring_text)

    class FlakyJuror(StaticJuror):
        async def ascore(self, _scoring_text: str) -> PHQ8Report:
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("boom")
            return self._report

    jurors = [FlakyJuror(0)] + [StaticJuror(i) for i in range(1, 6)]

    score_corpus(
        input_path=dataset_dir,
        output_dir=output_dir,
        checkpoint_db=checkpoint_db,
        limit=3,
        prompt_version="v1",
        dialogue_view="client_qa",
        max_concurrency=1,
        fail_fast=False,
        jurors=jurors,
        judge_item=build_fake_judge_item(),
    )

    manifest = json.loads((output_dir / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["completed"] == 2
    assert manifest["failed"] == 1
    assert manifest["rows_written"] == 2

    with JobLedger(output_dir / "ledger.sqlite") as ledger:
        assert ledger.get_status("active0001") == "failed"
        row = ledger.conn.execute(
            "SELECT error_code, error_message FROM jobs WHERE file_id = ?",
            ("active0001",),
        ).fetchone()
        assert row is not None
        assert row[0] == "RuntimeError"
        assert "boom" in str(row[1])


def test_batch_runner_fail_fast_raises_on_first_error(tmp_path: Path) -> None:
    output_dir = tmp_path / "run"
    checkpoint_db = str(tmp_path / "checkpoints.sqlite")
    dataset_dir = write_sqpsychconv_like_dataset(tmp_path, n_train=3, n_test=0)

    class StaticJuror:
        def __init__(self, idx: int) -> None:
            base = create_mock_report(idx)
            self._report = base.model_copy(
                update={
                    "usage": TokenUsage(
                        input_tokens=10,
                        output_tokens=5,
                        reasoning_tokens=1,
                        total_tokens=16,
                    )
                }
            )

        def score(self, _scoring_text: str) -> PHQ8Report:
            return self._report

        async def ascore(self, scoring_text: str) -> PHQ8Report:
            return self.score(scoring_text)

    class FlakyJuror(StaticJuror):
        def __init__(self, idx: int) -> None:
            super().__init__(idx)
            self.calls = 0

        async def ascore(self, _scoring_text: str) -> PHQ8Report:
            self.calls += 1
            raise RuntimeError("boom")

    jurors = [FlakyJuror(0)] + [StaticJuror(i) for i in range(1, 6)]

    with pytest.raises(ExceptionGroup) as excinfo:
        score_corpus(
            input_path=dataset_dir,
            output_dir=output_dir,
            checkpoint_db=checkpoint_db,
            limit=3,
            prompt_version="v1",
            dialogue_view="client_qa",
            max_concurrency=1,
            fail_fast=True,
            jurors=jurors,
            judge_item=build_fake_judge_item(),
        )

    def _flatten(exc: BaseException) -> list[BaseException]:
        if isinstance(exc, BaseExceptionGroup):
            flattened: list[BaseException] = []
            for child in exc.exceptions:
                flattened.extend(_flatten(child))
            return flattened
        return [exc]

    leaf_exceptions = _flatten(excinfo.value)
    assert any(isinstance(e, RuntimeError) and str(e) == "boom" for e in leaf_exceptions)

    with JobLedger(output_dir / "ledger.sqlite") as ledger:
        assert ledger.get_status("active0001") == "failed"
