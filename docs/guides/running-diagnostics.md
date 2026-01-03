# Running Diagnostics

Validate scoring quality before exporting labels.

---

## Overview

Diagnostics compute quality metrics and check if the run passes all gates:

| Gate | Metric | Threshold |
|------|--------|-----------|
| Reliability | Krippendorff's α | ≥ 0.67 |
| Consistency | Cronbach's α | ≥ 0.70 |
| Separation | Separation validity | MDD > control, p < 0.01, d ≥ 0.5 |
| Arbitration | Rate | < 30% |

---

## Basic Usage

```bash
uv run vibe-check diagnostics \
    --scored data/outputs/scored.jsonl \
    --output data/outputs/diagnostics.json
```

---

## Strict Mode

Exit with non-zero code if any gate fails:

```bash
uv run vibe-check diagnostics \
    --scored data/outputs/scored.jsonl \
    --output data/outputs/diagnostics.json \
    --strict
```

Use in CI/CD to block bad runs from proceeding.

---

## Output Formats

### JSON (Default)

```bash
uv run vibe-check diagnostics \
    --scored data/outputs/scored.jsonl \
    --output data/outputs/diagnostics.json \
    --format json
```

### Markdown

```bash
uv run vibe-check diagnostics \
    --scored data/outputs/scored.jsonl \
    --output data/outputs/diagnostics.md \
    --format markdown
```

---

## Understanding the Report

### JSON Structure

```json
{
  "run_id": "outputs",
  "n_dialogues": 2090,
  "n_mdd": 912,
  "n_control": 1178,

  "reliability": {
    "krippendorff_alpha": 0.73,
    "krippendorff_alpha_per_item": {
      "anhedonia": 0.71,
      "depressed_mood": 0.78,
      ...
    },
    "icc_consistency": 0.82,
    "icc_agreement": 0.79
  },

  "consistency": {
    "cronbach_alpha": 0.85,
    "item_total_correlations": {
      "anhedonia": 0.65,
      ...
    }
  },

  "separation": {
    "mdd_mean": 12.4,
    "control_mean": 4.8,
    "cohens_d": 1.23,
    "is_valid": true
  },

  "arbitration": {
    "overall_rate": 0.23,
    "per_item_rate": {...},
    "trigger_counts": {...}
  },

  "passes_reliability_gate": true,
  "passes_consistency_gate": true,
  "passes_separation_gate": true,
  "passes_arbitration_gate": true
}
```

---

## Interpreting Results

### Reliability (Krippendorff's α)

| Value | Interpretation |
|-------|----------------|
| ≥ 0.80 | Excellent - jurors strongly agree |
| 0.67-0.80 | Acceptable - proceed with caution |
| < 0.67 | **FAIL** - juror disagreement too high |

**Per-item breakdown** identifies problematic items:
- Low α items may need prompt improvements
- Consider reviewing juror evidence quality

### Consistency (Cronbach's α)

| Value | Interpretation |
|-------|----------------|
| ≥ 0.90 | Excellent internal consistency |
| 0.70-0.90 | Acceptable |
| < 0.70 | **FAIL** - items not measuring same construct |

### Separation

The MDD group should score higher than Control and show clear separation:
- `mdd_mean` typically 10-15
- `control_mean` typically 3-7
- `cohens_d` > 0.8 indicates large effect
- Gate requires: `mdd_mean > control_mean`, `p_value < 0.01`, `cohens_d >= 0.5`

If `is_valid: false`, check:
- Are condition labels correct?
- Is the corpus balanced?

### Arbitration Rate

| Rate | Interpretation |
|------|----------------|
| < 20% | Excellent - strong jury consensus |
| 20-30% | Acceptable |
| > 30% | **FAIL** - too much disagreement |

High arbitration indicates:
- Prompts may need refinement
- Model selection may be suboptimal
- Items may be ambiguous

---

## When Gates Fail

### Reliability Failure

```bash
# Check per-item reliability
cat diagnostics.json | jq '.reliability.krippendorff_alpha_per_item'
```

Identify low-α items and:
1. Review juror prompts for those items
2. Check if evidence extraction is working
3. Consider adding more jurors

### Consistency Failure

```bash
# Check item-total correlations
cat diagnostics.json | jq '.consistency.item_total_correlations'
```

Low correlations indicate items scored inconsistently.

### Separation Failure

```bash
# Check separation metrics
cat diagnostics.json | jq '{mdd: .separation.mdd_mean, control: .separation.control_mean, d: .separation.cohens_d, p: .separation.p_value, is_valid: .separation.is_valid}'
```

If means are reversed:
- Verify corpus condition labels
- Check for data corruption

### Arbitration Failure

```bash
# Check per-item rates
cat diagnostics.json | jq '.arbitration.per_item_rate'
```

High-rate items need attention:
- Review arbitration triggers
- Consider threshold adjustments

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | All gates passed |
| 2 | At least one gate failed (with `--strict`) |

---

## Next Steps

If all gates pass:
- [Export Labels](exporting-labels.md) - Create public format

If gates fail:
- Review the failing metrics
- Adjust prompts or thresholds
- Re-run scoring
