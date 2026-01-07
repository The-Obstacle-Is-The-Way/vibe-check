from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal

from vibe_check.aggregation.aggregate import aggregate_reports
from vibe_check.cli import main
from vibe_check.constants import PHQ8_ITEMS
from vibe_check.schemas.scoring import PHQ8ItemScore, PHQ8Report, TokenUsage

if TYPE_CHECKING:
    from pathlib import Path


Score = Literal[0, 1, 2, 3]


def _make_uniform_report(*, model_id: str, run_number: int, score: Score) -> PHQ8Report:
    if score == 0:
        item = PHQ8ItemScore(
            discussed=True,
            score=0,
            assertion="denied",
            confidence=0.9,
            evidence=["evidence"],
        )
    else:
        item = PHQ8ItemScore(
            discussed=True,
            score=score,
            assertion="present",
            confidence=0.9,
            evidence=["evidence"],
        )
    return PHQ8Report(
        model_id=model_id,
        run_number=run_number,
        anhedonia=item,
        depressed_mood=item,
        sleep=item,
        fatigue=item,
        appetite=item,
        guilt=item,
        concentration=item,
        psychomotor=item,
        total_score=int(score) * len(PHQ8_ITEMS),
        discussed_count=len(PHQ8_ITEMS),
        mentions_self_harm=False,
        self_harm_evidence=[],
        usage=TokenUsage(input_tokens=1, output_tokens=1, reasoning_tokens=0, total_tokens=2),
        scored_at=datetime.now(UTC),
    )


def test_cli_export_and_validate_export(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    scored_path = run_dir / "scored.jsonl"

    model_ids = [
        ("gpt-5.2", 1),
        ("gpt-5.2", 2),
        ("claude-sonnet-4-5-20250929", 1),
        ("claude-sonnet-4-5-20250929", 2),
        ("gemini-3-pro-preview", 1),
        ("gemini-3-pro-preview", 2),
    ]

    reports = [
        _make_uniform_report(model_id=model_id, run_number=run_number, score=1)
        for model_id, run_number in model_ids
    ]
    agg = aggregate_reports(
        reports,
        file_id="dialogue_0001",
        condition="control",
        prompt_version="v1.0.0",
    )
    row = agg.model_dump(mode="json")
    row["computed_split"] = "train"
    row["dialogue_view"] = "client_qa"
    row["scoring_text"] = "Therapist: Hi\\nClient: OK."

    scored_path.write_text(json.dumps(row) + "\n", encoding="utf-8")

    export_dir = run_dir / "export"
    exit_code = main(
        [
            "export",
            "--input",
            str(scored_path),
            "--output-dir",
            str(export_dir),
            "--format",
            "jsonl,csv",
        ]
    )
    assert exit_code == 0
    assert (export_dir / "vibe_check_labels.jsonl").exists()
    assert (export_dir / "vibe_check_labels.csv").exists()
    assert (export_dir / "validation_report.json").exists()

    validate_code = main(
        [
            "validate-export",
            "--input",
            str(export_dir / "vibe_check_labels.jsonl"),
        ]
    )
    assert validate_code == 0


def test_cli_export_csv_only_does_not_crash(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    scored_path = run_dir / "scored.jsonl"

    model_ids = [
        ("gpt-5.2", 1),
        ("gpt-5.2", 2),
        ("claude-sonnet-4-5-20250929", 1),
        ("claude-sonnet-4-5-20250929", 2),
        ("gemini-3-pro-preview", 1),
        ("gemini-3-pro-preview", 2),
    ]

    reports = [
        _make_uniform_report(model_id=model_id, run_number=run_number, score=1)
        for model_id, run_number in model_ids
    ]
    agg = aggregate_reports(
        reports,
        file_id="dialogue_0001",
        condition="control",
        prompt_version="v1.0.0",
    )
    row = agg.model_dump(mode="json")
    row["computed_split"] = "train"
    row["dialogue_view"] = "client_qa"
    row["scoring_text"] = "Therapist: Hi\\nClient: OK."

    scored_path.write_text(json.dumps(row) + "\n", encoding="utf-8")

    export_dir = run_dir / "export_csv_only"
    exit_code = main(
        [
            "export",
            "--input",
            str(scored_path),
            "--output-dir",
            str(export_dir),
            "--format",
            "csv",
        ]
    )
    assert exit_code == 0
    # JSONL is always written (canonical contract), even when --format csv
    assert (export_dir / "vibe_check_labels.jsonl").exists()
    assert (export_dir / "vibe_check_labels.csv").exists()
    assert (export_dir / "validation_report.json").exists()
