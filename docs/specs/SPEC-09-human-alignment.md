# SPEC-09: Human-in-the-Loop Calibration (Golden Set)

**Status**: PLANNED
**Slice Type**: Vertical (Validation Pipeline)
**Dependencies**: SPEC-07 (Run Diagnostics), SPEC-08 (Export)
**Priority**: CRITICAL (Scientific Validity)

---

## 1. Objective

To validate that the `vibe-check` consensus engine aligns with human expert judgment. While internal consistency (Cronbach's α) and inter-rater reliability (Krippendorff's α) measure the *stability* of the system, they do not measure *correctness*.

This specification defines the infrastructure to:
1.  **Stratify & Sample**: Select high-signal dialogues (both random and high-uncertainty) for human review.
2.  **Ingest**: Load human "Golden Set" labels from an external source.
3.  **Calibrate**: Compute rigorous agreement metrics (Cohen's Kappa, F1, Confusion Matrices) between the AI Jury/Judge and the Human Expert.

> **Data Governance Note**: This tool processes human labels provided at runtime. It does **not** store real clinical data or restricted PHI within the repository. The "Golden Set" is an external artifact.

---

## 2. Methodology

### 2.1 Sampling Strategy

We employ a **hybrid sampling strategy** to maximize the information gain from expensive human annotation effort.

*   **Random Slice (50%)**: Establishes baseline performance and unbiased error rates.
*   **Uncertainty Slice (50%)**: Targets dialogues where the model struggled. Selection criteria:
    *   **High Entropy**: `mean(item_entropy) > 1.0`
    *   **Arbitrated**: Dialogues that triggered the Judge.
    *   **Disagreement**: `max(juror_score) - min(juror_score) >= 2`

### 2.2 Metrics

| Metric | Purpose | Target |
|--------|---------|--------|
| **Cohen's Kappa (κ)** | Chance-corrected agreement (Human vs. System Final) | > 0.60 (Good) |
| **Quadratic Weighted Kappa** | Penalizes large errors (e.g., 0 vs 3) more than small ones (1 vs 2) | > 0.70 |
| **F1-Macro** | Balanced accuracy across severity buckets | > 0.70 |
| **Recall (Self-Harm)** | Safety check: did we catch what the human caught? | 1.0 (Critical) |

---

## 3. Architecture & Schemas

### 3.1 Golden Set Input Schema (`golden_set.csv`)

The system must ingest a simple CSV format produced by human annotators (e.g., from a spreadsheet or annotation tool).

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| `file_id` | str | Yes | Matches `vibe-check` file_id |
| `annotator_id` | str | Yes | ID of the human expert |
| `phq8_total` | int | Yes | 0-24 |
| `phq8_item_1`...`8` | int | No | 0-3 (Optional item-level granularity) |
| `self_harm_flag` | bool | No | TRUE/FALSE |
| `notes` | str | No | Free text justification |

### 3.2 Calibration Report Schema

```python
from pydantic import BaseModel

class ClassMetrics(BaseModel):
    precision: float
    recall: float
    f1: float
    support: int

class AgreementMetrics(BaseModel):
    cohens_kappa: float
    quadratic_weighted_kappa: float
    accuracy: float
    confusion_matrix: list[list[int]]  # 5x5 for severity buckets

class CalibrationReport(BaseModel):
    # Meta
    system_version: str
    human_annotator_ids: list[str]
    sample_size: int
    sampling_strategy: str

    # Performance
    overall_agreement: AgreementMetrics
    per_severity_class: dict[str, ClassMetrics]

    # Safety
    self_harm_recall: float  # Human True -> System True / Human True

    # Drift
    system_bias: float  # Mean(System) - Mean(Human)
```

---

## 4. Implementation Details

### 4.1 CLI Commands

#### `vibe-check calibration sample`
Extracts dialogues for human review.

```bash
vibe-check calibration sample \
    --scored data/outputs/scored.jsonl \
    --n 50 \
    --strategy hybrid \
    --output data/calibration/to_annotate.csv
```

**Logic**:
1. Load `scored.jsonl`.
2. Filter valid records.
3. Sort by entropy (descending) for the "Active Learning" half.
4. Randomly sample the rest.
5. Export CSV with columns pre-filled with `file_id` and empty score columns.

#### `vibe-check calibration evaluate`
Compares system output against the filled Golden Set.

```bash
vibe-check calibration evaluate \
    --system data/outputs/scored.jsonl \
    --human data/calibration/golden_set_filled.csv \
    --output data/reports/human_alignment.json
```

**Logic**:
1. Join System and Human datasets on `file_id`.
2. Compute `sklearn.metrics.cohen_kappa_score` (linear and quadratic).
3. Compute Confusion Matrix.
4. Render Markdown report to stdout and JSON to file.

---

## 5. Acceptance Criteria

1.  **Ingestion Robustness**: Must gracefully handle missing item-level scores in the CSV (falling back to Total Score comparison only).
2.  **Safety Gate**: If `self_harm_recall < 1.0` (System missed a flag Human caught), the command must exit with a non-zero code.
3.  **Visual Output**: The CLI should print a text-based Confusion Matrix table for immediate feedback.
4.  **Reproducibility**: The `sample` command must accept a `--seed` for deterministic sampling.

---

## 6. Testing Strategy

*   **Unit Tests**:
    *   Test metric calculations against known vectors (e.g., perfect agreement = 1.0).
    *   Test CSV parsing with malformed rows.
*   **Integration Tests**:
    *   End-to-end flow: Sample -> (Mock Annotate) -> Evaluate.

## 7. Anti-Patterns

*   **Overfitting**: Do not use the Golden Set to "train" the prompts directly in the loop. This is a *validation* set, not a training set.
*   **PHI Leakage**: Do not include transcript text in the `calibration_report.json` output, only IDs and Scores.
