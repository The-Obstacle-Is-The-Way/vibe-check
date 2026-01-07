"""NA-aware HuggingFace export writer (SPEC-16)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal, cast

from vibe_check.constants import PHQ8_ITEMS
from vibe_check.export.huggingface_schema import (
    HuggingFaceDialogueExport,
    HuggingFaceItemExport,
    HuggingFaceMetadataExport,
    HuggingFaceTotalsExport,
    Split,
)
from vibe_check.schemas.output import AggregatedPHQ8


def write_huggingface_export(
    *,
    scored_jsonl: str | Path,
    output_dir: str | Path,
    run_manifest: str | Path | None = None,
) -> None:
    """Write NA-aware HuggingFace export JSONL (separate from SPEC-08)."""
    scored_path = Path(scored_jsonl)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = (
        Path(run_manifest)
        if run_manifest is not None
        else scored_path.with_name("run_manifest.json")
    )
    judge_model: str | None = None
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        run_cfg = manifest.get("run_config") if isinstance(manifest, dict) else None
        if isinstance(run_cfg, dict):
            judge_model = cast(
                "str | None", run_cfg.get("judge_model") or run_cfg.get("judge_model_id")
            )
            judge_item = run_cfg.get("judge_item")
            if judge_model is None and isinstance(judge_item, dict):
                judge_model = cast("str | None", judge_item.get("model_id"))

    exports: list[HuggingFaceDialogueExport] = []
    for line in scored_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        raw: dict[str, Any] = json.loads(line)

        split = raw.get("computed_split")
        if split not in ("train", "dev", "test"):
            raise ValueError(f"computed_split must be train/dev/test, got {split!r}")

        filtered = {k: raw[k] for k in AggregatedPHQ8.model_fields if k in raw}
        aggregated = AggregatedPHQ8.model_validate(filtered)

        exports.append(
            _aggregated_to_record(
                aggregated,
                split=cast("Split", split),
                judge_model=judge_model,
            )
        )

    exports.sort(key=lambda r: r.dialogue_id)

    output_path = out_dir / "vibe_check_labels_huggingface.jsonl"
    output_path.write_text(
        "\n".join(json.dumps(e.model_dump(mode="json"), sort_keys=True) for e in exports) + "\n",
        encoding="utf-8",
    )


def _aggregated_to_record(
    aggregated: AggregatedPHQ8,
    *,
    split: Split,
    judge_model: str | None,
) -> HuggingFaceDialogueExport:
    juror_models = sorted({r.model_id for r in aggregated.juror_reports})
    runs_per_model = max(r.run_number for r in aggregated.juror_reports)
    expected_runs = set(range(1, runs_per_model + 1))
    for model_id in juror_models:
        runs = {r.run_number for r in aggregated.juror_reports if r.model_id == model_id}
        if runs != expected_runs:
            raise ValueError(f"inconsistent runs for model_id={model_id!r}: {sorted(runs)}")

    metadata = HuggingFaceMetadataExport(
        prompt_version=aggregated.prompt_version,
        juror_models=juror_models,
        runs_per_model=runs_per_model,
        arbitration_triggered=bool(aggregated.triggered_arbitration),
        judge_model=judge_model if aggregated.triggered_arbitration else None,
    )

    items: dict[str, HuggingFaceItemExport] = {}
    judge_map = aggregated.judge_resolution or {}

    for item in PHQ8_ITEMS:
        if item in judge_map:
            resolution = judge_map[item]
            if not isinstance(resolution, dict):
                raise ValueError(f"judge_resolution[{item!r}] must be a dict")

            assertion_raw = resolution.get("assertion")
            if assertion_raw not in ("present", "denied", "possible", "not_mentioned"):
                raise ValueError(f"invalid judge assertion for item={item!r}: {assertion_raw!r}")
            judge_assertion = cast(
                "Literal['present', 'denied', 'possible', 'not_mentioned']",
                assertion_raw,
            )

            score_raw = resolution.get("final_score")
            if score_raw is not None and score_raw not in (0, 1, 2, 3):
                raise ValueError(f"invalid judge score for item={item!r}: {score_raw!r}")
            judge_score = cast("Literal[0, 1, 2, 3] | None", score_raw)

            confidence = cast("float | None", resolution.get("confidence"))

            evidence_raw = resolution.get("evidence") or []
            if not isinstance(evidence_raw, list) or any(
                not isinstance(e, str) for e in evidence_raw
            ):
                raise ValueError(f"invalid judge evidence for item={item!r}")
            evidence = cast("list[str]", evidence_raw)

            items[item] = HuggingFaceItemExport(
                assertion=judge_assertion,
                score=judge_score,
                confidence=confidence,
                evidence=evidence,
            )
            continue

        item_agg = aggregated.items[item]
        consensus_assertion = item_agg.consensus_assertion
        consensus_score_raw = item_agg.consensus_score

        if consensus_assertion == "not_mentioned":
            items[item] = HuggingFaceItemExport(
                assertion="not_mentioned",
                score=None,
                confidence=None,
                evidence=[],
            )
            continue

        candidates: list[tuple[float, str, int, list[str]]] = []
        for r in aggregated.juror_reports:
            juror_item = getattr(r, item)
            if (
                juror_item.assertion == consensus_assertion
                and juror_item.score == consensus_score_raw
            ):
                if juror_item.confidence is None:
                    continue
                candidates.append(
                    (
                        float(juror_item.confidence),
                        r.model_id,
                        int(r.run_number),
                        juror_item.evidence,
                    )
                )
        if not candidates:
            raise ValueError(
                f"no juror candidates for item={item!r} consensus=({consensus_assertion!r}, {consensus_score_raw!r})"
            )

        candidates.sort(key=lambda x: (-x[0], x[1], x[2]))
        best_confidence, _, _, best_evidence = candidates[0]
        if consensus_score_raw is None:
            raise ValueError(f"unexpected None score for non-NA consensus item={item!r}")
        if consensus_score_raw not in (0, 1, 2, 3):
            raise ValueError(
                f"unexpected out-of-range consensus_score for item={item!r}: {consensus_score_raw!r}"
            )
        consensus_score = cast("Literal[0, 1, 2, 3]", consensus_score_raw)

        items[item] = HuggingFaceItemExport(
            assertion=consensus_assertion,
            score=consensus_score,
            confidence=best_confidence,
            evidence=list(best_evidence),
        )

    totals = HuggingFaceTotalsExport(**aggregated.totals.model_dump())

    return HuggingFaceDialogueExport(
        dialogue_id=aggregated.file_id,
        condition=aggregated.condition,
        split=split,
        items=items,
        totals=totals,
        scoring_metadata=metadata,
    )
