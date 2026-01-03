# SPEC-07: Run Diagnostics & Quality Metrics

**Status**: IMPLEMENTED (2026-01-03)
**Slice Type**: Vertical (Scored Corpus → Quality Report)
**Dependencies**: SPEC-06 (Batch Runner & Export)
**Estimated Scope**: ~400 lines of code, ~300 lines of tests

---

## 1. Objective

Implement a diagnostic pipeline that validates the scored SQPsychConv corpus **before** export. This is the "Phase 0 Sanity Check" from the SSOT (Section 12.1).

Goals:
1. **Inter-rater reliability**: Compute agreement metrics across 6 juror passes (3 models × 2 runs)
2. **Internal consistency**: Validate that PHQ-8 items correlate appropriately
3. **Condition separation**: Verify MDD dialogues score higher than control
4. **Arbitration analysis**: Profile when/why the judge was invoked
5. **Quality gates**: Define pass/fail thresholds before proceeding

> **Note**: This tool consumes the **Internal** `scored.jsonl` (from SPEC-06) which contains full juror reports and posterior distributions. It does NOT use the flattened public export (SPEC-08).

### Success Criteria

```python
from vibe_check.diagnostics import RunDiagnostics
from vibe_check.diagnostics.report import DiagnosticReport

# Note: Uses internal scored.jsonl, not export
diagnostics = RunDiagnostics(
    scored_jsonl="data/outputs/scored.jsonl",
    run_manifest="data/outputs/run_manifest.json",
)
report: DiagnosticReport = diagnostics.compute()

assert report.krippendorff_alpha >= 0.70  # Inter-rater reliability
assert report.cronbach_alpha >= 0.70      # Internal consistency
assert report.mdd_mean_total > report.control_mean_total  # Directional validity
assert report.arbitration_rate < 0.30     # Most items reach consensus
```

---

## 2. Deliverables

### 2.1 New Source Files

| File | Purpose |
|------|---------|
| `src/vibe_check/diagnostics/__init__.py` | Package exports |
| `src/vibe_check/diagnostics/reliability.py` | Inter-rater metrics (Krippendorff's α, ICC) |
| `src/vibe_check/diagnostics/consistency.py` | Internal consistency (Cronbach's α) |
| `src/vibe_check/diagnostics/separation.py` | Condition separation (MDD vs control) |
| `src/vibe_check/diagnostics/arbitration.py` | Arbitration profiling |
| `src/vibe_check/diagnostics/report.py` | DiagnosticReport schema + rendering |
| `src/vibe_check/diagnostics/runner.py` | RunDiagnostics orchestration |

### 2.2 New Test Files

| File | Purpose |
|------|---------|
| `tests/unit/test_reliability.py` | Krippendorff/ICC edge cases |
| `tests/unit/test_consistency.py` | Cronbach's α computation |
| `tests/unit/test_separation.py` | Effect size calculations |
| `tests/integration/test_diagnostics_runner.py` | End-to-end on sample data |

### 2.3 pyproject.toml Updates

Add diagnostic dependencies:

- `krippendorff>=0.8.0` — [Fast Krippendorff](https://pypi.org/project/krippendorff/) for inter-rater reliability

---

## 3. Metrics Specification

### 3.1 Inter-Rater Reliability

We have 6 "raters" (3 models × 2 runs) scoring 8 items per dialogue.

#### Krippendorff's Alpha (α)

Per the [Beyond Majority Voting](https://arxiv.org/abs/2310.XXXXX) paper, simple majority voting ignores model heterogeneity. Krippendorff's α handles:
- Multiple raters (not just 2)
- Ordinal data (0-3 scale)
- Missing values (if a juror failed)

```python
import krippendorff
import numpy as np

def compute_krippendorff_alpha(
    item_votes: np.ndarray,  # Shape: (n_dialogues, n_items, n_jurors)
    level_of_measurement: str = "ordinal",
) -> float:
    """Compute Krippendorff's alpha across all items and jurors.

    Args:
        item_votes: 3D array of votes per dialogue/item/juror
        level_of_measurement: "ordinal" for 0-3 scale

    Returns:
        Alpha coefficient (-1 to 1, higher = better agreement; negative = worse than chance)
    """
    # Reshape to (n_units, n_raters) where n_units = dialogues × items
    n_dialogues, n_items, n_jurors = item_votes.shape
    reshaped = item_votes.reshape(n_dialogues * n_items, n_jurors)

    return krippendorff.alpha(
        reshaped.T,  # krippendorff expects (raters, units)
        level_of_measurement=level_of_measurement,
    )
```

**Thresholds** (per Krippendorff's guidelines):
- α ≥ 0.80: Excellent agreement
- 0.67 ≤ α < 0.80: Acceptable for exploratory research
- α < 0.67: Unreliable — do NOT proceed

#### Intraclass Correlation Coefficient (ICC)

Per the [MentalBench](https://github.com/abeerbadawi/MentalBench-Align/) framework, ICC provides both:
- **ICC(C,1)**: Consistency (rank agreement, ignores scale shifts)
- **ICC(A,1)**: Absolute agreement (rank AND level match)

```python
from scipy import stats

def compute_icc(
    votes: np.ndarray,  # Shape: (n_units, n_raters)
    icc_type: str = "ICC(2,1)",  # Two-way random, single measure
) -> tuple[float, tuple[float, float]]:
    """Compute ICC with 95% CI.

    Returns:
        (icc_value, (ci_lower, ci_upper))
    """
    # Implementation follows Shrout & Fleiss (1979)
    ...
```

### 3.2 Internal Consistency (Cronbach's α)

Measures whether the 8 PHQ-8 items correlate appropriately (i.e., depression is a coherent construct).

```python
def compute_cronbach_alpha(item_scores: np.ndarray) -> float:
    """Compute Cronbach's alpha for internal consistency.

    Args:
        item_scores: Shape (n_dialogues, 8) — final scores per item

    Returns:
        Alpha coefficient (target: ≥ 0.70)
    """
    n_items = item_scores.shape[1]
    item_variances = item_scores.var(axis=0, ddof=1)
    total_variance = item_scores.sum(axis=1).var(ddof=1)

    return (n_items / (n_items - 1)) * (1 - item_variances.sum() / total_variance)
```

**Thresholds**:
- α ≥ 0.70: Acceptable internal consistency
- α ≥ 0.80: Good
- α < 0.70: Questionable — items may not form coherent scale

### 3.3 Condition Separation

Validate that MDD-labeled dialogues score higher than control.

```python
from scipy import stats

def compute_condition_separation(
    mdd_totals: np.ndarray,
    control_totals: np.ndarray,
) -> dict:
    """Compute separation metrics between conditions.

    Returns:
        {
            "mdd_mean": float,
            "control_mean": float,
            "cohens_d": float,  # Effect size
            "t_statistic": float,
            "p_value": float,
            "is_valid": bool,  # mdd_mean > control_mean AND p < 0.01
        }
    """
    mdd_mean = mdd_totals.mean()
    control_mean = control_totals.mean()

    # Cohen's d effect size
    pooled_std = np.sqrt(
        ((len(mdd_totals) - 1) * mdd_totals.std(ddof=1)**2 +
         (len(control_totals) - 1) * control_totals.std(ddof=1)**2) /
        (len(mdd_totals) + len(control_totals) - 2)
    )
    cohens_d = (mdd_mean - control_mean) / pooled_std

    # t-test
    t_stat, p_value = stats.ttest_ind(mdd_totals, control_totals)

    return {
        "mdd_mean": mdd_mean,
        "control_mean": control_mean,
        "cohens_d": cohens_d,
        "t_statistic": t_stat,
        "p_value": p_value,
        "is_valid": mdd_mean > control_mean and p_value < 0.01,
    }
```

**Thresholds**:
- `mdd_mean > control_mean`: Required (directional validity)
- Cohen's d ≥ 0.5: Medium effect size (expected for MDD vs control)
- p < 0.01: Statistically significant separation

### 3.4 Arbitration Profiling

Understand when/why the judge was invoked.

```python
@dataclass
class ArbitrationProfile:
    overall_rate: float  # % of dialogues with any arbitration
    per_item_rates: dict[str, float]  # % per PHQ-8 item
    trigger_reasons: dict[str, int]  # counts by reason
    judge_agreement_with_mode: float  # How often judge picked juror mode
```

**Metrics**:
- `overall_rate < 0.30`: Good — most items reach consensus
- Per-item analysis: Identify problematic items (e.g., psychomotor often triggers)
- `trigger_reasons`: Map to SSOT Section 7.3 (entropy, max_prob, range)

---

## 4. DiagnosticReport Schema

```python
from pydantic import BaseModel, Field
from datetime import datetime

class ReliabilityMetrics(BaseModel):
    # Krippendorff's alpha can be negative when agreement is worse than chance
    krippendorff_alpha: float = Field(ge=-1.0, le=1.0)
    krippendorff_alpha_per_item: dict[str, float]
    icc_consistency: float
    icc_agreement: float
    icc_ci_95: tuple[float, float]

class ConsistencyMetrics(BaseModel):
    # Cronbach's alpha can be negative when items are negatively correlated
    cronbach_alpha: float = Field(ge=-1.0, le=1.0)
    item_total_correlations: dict[str, float]

class SeparationMetrics(BaseModel):
    mdd_mean: float
    mdd_std: float
    control_mean: float
    control_std: float
    cohens_d: float
    t_statistic: float
    p_value: float
    is_valid: bool

class ArbitrationMetrics(BaseModel):
    overall_rate: float
    per_item_rates: dict[str, float]
    trigger_reasons: dict[str, int]
    judge_agreement_with_mode: float

class DiagnosticReport(BaseModel):
    # Identity
    run_id: str
    computed_at: datetime

    # Corpus stats
    n_dialogues: int
    n_mdd: int
    n_control: int

    # Metrics
    reliability: ReliabilityMetrics
    consistency: ConsistencyMetrics
    separation: SeparationMetrics
    arbitration: ArbitrationMetrics

    # Quality gates
    passes_reliability_gate: bool  # krippendorff_alpha >= 0.67
    passes_consistency_gate: bool  # cronbach_alpha >= 0.70
    passes_separation_gate: bool   # is_valid
    passes_arbitration_gate: bool  # overall_rate < 0.30

    @property
    def passes_all_gates(self) -> bool:
        return all([
            self.passes_reliability_gate,
            self.passes_consistency_gate,
            self.passes_separation_gate,
            self.passes_arbitration_gate,
        ])
```

---

## 5. CLI Interface

```bash
# Generate diagnostic report
uv run python -m vibe_check.cli diagnostics \
  --scored data/outputs/scored_sqpsychconv.jsonl \
  --output data/outputs/diagnostics_report.json \
  --format json  # or "markdown" for human-readable

# Strict mode: fail if any gate fails
uv run python -m vibe_check.cli diagnostics \
  --scored data/outputs/scored_sqpsychconv.jsonl \
  --strict \
  --output data/outputs/diagnostics_report.json
```

---

## 6. Testing Strategy

### 6.1 Unit Tests

- **Krippendorff edge cases**: Perfect agreement (α=1.0), random (α≈0), missing values
- **Cronbach edge cases**: Single item, perfect correlation, negative correlation
- **Separation**: Equal means, inverted means (MDD < control = fail)

### 6.2 Integration Tests

- Load sample scored JSONL (N=50 dialogues)
- Compute full diagnostic report
- Assert all gates pass for well-formed data
- Assert appropriate gates fail for malformed data

---

## 7. References

- [Beyond Majority Voting (PoLL)](https://arxiv.org/abs/2310.XXXXX) — Optimal Weight and ISP aggregation
- [MentalBench/MentalAlign](https://github.com/abeerbadawi/MentalBench-Align/) — ICC framework for LLM-as-Judge reliability
- [Krippendorff's Alpha (PyPI)](https://pypi.org/project/krippendorff/) — Fast Python implementation
- [Shrout & Fleiss (1979)](https://doi.org/10.1037/0033-2909.86.2.420) — ICC definitions
- SSOT Section 12.1 — Phase 0 Sanity Checks

---

## 8. Non-Goals

- Ground-truth validation (happens in `_reference/ai-psychiatrist/`, NOT here)
- Embedding generation (SPEC-08)
- Per-model performance breakdown (covered in run_manifest.json from SPEC-06)

---

## 9. Anti-Patterns

> **CRITICAL: vibe-check NEVER touches real clinical data.**
>
> - DAIC-WOZ evaluation happens in `ai-psychiatrist`, NOT vibe-check
> - vibe-check's job ends at producing labels from SQPsychConv
> - Embedding generation happens in `ai-psychiatrist`
> - See `_reference/ai-psychiatrist/` for the transfer evaluation pipeline
