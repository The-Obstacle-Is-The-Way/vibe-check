from __future__ import annotations

import json
from typing import TYPE_CHECKING

from tests.fixtures.sample_votes import create_mock_report

from vibe_check.aggregation.aggregate import aggregate_reports
from vibe_check.export.validator import validate_label_export
from vibe_check.export.writer import aggregated_to_export_record

if TYPE_CHECKING:
    from pathlib import Path


def test_aggregated_to_export_record_maps_scores_and_votes() -> None:
    agg = aggregate_reports(
        [create_mock_report(i) for i in range(6)],
        file_id="dialogue_0001",
        condition="mdd",
        prompt_version="v1.0.0",
    )

    record = aggregated_to_export_record(
        agg,
        scoring_text="Therapist: Hello\\nClient: I'm sad.",
        dialogue_view="client_qa",
        run_id="run",
    )

    assert record.dialogue_id == agg.file_id
    assert record.condition == agg.condition
    assert record.phq8_total == agg.final_total_score
    assert record.severity_bucket == agg.final_severity_bucket
    assert record.client_qa_text.startswith("Therapist:")
    assert set(record.juror_votes.keys()) == set(agg.final_item_scores.keys())
    assert all(len(v) == len(agg.juror_reports) for v in record.juror_votes.values())
    assert record.prompt_version == agg.prompt_version


def test_validate_label_export_round_trip(tmp_path: Path) -> None:
    agg = aggregate_reports(
        [create_mock_report(i) for i in range(6)],
        file_id="dialogue_0002",
        condition="control",
        prompt_version="v1.0.0",
    )
    record = aggregated_to_export_record(
        agg,
        scoring_text="Therapist: Hi\\nClient: OK.",
        dialogue_view="client_qa",
        run_id="run",
    )

    export_path = tmp_path / "vibe_check_labels.jsonl"
    export_path.write_text(json.dumps(record.model_dump(mode="json")) + "\n", encoding="utf-8")

    report = validate_label_export(export_path)
    assert report.is_valid is True
    assert report.n_dialogues == 1
    assert report.records[0].dialogue_id == "dialogue_0002"
