from __future__ import annotations

import json
from typing import TYPE_CHECKING

from tests.fixtures.hf_disk_dataset import write_sqpsychconv_like_dataset

from vibe_check.cli import main
from vibe_check.run.ledger import JobLedger

if TYPE_CHECKING:
    from pathlib import Path

    from _pytest.monkeypatch import MonkeyPatch


def _clear_settings_env(monkeypatch: MonkeyPatch) -> None:
    # Settings reads from env + `.env` by default. Keep this test hermetic.
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
        "EMBEDDING_DIALOGUE_VIEW",
        "MAX_CONCURRENT_DIALOGUES",
        "OPENAI_RPM",
        "ANTHROPIC_RPM",
        "GOOGLE_RPM",
        "MAX_RETRIES",
        "RETRY_INITIAL_WAIT",
        "RETRY_MAX_WAIT",
        "RETRY_JITTER",
        "VALIDATION_RETRIES",
        "CHECKPOINT_DB",
        "OUTPUT_DIR",
        "PROMPT_VERSION",
    ]:
        monkeypatch.delenv(key, raising=False)


def test_cli_score_corpus_end_to_end_fake_mode(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    _clear_settings_env(monkeypatch)
    dataset_dir = write_sqpsychconv_like_dataset(tmp_path, n_train=4, n_test=0)
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
            "4",
            "--prompt-version",
            "v1.0.0",
            "--dialogue-view",
            "client_qa",
            "--max-concurrency",
            "1",
        ]
    )
    assert exit_code == 0

    assert (output_dir / "ledger.sqlite").exists()
    assert (output_dir / "rows").is_dir()
    assert (output_dir / "scored.jsonl").exists()
    assert (output_dir / "run_manifest.json").exists()
    assert checkpoint_db.exists()

    lines = (output_dir / "scored.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 4
    first = json.loads(lines[0])
    assert first["dialogue_view"] == "client_qa"
    assert isinstance(first["final_total_score"], int)

    with JobLedger(output_dir / "ledger.sqlite") as ledger:
        assert len(ledger.list_all()) == 4
        assert all(ledger.get_status(fid) == "done" for fid in ledger.list_all())

    diagnostics_out = output_dir / "diagnostics.json"
    diag_exit = main(
        [
            "diagnostics",
            "--scored",
            str(output_dir / "scored.jsonl"),
            "--output",
            str(diagnostics_out),
            "--format",
            "json",
        ]
    )
    assert diag_exit == 0
    payload = json.loads(diagnostics_out.read_text(encoding="utf-8"))
    assert payload["run_id"] == "run"

    export_dir = output_dir / "export"
    export_exit = main(
        [
            "export",
            "--input",
            str(output_dir / "scored.jsonl"),
            "--output-dir",
            str(export_dir),
            "--format",
            "jsonl,csv",
        ]
    )
    assert export_exit == 0
    assert (export_dir / "vibe_check_labels.jsonl").exists()
    assert (export_dir / "vibe_check_labels.csv").exists()
    assert (export_dir / "validation_report.json").exists()

    validate_exit = main(
        [
            "validate-export",
            "--input",
            str(export_dir / "vibe_check_labels.jsonl"),
        ]
    )
    assert validate_exit == 0
