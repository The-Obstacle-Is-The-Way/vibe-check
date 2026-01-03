"""Export writer for producing stable public label files (SPEC-08)."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Literal

from vibe_check.constants import PHQ8_ITEMS
from vibe_check.export.schemas import ScoredDialogueExport
from vibe_check.export.validator import ExportValidationReport, validate_label_export
from vibe_check.schemas.output import AggregatedPHQ8

DialogueViewName = Literal["client_qa", "client_only"]


def aggregated_to_export_record(
    aggregated: AggregatedPHQ8,
    *,
    scoring_text: str,
    dialogue_view: DialogueViewName,
    run_id: str,
) -> ScoredDialogueExport:
    """Transform an internal AggregatedPHQ8 record into the public export schema."""
    if dialogue_view != "client_qa":
        raise ValueError("Export contract requires dialogue_view='client_qa'")

    final_items = aggregated.final_item_scores
    votes: dict[str, list[int]] = {}
    for item in PHQ8_ITEMS:
        votes[item] = [int(getattr(r, item).score) for r in aggregated.juror_reports]

    arbitration_triggered = dict.fromkeys(PHQ8_ITEMS, False)
    if "__total__" in aggregated.arbitration_items:
        arbitration_triggered = dict.fromkeys(PHQ8_ITEMS, True)
    else:
        for item in aggregated.arbitration_items:
            if item in arbitration_triggered:
                arbitration_triggered[item] = True

    return ScoredDialogueExport(
        dialogue_id=aggregated.file_id,
        condition=aggregated.condition,
        phq8_item_1=int(final_items["anhedonia"]),
        phq8_item_2=int(final_items["depressed_mood"]),
        phq8_item_3=int(final_items["sleep"]),
        phq8_item_4=int(final_items["fatigue"]),
        phq8_item_5=int(final_items["appetite"]),
        phq8_item_6=int(final_items["guilt"]),
        phq8_item_7=int(final_items["concentration"]),
        phq8_item_8=int(final_items["psychomotor"]),
        phq8_total=int(aggregated.final_total_score),
        severity_bucket=aggregated.final_severity_bucket,
        client_qa_text=scoring_text,
        juror_votes=votes,
        arbitration_triggered=arbitration_triggered,
        run_id=run_id,
        prompt_version=aggregated.prompt_version,
    )


def write_label_exports(
    *,
    scored_jsonl: str | Path,
    output_dir: str | Path,
    formats: set[str],
) -> ExportValidationReport:
    """Write `vibe_check_labels.jsonl` and optional `vibe_check_labels.csv`, then validate JSONL."""
    scored_path = Path(scored_jsonl)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    run_id = scored_path.parent.name or "run"

    records: list[ScoredDialogueExport] = []
    for line in scored_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        raw: dict[str, Any] = json.loads(line)
        scoring_text = raw.get("scoring_text")
        dialogue_view = raw.get("dialogue_view")
        if not isinstance(scoring_text, str) or not scoring_text.strip():
            raise ValueError("Missing required scoring_text in scored.jsonl row")
        if dialogue_view not in ("client_qa", "client_only"):
            raise ValueError("Missing required dialogue_view in scored.jsonl row")

        filtered = {k: raw[k] for k in AggregatedPHQ8.model_fields if k in raw}
        agg = AggregatedPHQ8.model_validate(filtered)
        records.append(
            aggregated_to_export_record(
                agg,
                scoring_text=scoring_text,
                dialogue_view=dialogue_view,
                run_id=run_id,
            )
        )

    records.sort(key=lambda r: r.dialogue_id)

    jsonl_path = out_dir / "vibe_check_labels.jsonl"
    csv_path = out_dir / "vibe_check_labels.csv"

    # JSONL is the public contract and the target of schema validation; always write it.
    jsonl_path.write_text(
        "\n".join(json.dumps(r.model_dump(mode="json"), sort_keys=True) for r in records) + "\n",
        encoding="utf-8",
    )

    if "csv" in formats:
        fieldnames = [
            "dialogue_id",
            "condition",
            "phq8_item_1",
            "phq8_item_2",
            "phq8_item_3",
            "phq8_item_4",
            "phq8_item_5",
            "phq8_item_6",
            "phq8_item_7",
            "phq8_item_8",
            "phq8_total",
            "severity_bucket",
            "client_qa_text",
            "run_id",
            "prompt_version",
        ]
        with csv_path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in records:
                writer.writerow({k: getattr(r, k) for k in fieldnames})

    validation = validate_label_export(jsonl_path)
    (out_dir / "validation_report.json").write_text(
        validation.model_dump_json(indent=2, exclude={"records"}) + "\n",
        encoding="utf-8",
    )
    return validation
