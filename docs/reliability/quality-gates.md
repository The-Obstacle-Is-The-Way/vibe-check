# Quality Gates

Quality gates validate that the scoring run meets statistical thresholds before labels are exported. They detect problems with juror agreement, internal consistency, and clinical validity.

---

## Overview

After scoring completes, diagnostics compute:

| Gate | Metric | Threshold | Purpose |
|------|--------|-----------|---------|
| **Reliability** | Krippendorff's α | ≥ 0.67 | Jurors agree with each other |
| **Consistency** | Cronbach's α | ≥ 0.70 | PHQ-8 items correlate internally |
| **Separation** | MDD mean > Control mean | True | Scores differentiate conditions |
| **Arbitration** | Rate < 30% | True | Not too many disagreements |

All gates must pass before export is considered valid.

---

## Reliability Gate

**Metric**: Krippendorff's Alpha (α)

Measures **inter-rater reliability**—how much jurors agree with each other.

### How It Works

```
For each item across all dialogues:
  - Collect all juror votes (6 votes per dialogue)
  - Compute agreement accounting for chance
  - α = 1.0 means perfect agreement
  - α = 0.0 means chance-level agreement
```

### Thresholds

| α Value | Interpretation |
|---------|----------------|
| ≥ 0.80 | Excellent agreement |
| ≥ 0.67 | **Acceptable** (gate threshold) |
| ≥ 0.50 | Moderate agreement |
| < 0.50 | Poor agreement |

### Per-Item Breakdown

The report includes per-item α values to identify problematic items:

```python
krippendorff_alpha_per_item = {
    "anhedonia": 0.72,
    "depressed_mood": 0.81,
    "sleep": 0.68,
    # ... etc
}
```

---

## Consistency Gate

**Metric**: Cronbach's Alpha (α)

Measures **internal consistency**—whether the 8 PHQ items correlate with each other (higher scores on one item → higher scores on others).

### Why It Matters

PHQ-8 items measure different facets of depression. If they don't correlate:
- Either the items aren't measuring the same construct
- Or the scoring is unreliable

### Threshold

| α Value | Interpretation |
|---------|----------------|
| ≥ 0.90 | Excellent internal consistency |
| ≥ 0.70 | **Acceptable** (gate threshold) |
| < 0.70 | Poor internal consistency |

### Item-Total Correlations

Shows how each item correlates with the total score:

```python
item_total_correlations = {
    "anhedonia": 0.65,
    "depressed_mood": 0.78,
    # ... etc
}
```

Low correlations indicate items that may not be scored consistently.

---

## Separation Gate

**Metric**: MDD vs Control mean comparison

Validates that the scoring correctly differentiates clinical conditions.

### What It Checks

```
MDD dialogues should have higher PHQ-8 scores than Control dialogues
```

The gate computes:

| Statistic | Description |
|-----------|-------------|
| `mdd_mean` | Average total score for MDD dialogues |
| `control_mean` | Average total score for Control dialogues |
| `cohens_d` | Effect size (standardized difference) |
| `is_valid` | True if `mdd_mean > control_mean` |

### Expected Values

For clinical validity:
- `mdd_mean` should be ~10-15 (moderate depression)
- `control_mean` should be ~3-7 (minimal symptoms)
- `cohens_d` > 0.8 indicates large effect

---

## Arbitration Gate

**Metric**: Arbitration rate

Ensures the jury reaches consensus on most items without needing judge intervention.

### Threshold

```
arbitration_rate < 30%
```

If more than 30% of items require arbitration, it indicates:
- Jurors are systematically disagreeing
- Prompts may need refinement
- Model selection may be suboptimal

### Breakdown

The report includes:

```python
arbitration = {
    "overall_rate": 0.23,  # 23% of items needed arbitration
    "per_item_rate": {
        "anhedonia": 0.35,      # 35% of dialogues
        "depressed_mood": 0.18,
        # ... etc
    },
    "trigger_counts": {
        "low_max_prob": 145,
        "high_entropy": 89,
        "vote_range": 67,
        # ... etc
    }
}
```

---

## Diagnostic Report Schema

```python
class DiagnosticReport(BaseModel):
    run_id: str
    n_dialogues: int
    n_mdd: int
    n_control: int

    reliability: ReliabilityMetrics
    consistency: ConsistencyMetrics
    separation: SeparationMetrics
    arbitration: ArbitrationMetrics

    passes_reliability_gate: bool  # α ≥ 0.67
    passes_consistency_gate: bool  # α ≥ 0.70
    passes_separation_gate: bool   # mdd_mean > control_mean
    passes_arbitration_gate: bool  # rate < 30%
```

---

## Running Diagnostics

```bash
vibe-check diagnostics \
    --scored data/outputs/scored.jsonl \
    --strict  # Exit non-zero if any gate fails
```

### Output

```
=== Diagnostic Report ===
Run: 2026-01-03_production
Dialogues: 2,090 (MDD: 912, Control: 1,178)

RELIABILITY
  Krippendorff α: 0.73 ✓ (threshold: 0.67)

CONSISTENCY
  Cronbach α: 0.82 ✓ (threshold: 0.70)

SEPARATION
  MDD mean: 12.4 | Control mean: 4.8
  Cohen's d: 1.23 ✓

ARBITRATION
  Rate: 23% ✓ (threshold: 30%)

All gates passed. Export ready.
```

---

## When Gates Fail

| Gate | Failure | Likely Cause | Action |
|------|---------|--------------|--------|
| Reliability | α < 0.67 | Juror disagreement | Review prompts, add jurors |
| Consistency | α < 0.70 | Scoring inconsistency | Check item definitions |
| Separation | Invalid | Wrong condition labels | Verify corpus metadata |
| Arbitration | Rate > 30% | Systematic disagreement | Lower thresholds or add judge capacity |

---

## Code Reference

| File | Component | Purpose |
|------|-----------|---------|
| `diagnostics/runner.py` | `RunDiagnostics` | Main diagnostic computation |
| `diagnostics/reliability.py` | `compute_krippendorff_alpha()` | Inter-rater reliability |
| `diagnostics/consistency.py` | `compute_cronbach_alpha()` | Internal consistency |
| `diagnostics/separation.py` | `compute_condition_separation()` | MDD vs Control |
| `diagnostics/arbitration.py` | `compute_arbitration_metrics()` | Arbitration stats |
| `diagnostics/report.py` | `DiagnosticReport` | Output schema |

---

## Related Concepts

- [Jury Consensus](../scoring/jury-consensus.md) - What generates the votes
- [Arbitration](../scoring/arbitration.md) - What happens when jurors disagree
