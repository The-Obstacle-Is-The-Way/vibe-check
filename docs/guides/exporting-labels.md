# Exporting Labels

Create public label files from scored data.

---

## Overview

The export command transforms internal `scored.jsonl` to a public format:
- Flattens nested structures
- Adds scoring text for embeddings
- Removes internal-only fields

---

## Basic Usage

```bash
uv run vibe-check export \
    --input data/outputs/scored.jsonl \
    --output-dir data/exports
```

This creates:
- `vibe_check_labels.jsonl`
- `vibe_check_labels.csv`

---

## Output Formats

### JSONL Only

```bash
uv run vibe-check export \
    --input data/outputs/scored.jsonl \
    --output-dir data/exports \
    --format jsonl
```

### CSV Only

```bash
uv run vibe-check export \
    --input data/outputs/scored.jsonl \
    --output-dir data/exports \
    --format csv
```

### Both (Default)

```bash
uv run vibe-check export \
    --input data/outputs/scored.jsonl \
    --output-dir data/exports \
    --format jsonl,csv
```

---

## Export Schema

Each record in the export:

```json
{
  "dialogue_id": "active436",
  "condition": "mdd",
  "phq8_item_1": 2,
  "phq8_item_2": 3,
  "phq8_item_3": 2,
  "phq8_item_4": 1,
  "phq8_item_5": 2,
  "phq8_item_6": 3,
  "phq8_item_7": 1,
  "phq8_item_8": 1,
  "phq8_total": 15,
  "severity_bucket": "15-19",
  "client_qa_text": "Therapist: How have you been...\nClient: Not well...",
  "juror_votes": {
    "anhedonia": [1, 2, 1, 2, 1, 2],
    "depressed_mood": [2, 3, 2, 2, 2, 3],
    ...
  },
  "arbitration_triggered": {
    "anhedonia": false,
    "depressed_mood": true,
    ...
  },
  "run_id": "2026-01-03_production",
  "prompt_version": "v1.0.0"
}
```

### Field Mapping

| Export Field | Source | Description |
|--------------|--------|-------------|
| `dialogue_id` | `file_id` | Unique identifier |
| `condition` | `condition` | "mdd" or "control" |
| `phq8_item_1..8` | `final_item_scores` | Final scores (0-3) |
| `phq8_total` | `final_total_score` | Total (0-24) |
| `severity_bucket` | `final_severity_bucket` | Severity classification |
| `client_qa_text` | Preprocessing | Scoring text for embeddings |
| `juror_votes` | `juror_reports` | All 6 juror votes per item |
| `arbitration_triggered` | `triggered_arbitration` + items | Per-item arbitration flags (dict) |
| `run_id` | `scored.jsonl` parent directory name | Run identifier |
| `prompt_version` | `prompt_version` | Prompt version label |

---

## Validating Exports

After export, validate the output:

```bash
uv run vibe-check validate-export \
    --input data/exports/vibe_check_labels.jsonl
```

This:
1. Parses every record
2. Validates against schema
3. Checks for duplicates
4. Writes `validation_report.json`

### Validation Report

```json
{
  "is_valid": true,
  "total_records": 2090,
  "valid_records": 2090,
  "invalid_records": 0,
  "duplicate_ids": []
}
```

---

## Using Exports

### For ai-psychiatrist

The export format is designed for few-shot retrieval:

```python
import json

# Load labels
with open("vibe_check_labels.jsonl") as f:
    labels = [json.loads(line) for line in f]

# Filter by condition
mdd_cases = [l for l in labels if l["condition"] == "mdd"]

# Get high-severity cases
severe = [l for l in labels if l["phq8_total"] >= 15]

# Use client_qa_text for embeddings
texts = [l["client_qa_text"] for l in labels]
```

### CSV for Analysis

```python
import pandas as pd

df = pd.read_csv("vibe_check_labels.csv")

# Condition distribution
print(df["condition"].value_counts())

# Mean by condition
print(df.groupby("condition")["phq8_total"].mean())

# Item correlations
items = [f"phq8_item_{i}" for i in range(1, 9)]
print(df[items].corr())
```

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Export successful, validation passed |
| 2 | Validation failed |

---

## Troubleshooting

### Empty Export

Check that `scored.jsonl` has records:

```bash
wc -l data/outputs/scored.jsonl
```

### Missing Fields

Ensure all required fields are present:

```bash
head -1 data/outputs/scored.jsonl | python -m json.tool | grep -E "final_|file_id|condition"
```

### Validation Failures

Check the validation report:

```bash
cat data/exports/validation_report.json | python -m json.tool
```
