from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from tests.fixtures.hf_disk_dataset import write_sqpsychconv_like_dataset
from tests.fixtures.sample_votes import create_mock_report

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
    assert row["triggered_arbitration"] is True

    with JobLedger(output_dir / "ledger.sqlite") as ledger:
        attempts_before = {file_id: ledger.get_attempts(file_id) for file_id in ledger.list_all()}

    manifest_1 = json.loads(manifest_path.read_text(encoding="utf-8"))
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
