from __future__ import annotations

import csv
import json
from typing import TYPE_CHECKING

import pytest
from tests.fixtures.hf_disk_dataset import write_sqpsychconv_like_dataset

from vibe_check.cli import main

if TYPE_CHECKING:
    from pathlib import Path

    from _pytest.monkeypatch import MonkeyPatch


def _clear_settings_env(monkeypatch: MonkeyPatch) -> None:
    for key in [
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "GOOGLE_API_KEY",
        "GEMINI_API_KEY",
        "JUROR_GPT_MODEL",
        "JUROR_CLAUDE_MODEL",
        "JUROR_GEMINI_MODEL",
        "JUDGE_MODEL",
        "RUNS_PER_MODEL",
        "DISAGREEMENT_RANGE_THRESHOLD",
        "ARBITRATION_TOTAL_STD_THRESHOLD",
        "ARBITRATION_MAX_PROB_THRESHOLD",
        "ARBITRATION_ENTROPY_THRESHOLD",
        "CLINICAL_AMBIGUITY_BAND_LOW",
        "CLINICAL_AMBIGUITY_BAND_HIGH",
        "INSUFFICIENT_EVIDENCE_THRESHOLD",
        "DIRICHLET_ALPHA",
        "SCORING_DIALOGUE_VIEW",
        "MAX_CONCURRENT_DIALOGUES",
        "OPENAI_RPM",
        "ANTHROPIC_RPM",
        "GOOGLE_RPM",
        "MAX_RETRIES",
        "RETRY_INITIAL_WAIT",
        "RETRY_MAX_WAIT",
        "RETRY_JITTER",
        "VALIDATION_RETRIES",
        "GRAPH_RECURSION_LIMIT",
        "CHECKPOINT_DB",
        "OUTPUT_DIR",
        "PROMPT_VERSION",
        "LLM_TEMPERATURE",
        "LLM_TOP_P",
        "LLM_MAX_TOKENS",
        "LLM_TIMEOUT",
        "LLM_SEED",
    ]:
        monkeypatch.delenv(key, raising=False)


@pytest.mark.integration
def test_cli_calibration_sample_then_evaluate(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    _clear_settings_env(monkeypatch)

    dataset_dir = write_sqpsychconv_like_dataset(tmp_path, n_train=6, n_test=0)
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
            "6",
            "--prompt-version",
            "v1.0.0",
            "--dialogue-view",
            "client_qa",
            "--max-concurrency",
            "1",
        ]
    )
    assert exit_code == 0

    scored_path = output_dir / "scored.jsonl"
    assert scored_path.exists()

    sample_path = tmp_path / "to_annotate.csv"
    sample_exit = main(
        [
            "calibration",
            "sample",
            "--scored",
            str(scored_path),
            "--n",
            "4",
            "--seed",
            "123",
            "--output",
            str(sample_path),
        ]
    )
    assert sample_exit == 0
    assert sample_path.exists()

    # Deterministic sampling with the same seed.
    sample_path_2 = tmp_path / "to_annotate_2.csv"
    sample_exit_2 = main(
        [
            "calibration",
            "sample",
            "--scored",
            str(scored_path),
            "--n",
            "4",
            "--seed",
            "123",
            "--output",
            str(sample_path_2),
        ]
    )
    assert sample_exit_2 == 0
    assert sample_path.read_text(encoding="utf-8") == sample_path_2.read_text(encoding="utf-8")

    system_rows = {
        row["file_id"]: row
        for row in (
            json.loads(line) for line in scored_path.read_text(encoding="utf-8").splitlines()
        )
        if row.get("file_id")
    }
    assert system_rows

    filled_path = tmp_path / "golden.csv"
    with (
        sample_path.open("r", encoding="utf-8", newline="") as f_in,
        filled_path.open("w", encoding="utf-8", newline="") as f_out,
    ):
        reader = csv.DictReader(f_in)
        assert reader.fieldnames is not None
        writer = csv.DictWriter(f_out, fieldnames=reader.fieldnames)
        writer.writeheader()
        for row in reader:
            file_id = str(row["file_id"])
            system = system_rows[file_id]
            row["annotator_id"] = "test"
            row["phq8_total"] = str(int(system["final_total_score"]))
            writer.writerow(row)

    report_path = tmp_path / "calibration_report.json"
    eval_exit = main(
        [
            "calibration",
            "evaluate",
            "--system",
            str(scored_path),
            "--human",
            str(filled_path),
            "--output",
            str(report_path),
        ]
    )
    assert eval_exit == 0
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["sample_size"] == 4
    assert payload["overall_agreement"]["accuracy"] == 1.0
    assert payload["overall_agreement"]["cohens_kappa"] == 1.0
    assert payload["overall_agreement"]["quadratic_weighted_kappa"] == 1.0
