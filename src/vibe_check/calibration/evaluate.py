"""Golden set evaluation (SPEC-09)."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from vibe_check import __version__
from vibe_check.aggregation.aggregate import get_severity_bucket
from vibe_check.calibration.metrics import (
    compute_accuracy,
    compute_cohens_kappa,
    compute_confusion_matrix,
    compute_quadratic_weighted_kappa,
)
from vibe_check.calibration.schema import AgreementMetrics, CalibrationReport, ClassMetrics
from vibe_check.constants import SEVERITY_BUCKETS

if TYPE_CHECKING:
    from vibe_check.constants import SeverityBucket


def _parse_optional_bool(raw: str | None) -> bool | None:
    if raw is None:
        return None
    value = raw.strip().lower()
    if value in ("", "na", "n/a", "null"):
        return None
    if value in ("true", "t", "1", "yes", "y"):
        return True
    if value in ("false", "f", "0", "no", "n"):
        return False
    raise ValueError(f"Invalid boolean value: {raw!r}")


def _load_system_rows(scored_jsonl: Path) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for line in scored_jsonl.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        raw = json.loads(line)
        if not isinstance(raw, dict):
            raise ValueError("scored.jsonl row is not an object")
        file_id = raw.get("file_id")
        if not isinstance(file_id, str) or not file_id.strip():
            raise ValueError("scored.jsonl row missing required field: file_id")
        rows[file_id] = raw
    if not rows:
        raise ValueError("scored.jsonl is empty")
    return rows


def _severity_bucket_index(bucket: SeverityBucket) -> int:
    order = list(SEVERITY_BUCKETS.keys())
    try:
        return order.index(bucket)
    except ValueError as exc:
        raise ValueError(f"Unknown severity bucket: {bucket!r}") from exc


def _compute_class_metrics(confusion_matrix: list[list[int]]) -> dict[str, ClassMetrics]:
    n = len(confusion_matrix)
    class_metrics: dict[str, ClassMetrics] = {}
    bucket_order = list(SEVERITY_BUCKETS.keys())
    for idx in range(n):
        tp = confusion_matrix[idx][idx]
        fp = sum(confusion_matrix[i][idx] for i in range(n) if i != idx)
        fn = sum(confusion_matrix[idx][j] for j in range(n) if j != idx)
        support = sum(confusion_matrix[idx][j] for j in range(n))

        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
        class_metrics[bucket_order[idx]] = ClassMetrics(
            precision=float(precision),
            recall=float(recall),
            f1=float(f1),
            support=int(support),
        )
    return class_metrics


def evaluate_golden_set(
    *,
    system_scored_jsonl: str | Path,
    human_csv: str | Path,
    sampling_strategy: str = "hybrid",
) -> CalibrationReport:
    """Compute agreement metrics between system outputs and human annotations."""
    system_rows = _load_system_rows(Path(system_scored_jsonl))

    human_path = Path(human_csv)
    annotator_ids: set[str] = set()
    y_true: list[int] = []
    y_pred: list[int] = []
    deltas: list[int] = []

    human_self_harm: dict[str, bool] = {}

    with human_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        required = {"file_id", "annotator_id", "phq8_total"}
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise ValueError("golden_set.csv must include: file_id, annotator_id, phq8_total")

        for row in reader:
            file_id = str(row.get("file_id", "")).strip()
            if not file_id:
                raise ValueError("golden_set.csv row missing file_id")
            annotator = str(row.get("annotator_id", "")).strip()
            if not annotator:
                raise ValueError("golden_set.csv row missing annotator_id")
            annotator_ids.add(annotator)

            raw_total = str(row.get("phq8_total", "")).strip()
            if raw_total == "":
                raise ValueError("golden_set.csv row missing phq8_total")
            human_total = int(raw_total)

            system = system_rows.get(file_id)
            if system is None:
                raise ValueError(f"file_id not found in system scored.jsonl: {file_id}")
            system_total_raw = system.get("final_total_score")
            if not isinstance(system_total_raw, int):
                raise ValueError(f"system row missing final_total_score for {file_id}")
            system_total = int(system_total_raw)

            human_bucket = get_severity_bucket(human_total)
            system_bucket = get_severity_bucket(system_total)
            y_true.append(_severity_bucket_index(human_bucket))
            y_pred.append(_severity_bucket_index(system_bucket))
            deltas.append(system_total - human_total)

            self_harm_raw = row.get("self_harm_flag")
            if self_harm_raw is not None:
                parsed = _parse_optional_bool(self_harm_raw)
                if parsed is not None:
                    human_self_harm[file_id] = parsed

    if not y_true:
        raise ValueError("golden_set.csv has no rows")

    matrix = compute_confusion_matrix(y_true, y_pred, n_classes=len(SEVERITY_BUCKETS))
    agreement = AgreementMetrics(
        cohens_kappa=compute_cohens_kappa(matrix),
        quadratic_weighted_kappa=compute_quadratic_weighted_kappa(matrix),
        accuracy=compute_accuracy(matrix),
        confusion_matrix=matrix,
    )

    per_class = _compute_class_metrics(matrix)

    # Safety: self-harm recall among human positives, if provided.
    positives = [fid for fid, flag in human_self_harm.items() if flag]
    if not positives:
        self_harm_recall = 1.0
    else:
        hits = 0
        for fid in positives:
            system = system_rows[fid]
            if system.get("mentions_self_harm") is True:
                hits += 1
        self_harm_recall = hits / len(positives)

    system_bias = sum(deltas) / len(deltas) if deltas else 0.0

    return CalibrationReport(
        system_version=__version__,
        human_annotator_ids=sorted(annotator_ids),
        sample_size=len(y_true),
        sampling_strategy=sampling_strategy,
        overall_agreement=agreement,
        per_severity_class=per_class,
        self_harm_recall=float(self_harm_recall),
        system_bias=float(system_bias),
    )


def render_confusion_matrix_table(report: CalibrationReport) -> str:
    """Render a compact text confusion matrix for quick CLI feedback."""
    labels = list(SEVERITY_BUCKETS.keys())
    matrix = report.overall_agreement.confusion_matrix
    header = "true\\pred," + ",".join(labels)
    lines = [header]
    for i, label in enumerate(labels):
        lines.append(label + "," + ",".join(str(int(v)) for v in matrix[i]))
    return "\\n".join(lines) + "\\n"
