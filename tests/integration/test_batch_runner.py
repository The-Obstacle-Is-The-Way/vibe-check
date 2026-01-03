from __future__ import annotations

import json
from typing import TYPE_CHECKING

from vibe_check.run.factory import build_fake_judge_item, build_fake_jury
from vibe_check.run.ledger import JobLedger
from vibe_check.run.runner import score_corpus

if TYPE_CHECKING:
    from pathlib import Path


def test_batch_runner_writes_outputs_and_resumes(tmp_path: Path) -> None:
    output_dir = tmp_path / "run"
    checkpoint_db = str(tmp_path / "checkpoints.sqlite")

    score_corpus(
        input_path="data/sqpsychconv/qwen-2.5",
        output_dir=output_dir,
        checkpoint_db=checkpoint_db,
        limit=5,
        prompt_version="v1",
        dialogue_view="client_qa",
        jurors=build_fake_jury(),
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

    with JobLedger(output_dir / "ledger.sqlite") as ledger:
        attempts_before = {file_id: ledger.get_attempts(file_id) for file_id in ledger.list_all()}

    score_corpus(
        input_path="data/sqpsychconv/qwen-2.5",
        output_dir=output_dir,
        checkpoint_db=checkpoint_db,
        limit=5,
        prompt_version="v1",
        dialogue_view="client_qa",
        jurors=build_fake_jury(),
        judge_item=build_fake_judge_item(),
    )

    with JobLedger(output_dir / "ledger.sqlite") as ledger:
        attempts_after = {file_id: ledger.get_attempts(file_id) for file_id in ledger.list_all()}
    assert attempts_after == attempts_before

    # Verify token usage is present in manifest
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    token_totals = manifest["token_usage_totals"]
    assert token_totals["total_tokens"] > 0
    assert token_totals["input_tokens"] > 0
    assert token_totals["output_tokens"] > 0
    # Reasoning might be 0 depending on the model/fake used, so we check >= 0
    assert token_totals["reasoning_tokens"] >= 0
