from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal

from vibe_check.aggregation.aggregate import aggregate_reports
from vibe_check.constants import PHQ8_ITEMS
from vibe_check.diagnostics import RunDiagnostics
from vibe_check.schemas.scoring import PHQ8ItemScore, PHQ8Report, TokenUsage

if TYPE_CHECKING:
    from pathlib import Path


Score = Literal[0, 1, 2, 3]


def _make_uniform_report(*, model_id: str, run_number: int, score: Score) -> PHQ8Report:
    item = PHQ8ItemScore(
        score=score,
        confidence=0.9,
        evidence=["evidence"],
        insufficient_evidence=False,
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
        mentions_self_harm=False,
        self_harm_evidence=[],
        usage=TokenUsage(input_tokens=1, output_tokens=1, reasoning_tokens=0, total_tokens=2),
        scored_at=datetime.now(UTC),
    )


def test_run_diagnostics_compute_passes_on_clean_synthetic_run(tmp_path: Path) -> None:
    scored_path = tmp_path / "scored.jsonl"
    manifest_path = tmp_path / "run_manifest.json"

    model_ids = [
        ("gpt-5.2", 1),
        ("gpt-5.2", 2),
        ("claude-sonnet-4-5-20250929", 1),
        ("claude-sonnet-4-5-20250929", 2),
        ("gemini-3-pro-preview", 1),
        ("gemini-3-pro-preview", 2),
    ]

    rows: list[dict[str, object]] = []
    for i in range(10):
        condition: Literal["mdd", "control"] = "control" if i < 5 else "mdd"
        score: Score = (
            (0 if i % 2 == 0 else 1) if condition == "control" else (2 if i % 2 == 0 else 3)
        )
        reports = [
            _make_uniform_report(model_id=model_id, run_number=run_number, score=score)
            for model_id, run_number in model_ids
        ]
        agg = aggregate_reports(
            reports,
            file_id=f"dialogue_{i:04d}",
            condition=condition,
            prompt_version="v1",
        )
        rows.append(agg.model_dump(mode="json"))

    scored_path.write_text(
        "\n".join(json.dumps(r, sort_keys=True) for r in rows) + "\n", encoding="utf-8"
    )
    manifest_path.write_text(
        json.dumps({"completed": len(rows)}, indent=2) + "\n", encoding="utf-8"
    )

    diagnostics = RunDiagnostics(scored_jsonl=scored_path, run_manifest=manifest_path)
    report = diagnostics.compute()

    assert report.passes_all_gates is True
    assert report.krippendorff_alpha >= 0.80
    assert report.cronbach_alpha >= 0.70
    assert report.mdd_mean_total > report.control_mean_total
    assert report.arbitration_rate < 0.30
