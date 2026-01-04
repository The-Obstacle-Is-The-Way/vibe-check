# Thresholds Reference

All numeric thresholds in vibe-check explained.

---

## Overview

Thresholds control two critical behaviors:
1. **Arbitration Triggers** - When the judge intervenes
2. **Quality Gates** - Whether a scoring run passes validation

---

## Arbitration Thresholds

These thresholds determine when a PHQ-8 item needs judge arbitration.

### max_prob_threshold

**Default**: `0.60`
**Setting**: `ARBITRATION_MAX_PROB_THRESHOLD`

The minimum posterior probability required for the mode to be considered a consensus.

| Value | Behavior |
|-------|----------|
| `0.60` | Default - triggers if max P(score) < 60% |
| `0.50` | More lenient - allows weaker consensus |
| `0.70` | More strict - requires stronger consensus |

**Example**:
```
Posterior: [0.10, 0.35, 0.40, 0.15]  # max = 0.40
Threshold: 0.60
Result: ARBITRATE (0.40 < 0.60)
```

---

### entropy_threshold

**Default**: `1.2`
**Setting**: `ARBITRATION_ENTROPY_THRESHOLD`

Maximum Shannon entropy before arbitration is triggered. Higher entropy = more uncertainty.

| Value | Behavior |
|-------|----------|
| `1.2` | Default - triggers if entropy > 1.2 nats |
| `1.5` | More lenient - tolerates more uncertainty |
| `1.0` | More strict - requires more certainty |

**Entropy Reference**:
```
Uniform [0.25, 0.25, 0.25, 0.25] → H = ln(4) ≈ 1.39 nats (maximum)
Certain [0.00, 0.00, 1.00, 0.00] → H = 0.0 nats (minimum)
Typical  [0.10, 0.30, 0.50, 0.10] → H ≈ 1.17 nats
```

**Formula**:
```
H = -Σ p(x) × ln(p(x))
```

---

### clinical_ambiguity_band

**Default**: `(0.4, 0.6)`
**Setting**: `CLINICAL_AMBIGUITY_BAND_LOW` and `CLINICAL_AMBIGUITY_BAND_HIGH`

Triggers arbitration when clinical probability (P(score ≥ 2)) falls in the ambiguous range.

| P(clinical) | Interpretation |
|-------------|----------------|
| `< 0.4` | Likely subclinical |
| `0.4 - 0.6` | Ambiguous - triggers arbitration |
| `> 0.6` | Likely clinical |

**Rationale**: The 2-point threshold is clinically meaningful. Ambiguity around this boundary warrants expert review.

---

### range_threshold

**Default**: `2`
**Setting**: `DISAGREEMENT_RANGE_THRESHOLD`

Maximum vote range (max - min) before arbitration.

| Votes | Range | Result |
|-------|-------|--------|
| `[1, 1, 1, 1, 2, 2]` | 1 | OK |
| `[0, 1, 1, 2, 2, 2]` | 2 | ARBITRATE |
| `[0, 1, 2, 2, 3, 3]` | 3 | ARBITRATE |

**Rationale**: A 2+ point spread indicates fundamental disagreement about severity.

---

### insufficient_evidence_threshold

**Default**: `2`
**Setting**: `INSUFFICIENT_EVIDENCE_THRESHOLD`

How many jurors must flag `insufficient_evidence: true` to trigger arbitration.

| Count | Result |
|-------|--------|
| 0-1 | OK - minority uncertain |
| 2+ | ARBITRATE - significant uncertainty |

---

### total_std_threshold

**Default**: `2.0`
**Setting**: `ARBITRATION_TOTAL_STD_THRESHOLD`

Maximum standard deviation of juror total scores.

Used to detect overall disagreement even when individual items might agree.

**Example**:
```
Juror totals: [12, 14, 13, 15, 12, 14]  # std ≈ 1.2
Threshold: 2.0
Result: OK (1.2 < 2.0)

Juror totals: [8, 10, 14, 16, 18, 20]   # std ≈ 4.3
Threshold: 2.0
Result: ARBITRATE (4.3 > 2.0)
```

---

## Quality Gate Thresholds

These thresholds determine if a scoring run passes validation.

### Reliability Gate: Krippendorff's α

**Threshold**: `α ≥ 0.67`
**File**: `diagnostics/runner.py:105`

Inter-rater reliability across all jurors.

| α Value | Interpretation |
|---------|---------------|
| `< 0.67` | **FAIL** - Poor agreement |
| `0.67 - 0.80` | Acceptable agreement |
| `> 0.80` | Good agreement |

**Formula**: Krippendorff's alpha using ordinal distance metric.

---

### Consistency Gate: Cronbach's α

**Threshold**: `α ≥ 0.70`
**File**: `diagnostics/runner.py:106`

Internal consistency of PHQ-8 items (do items correlate as expected for a depression scale).

| α Value | Interpretation |
|---------|---------------|
| `< 0.70` | **FAIL** - Items not internally consistent |
| `0.70 - 0.80` | Acceptable consistency |
| `> 0.80` | Good consistency |

**Formula**: Cronbach's alpha on final item scores.

---

### Separation Gate: MDD > control, p < 0.01, d ≥ 0.5

**Threshold**:
- `mdd_mean > control_mean`
- `p_value < 0.01`
- `cohens_d >= 0.5`

**Files**:
- `src/vibe_check/diagnostics/runner.py:107` (gate uses `separation.is_valid`)
- `src/vibe_check/diagnostics/separation.py:55` (definition of `is_valid`)

The corpus should show expected clinical separation.

| Condition | Expected |
|-----------|----------|
| MDD cases | Higher PHQ-8 totals |
| Control cases | Lower PHQ-8 totals |

**Additional Metrics (reported, not gated)**:
- t-statistic

---

### Arbitration Gate: Rate < 30%

**Threshold**: `rate < 0.30`
**File**: `diagnostics/runner.py:108`

At most 30% of items should require judge arbitration.

| Rate | Interpretation |
|------|---------------|
| `< 0.30` | **PASS** - Normal disagreement levels |
| `≥ 0.30` | **FAIL** - Excessive juror disagreement |

**Rationale**: High arbitration rate indicates:
- Prompts may be unclear
- Corpus may be ambiguous
- Jurors may be inconsistent

---

## Bayesian Parameters

### dirichlet_alpha

**Default**: `0.5`
**Setting**: `DIRICHLET_ALPHA`

Bayesian smoothing parameter for posteriors.

| Value | Effect |
|-------|--------|
| `0.5` | Jeffreys prior (recommended) |
| `1.0` | Uniform prior (flat) |
| `0.1` | Sparse prior (less smoothing) |

**Usage**: Prior counts = `[α, α, α, α]` for scores 0-3.

**Formula**:
```
posterior[i] = (vote_count[i] + α) / (total_votes + 4α)
```

---

## Threshold Tuning Guide

### Too Many Arbitrations (rate > 30%)

```bash
# More lenient thresholds
ARBITRATION_MAX_PROB_THRESHOLD=0.50
ARBITRATION_ENTROPY_THRESHOLD=1.5
DISAGREEMENT_RANGE_THRESHOLD=3
```

### Quality Gates Failing

```bash
# More aggressive arbitration (let judge fix disagreements)
ARBITRATION_MAX_PROB_THRESHOLD=0.70
ARBITRATION_ENTROPY_THRESHOLD=1.0
```

### Clinical Use Case (higher accuracy)

```bash
# Strictest settings - more judge involvement
ARBITRATION_MAX_PROB_THRESHOLD=0.75
ARBITRATION_ENTROPY_THRESHOLD=0.8
DISAGREEMENT_RANGE_THRESHOLD=1
```

---

## Threshold Summary Table

| Threshold | Default | Setting | Purpose |
|-----------|---------|---------|---------|
| `max_prob_threshold` | 0.60 | `ARBITRATION_MAX_PROB_THRESHOLD` | Min posterior peak |
| `entropy_threshold` | 1.2 | `ARBITRATION_ENTROPY_THRESHOLD` | Max uncertainty |
| `clinical_ambiguity_band` | (0.4, 0.6) | `CLINICAL_AMBIGUITY_BAND_LOW` / `CLINICAL_AMBIGUITY_BAND_HIGH` | Clinical boundary ambiguity |
| `range_threshold` | 2 | `DISAGREEMENT_RANGE_THRESHOLD` | Max vote spread |
| `insufficient_evidence_threshold` | 2 | `INSUFFICIENT_EVIDENCE_THRESHOLD` | Min uncertain jurors |
| `total_std_threshold` | 2.0 | `ARBITRATION_TOTAL_STD_THRESHOLD` | Max total score std |
| Krippendorff α gate | 0.67 | — | Min inter-rater agreement |
| Cronbach α gate | 0.70 | — | Min internal consistency |
| Separation gate | MDD > control, p<0.01, d≥0.5 | — | Condition separation validity |
| Arbitration rate gate | 0.30 | — | Max arbitration rate |
| `dirichlet_alpha` | 0.5 | `DIRICHLET_ALPHA` | Bayesian smoothing |
