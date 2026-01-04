from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest
from tests.fixtures.hf_disk_dataset import write_sqpsychconv_like_dataset

from vibe_check.cli import main

if TYPE_CHECKING:
    from pathlib import Path

    from _pytest.monkeypatch import MonkeyPatch


@pytest.mark.e2e
def test_cli_live_smoke_one_dialogue(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    """Live-provider smoke test (costs money).

    This test is skipped by default. Opt in explicitly:
      - set `VIBE_CHECK_RUN_LIVE_E2E=1`
      - export API keys: OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY (or GEMINI_API_KEY)
    """
    if os.environ.get("VIBE_CHECK_RUN_LIVE_E2E") != "1":
        pytest.skip("Set VIBE_CHECK_RUN_LIVE_E2E=1 to run live e2e tests (costs money).")

    missing: list[str] = []
    if not os.environ.get("OPENAI_API_KEY"):
        missing.append("OPENAI_API_KEY")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        missing.append("ANTHROPIC_API_KEY")
    if not (os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")):
        missing.append("GOOGLE_API_KEY (or GEMINI_API_KEY)")

    if missing:
        pytest.skip(f"Missing required API keys for live e2e: {', '.join(missing)}")

    # Keep `.env` from the repo from affecting this run.
    monkeypatch.chdir(tmp_path)

    # Minimize cost: 1 run per provider => 3 jurors total.
    monkeypatch.setenv("RUNS_PER_MODEL", "1")

    # Minimize judge cost/variance: effectively disable arbitration triggers.
    monkeypatch.setenv("DISAGREEMENT_RANGE_THRESHOLD", "10")
    monkeypatch.setenv("ARBITRATION_TOTAL_STD_THRESHOLD", "100.0")
    monkeypatch.setenv("ARBITRATION_MAX_PROB_THRESHOLD", "0.0")
    monkeypatch.setenv("ARBITRATION_ENTROPY_THRESHOLD", "100.0")
    monkeypatch.setenv("CLINICAL_AMBIGUITY_BAND_LOW", "0.5000001")
    monkeypatch.setenv("CLINICAL_AMBIGUITY_BAND_HIGH", "0.5000001")
    monkeypatch.setenv("INSUFFICIENT_EVIDENCE_THRESHOLD", "999")

    dataset_dir = write_sqpsychconv_like_dataset(tmp_path, n_train=1, n_test=0)
    output_dir = tmp_path / "run"
    checkpoint_db = tmp_path / "checkpoints.sqlite"

    exit_code = main(
        [
            "score-corpus",
            "--input",
            str(dataset_dir),
            "--checkpoint",
            str(checkpoint_db),
            "--output",
            str(output_dir),
            "--limit",
            "1",
            "--live",
            "--prompt-version",
            "v1.0.0",
            "--dialogue-view",
            "client_qa",
            "--max-concurrency",
            "1",
        ]
    )
    assert exit_code == 0

    assert (output_dir / "scored.jsonl").exists()

    export_dir = output_dir / "export"
    export_exit = main(
        [
            "export",
            "--input",
            str(output_dir / "scored.jsonl"),
            "--output-dir",
            str(export_dir),
            "--format",
            "jsonl",
        ]
    )
    assert export_exit == 0

    validate_exit = main(
        [
            "validate-export",
            "--input",
            str(export_dir / "vibe_check_labels.jsonl"),
        ]
    )
    assert validate_exit == 0
