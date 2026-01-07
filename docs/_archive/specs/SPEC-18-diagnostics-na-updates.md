# SPEC-18: Diagnostics NA Updates (Phase 1)

> **Status**: IMPLEMENTED (Phase 1 complete)
> **Depends On**: SPEC-13 (NA-aware juror schema), SPEC-15 (NA-aware aggregation), SPEC-17 (NA-aware judge)
> **Blocks**: Pilot quality gates for NA-aware runs

---

## 1. Overview

Diagnostics (SPEC-07) must become NA-aware to avoid:
- Crashing on `score=null` juror votes
- Misreporting coverage as “denial”
- Hiding assertion drift (`possible` vs `present` vs `not_mentioned`)

This spec adds:
1. Coverage + NA-rate metrics (SSOT §13.4)
2. Assertion distribution metrics (SSOT §13.4)
3. NA-aware separation reporting (imputed vs prorated)
4. Robustness updates to arbitration/reliability computations (no `int(None)` failures)

---

## 2. Coverage + Assertion Metrics (new)

### 2.1 Coverage Metrics Schema

```python
# File: src/vibe_check/diagnostics/coverage.py
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from vibe_check.constants import PHQ8_ITEMS


class CoverageMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    n_dialogues: int = Field(ge=0)

    # Corpus-level NA
    total_cells: int = Field(ge=0, description="n_dialogues * 8")
    na_cells: int = Field(ge=0, description="Count of cells where consensus_assertion == not_mentioned")
    corpus_na_rate: float = Field(ge=0.0, le=1.0, description="na_cells / total_cells")

    # Per-item coverage (discussion rate)
    item_coverage: dict[str, float] = Field(description="Per-item P(discussed) across dialogues")
    min_item_coverage: float = Field(ge=0.0, le=1.0)
    max_item_coverage: float = Field(ge=0.0, le=1.0)

    # Per-dialogue coverage
    dialogues_with_min_coverage: int = Field(ge=0, description="count(totals.is_min_coverage)")
    dialogues_with_proration_valid: int = Field(ge=0, description="count(totals.is_proration_valid)")
    dialogue_coverage_mean: float = Field(ge=0.0, le=1.0)
    dialogue_coverage_std: float = Field(ge=0.0)
    coverage_histogram: dict[int, int] = Field(description="counts by discussed_count (0..8)")
```

### 2.2 Coverage Computation (uses SPEC-15 shape)

```python
# File: src/vibe_check/diagnostics/coverage.py
from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from vibe_check.constants import PHQ8_ITEMS
from vibe_check.diagnostics.coverage import CoverageMetrics

if TYPE_CHECKING:
    from vibe_check.schemas.output import AggregatedPHQ8


def compute_coverage_metrics(rows: list["AggregatedPHQ8"]) -> CoverageMetrics:
    n_dialogues = len(rows)
    total_cells = n_dialogues * len(PHQ8_ITEMS)

    item_na_counts = dict.fromkeys(PHQ8_ITEMS, 0)
    coverage_hist = {i: 0 for i in range(9)}
    na_cells = 0
    dialogue_coverages: list[float] = []
    min_cov = 0
    proration_valid = 0

    for row in rows:
        discussed_count = int(row.totals.discussed_count)
        coverage_hist[discussed_count] += 1
        dialogue_coverages.append(discussed_count / 8.0)
        if row.totals.is_min_coverage:
            min_cov += 1
        if row.totals.is_proration_valid:
            proration_valid += 1

        for item in PHQ8_ITEMS:
            if row.items[item].consensus_assertion == "not_mentioned":
                item_na_counts[item] += 1
                na_cells += 1

    item_coverage = {
        item: ((n_dialogues - int(na_count)) / float(n_dialogues)) if n_dialogues else 0.0
        for item, na_count in item_na_counts.items()
    }
    cov_vals = list(item_coverage.values())
    cov_arr = np.array(dialogue_coverages, dtype=float) if dialogue_coverages else np.array([], dtype=float)

    return CoverageMetrics(
        n_dialogues=n_dialogues,
        total_cells=total_cells,
        na_cells=na_cells,
        corpus_na_rate=(na_cells / float(total_cells)) if total_cells else 0.0,
        item_coverage=item_coverage,
        min_item_coverage=min(cov_vals) if cov_vals else 0.0,
        max_item_coverage=max(cov_vals) if cov_vals else 0.0,
        dialogues_with_min_coverage=min_cov,
        dialogues_with_proration_valid=proration_valid,
        dialogue_coverage_mean=float(np.mean(cov_arr)) if cov_arr.size else 0.0,
        dialogue_coverage_std=float(np.std(cov_arr)) if cov_arr.size else 0.0,
        coverage_histogram=coverage_hist,
    )
```

### 2.3 Assertion Distribution Metrics (SSOT §13.4)

```python
# File: src/vibe_check/diagnostics/assertions.py
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from vibe_check.constants import PHQ8_ITEMS

Assertion = Literal["present", "denied", "possible", "not_mentioned"]


class AssertionDistribution(BaseModel):
    """Consensus assertion distribution across the run."""

    model_config = ConfigDict(extra="forbid")

    # by_item[item][assertion] = count
    by_item: dict[str, dict[Assertion, int]]
    # totals[assertion] = total count across all items and dialogues
    totals: dict[Assertion, int]


def compute_assertion_distribution(rows: list["AggregatedPHQ8"]) -> AssertionDistribution:
    by_item: dict[str, dict[Assertion, int]] = {
        item: {"present": 0, "denied": 0, "possible": 0, "not_mentioned": 0}
        for item in PHQ8_ITEMS
    }
    totals: dict[Assertion, int] = {"present": 0, "denied": 0, "possible": 0, "not_mentioned": 0}

    for row in rows:
        for item in PHQ8_ITEMS:
            a = row.items[item].consensus_assertion
            by_item[item][a] += 1
            totals[a] += 1

    return AssertionDistribution(by_item=by_item, totals=totals)
```

---

## 3. Reliability Updates (NA-safe)

### 3.1 Vote Tensor Construction (no `int(None)` failures)

In `RunDiagnostics.compute()` (existing `src/vibe_check/diagnostics/runner.py`), when building the juror vote tensor:
- Use `float(score)` when score is numeric
- Use `np.nan` when a juror vote is `score=None` (`assertion="not_mentioned"`)

Krippendorff alpha supports missingness via `np.nan` (krippendorff library).

### 3.2 ICC Handling (implementation-feasible)

To preserve the existing `ReliabilityMetrics` schema shape (overall ICC values), ICC is computed on an **imputed** tensor:

```python
icc_votes = np.nan_to_num(votes, nan=0.0)
flat = icc_votes.reshape(n_dialogues * n_items, n_jurors)
icc_consistency, icc_agreement, icc_ci = _compute_icc_metrics(flat)
```

This is explicitly a proxy metric under NA; Krippendorff alpha remains the primary missingness-aware reliability metric.

---

## 4. Separation Updates (imputed + prorated)

### 4.1 New Separation Schema

```python
# File: src/vibe_check/diagnostics/report.py (additions)
from pydantic import BaseModel, ConfigDict, Field


class SeparationMetricsNA(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Imputed totals (all dialogues; NA->0)
    mdd_mean_imputed: float
    mdd_std_imputed: float
    control_mean_imputed: float
    control_std_imputed: float
    cohens_d_imputed: float
    p_value_imputed: float
    is_imputed_valid: bool

    # Prorated totals (only dialogues with totals.is_proration_valid=True)
    n_mdd_prorated: int = Field(ge=0)
    n_control_prorated: int = Field(ge=0)
    mdd_mean_prorated: float | None
    mdd_std_prorated: float | None
    control_mean_prorated: float | None
    control_std_prorated: float | None
    cohens_d_prorated: float | None
    p_value_prorated: float | None
    is_prorated_valid: bool

    # Gate selection (ironclad)
    gate_basis: str = Field(description="'prorated' iff both n_*_prorated>=2 else 'imputed'")
```

### 4.2 Gate Logic (deterministic)

In `RunDiagnostics.compute()`:
- Always compute imputed separation (requires ≥2 per condition, same as v1)
- Compute prorated separation **only** over dialogues with `totals.is_proration_valid=True`
- If `n_mdd_prorated >= 2` AND `n_control_prorated >= 2`:
  - `gate_basis="prorated"`
  - `passes_separation_gate = separation.is_prorated_valid`
- Else:
  - `gate_basis="imputed"`
  - `passes_separation_gate = separation.is_imputed_valid`

### 4.3 Reference Implementation: `compute_separation_metrics_na`

```python
# File: src/vibe_check/diagnostics/separation.py (additions)
from __future__ import annotations

import numpy as np
from typing import TYPE_CHECKING

from vibe_check.diagnostics.report import SeparationMetricsNA

if TYPE_CHECKING:
    from vibe_check.schemas.output import AggregatedPHQ8


def compute_separation_metrics_na(rows: list["AggregatedPHQ8"]) -> SeparationMetricsNA:
    """Compute imputed + prorated separation with explicit gate basis."""
    mdd = [r for r in rows if r.condition == "mdd"]
    control = [r for r in rows if r.condition == "control"]

    mdd_imputed = np.array([float(r.totals.imputed_total) for r in mdd], dtype=float)
    control_imputed = np.array([float(r.totals.imputed_total) for r in control], dtype=float)
    imputed = compute_condition_separation(mdd_totals=mdd_imputed, control_totals=control_imputed)

    mdd_pr = [
        float(r.totals.prorated_total_rounded)
        for r in mdd
        if r.totals.is_proration_valid and r.totals.prorated_total_rounded is not None
    ]
    control_pr = [
        float(r.totals.prorated_total_rounded)
        for r in control
        if r.totals.is_proration_valid and r.totals.prorated_total_rounded is not None
    ]

    n_mdd_prorated = len(mdd_pr)
    n_control_prorated = len(control_pr)
    if n_mdd_prorated >= 2 and n_control_prorated >= 2:
        prorated = compute_condition_separation(
            mdd_totals=np.array(mdd_pr, dtype=float),
            control_totals=np.array(control_pr, dtype=float),
        )
        gate_basis = "prorated"
        return SeparationMetricsNA(
            mdd_mean_imputed=imputed.mdd_mean,
            mdd_std_imputed=imputed.mdd_std,
            control_mean_imputed=imputed.control_mean,
            control_std_imputed=imputed.control_std,
            cohens_d_imputed=imputed.cohens_d,
            p_value_imputed=imputed.p_value,
            is_imputed_valid=imputed.is_valid,
            n_mdd_prorated=n_mdd_prorated,
            n_control_prorated=n_control_prorated,
            mdd_mean_prorated=prorated.mdd_mean,
            mdd_std_prorated=prorated.mdd_std,
            control_mean_prorated=prorated.control_mean,
            control_std_prorated=prorated.control_std,
            cohens_d_prorated=prorated.cohens_d,
            p_value_prorated=prorated.p_value,
            is_prorated_valid=prorated.is_valid,
            gate_basis=gate_basis,
        )

    gate_basis = "imputed"
    return SeparationMetricsNA(
        mdd_mean_imputed=imputed.mdd_mean,
        mdd_std_imputed=imputed.mdd_std,
        control_mean_imputed=imputed.control_mean,
        control_std_imputed=imputed.control_std,
        cohens_d_imputed=imputed.cohens_d,
        p_value_imputed=imputed.p_value,
        is_imputed_valid=imputed.is_valid,
        n_mdd_prorated=n_mdd_prorated,
        n_control_prorated=n_control_prorated,
        mdd_mean_prorated=None,
        mdd_std_prorated=None,
        control_mean_prorated=None,
        control_std_prorated=None,
        cohens_d_prorated=None,
        p_value_prorated=None,
        is_prorated_valid=False,
        gate_basis=gate_basis,
    )
```

---

## 5. Report Schema Extensions (SSOT §13.4)

Extend existing `DiagnosticReport` to include:
- `coverage: CoverageMetrics`
- `assertion_distribution: AssertionDistribution`
- `separation: SeparationMetricsNA` (replaces `SeparationMetrics`)
- `passes_coverage_gate: bool` (Phase-1 gate is defined below)

### 5.1 Coverage Gate (explicit; no “TBD”)

This gate is intended to prevent a paid run when the run is dominated by NA (no-evidence) outputs.

Define in `src/vibe_check/constants.py`:

```python
# Coverage gates (SPEC-18)
MIN_ITEM_COVERAGE: float = 0.50       # each PHQ-8 item discussed in >=50% of dialogues
MAX_CORPUS_NA_RATE: float = 0.25      # at most 25% of all (dialogue,item) cells are NA
MIN_DIALOGUE_MIN_COVERAGE_RATE: float = 0.90  # >=90% of dialogues meet totals.is_min_coverage
```

Compute:
```python
passes_coverage_gate = (
    report.coverage.min_item_coverage >= MIN_ITEM_COVERAGE
    and report.coverage.corpus_na_rate <= MAX_CORPUS_NA_RATE
    and (report.coverage.dialogues_with_min_coverage / report.n_dialogues) >= MIN_DIALOGUE_MIN_COVERAGE_RATE
)
```

### 5.2 Markdown Renderer Update (must not crash)

`src/vibe_check/diagnostics/report.py::render_diagnostic_report_markdown()` must be updated to:

- Add a Coverage gate line:
  - `Coverage (min_item_coverage>=..., corpus_na_rate<=..., min_coverage_rate>=...)`
- Report `corpus_na_rate`, `min_item_coverage`, and `dialogues_with_proration_valid`
- Render Separation using `report.separation.gate_basis`:
  - If `gate_basis=="prorated"` use `*_prorated` fields
  - Else use `*_imputed` fields

---

## 6. TDD Test Cases

### 6.1 Coverage Metrics (unit)

```python
# File: tests/unit/test_diagnostics_coverage.py
import pytest

from vibe_check.diagnostics.coverage import compute_coverage_metrics


def test_coverage_full(tmp_path):
    from tests.unit.utils import make_minimal_aggregated_phq8_na

    rows = [make_minimal_aggregated_phq8_na(file_id=f"d{i}", na_items=set()) for i in range(10)]
    m = compute_coverage_metrics(rows)
    assert m.total_cells == 80
    assert m.na_cells == 0
    assert m.corpus_na_rate == 0.0
    assert m.min_item_coverage == 1.0
    assert m.dialogues_with_proration_valid == 10


def test_coverage_partial():
    from tests.unit.utils import make_minimal_aggregated_phq8_na

    rows = [
        make_minimal_aggregated_phq8_na(file_id="d1", na_items={"fatigue", "appetite"}),
        make_minimal_aggregated_phq8_na(file_id="d2", na_items={"fatigue"}),
        make_minimal_aggregated_phq8_na(file_id="d3", na_items=set()),
        make_minimal_aggregated_phq8_na(file_id="d4", na_items={"fatigue", "appetite", "psychomotor"}),
    ]
    m = compute_coverage_metrics(rows)
    assert m.total_cells == 32
    assert m.na_cells == 6
    assert m.corpus_na_rate == pytest.approx(6 / 32)
    assert m.item_coverage["fatigue"] == pytest.approx(0.25)
    assert m.coverage_histogram[8] == 1
    assert m.coverage_histogram[7] == 1
    assert m.coverage_histogram[6] == 1
    assert m.coverage_histogram[5] == 1
```

### 6.2 Assertion Distribution (unit)

```python
# File: tests/unit/test_diagnostics_assertions.py
from vibe_check.diagnostics.assertions import compute_assertion_distribution


def test_assertion_distribution_counts():
    from tests.unit.utils import make_minimal_aggregated_phq8_na

    rows = [
        make_minimal_aggregated_phq8_na(file_id="d1", na_items={"fatigue"}),
        make_minimal_aggregated_phq8_na(file_id="d2", na_items=set()),
    ]
    dist = compute_assertion_distribution(rows)

    # fatigue: 1 not_mentioned, 1 present
    assert dist.by_item["fatigue"]["not_mentioned"] == 1
    assert dist.by_item["fatigue"]["present"] == 1
    # totals sum to n_dialogues * 8
    assert sum(dist.totals.values()) == 16
```

### 6.3 Separation Gate Basis (unit)

```python
# File: tests/unit/test_diagnostics_separation_na.py
from vibe_check.diagnostics.separation import compute_separation_metrics_na


def test_separation_gate_prefers_prorated_when_enough_proration_valid():
    from tests.unit.utils import make_minimal_aggregated_phq8_na

    rows = [
        # 2 MDD with proration valid (>=7 discussed)
        make_minimal_aggregated_phq8_na(file_id="m1", condition="mdd", na_items=set(), base_score=2),
        make_minimal_aggregated_phq8_na(file_id="m2", condition="mdd", na_items={"fatigue"}, base_score=2),
        # 2 control with proration valid
        make_minimal_aggregated_phq8_na(file_id="c1", condition="control", na_items=set(), base_score=0),
        make_minimal_aggregated_phq8_na(file_id="c2", condition="control", na_items={"sleep"}, base_score=0),
    ]
    metrics = compute_separation_metrics_na(rows)
    assert metrics.n_mdd_prorated == 2
    assert metrics.n_control_prorated == 2
    assert metrics.gate_basis == "prorated"


def test_separation_gate_falls_back_to_imputed_when_prorated_insufficient():
    from tests.unit.utils import make_minimal_aggregated_phq8_na

    rows = [
        # MDD: only 1 proration-valid
        make_minimal_aggregated_phq8_na(file_id="m1", condition="mdd", na_items=set(), base_score=2),
        make_minimal_aggregated_phq8_na(file_id="m2", condition="mdd", na_items={"fatigue", "appetite"}, base_score=2),
        # control: 2 proration-valid
        make_minimal_aggregated_phq8_na(file_id="c1", condition="control", na_items=set(), base_score=0),
        make_minimal_aggregated_phq8_na(file_id="c2", condition="control", na_items={"sleep"}, base_score=0),
    ]
    metrics = compute_separation_metrics_na(rows)
    assert metrics.n_mdd_prorated == 1
    assert metrics.gate_basis == "imputed"
```

### 6.4 CLI Diagnostics (integration; uses argparse `main`)

```python
# File: tests/integration/test_cli_diagnostics_na.py
import json
from pathlib import Path

from vibe_check.cli import main


def test_cli_diagnostics_with_na(tmp_path: Path):
    scored = tmp_path / "scored.jsonl"
    output = tmp_path / "report.json"

    from tests.unit.utils import make_minimal_aggregated_phq8_na

    # Ensure ≥2 samples per condition so separation metrics can be computed.
    rows = [
        make_minimal_aggregated_phq8_na(file_id="m1", condition="mdd", na_items={"fatigue"}, base_score=2),
        make_minimal_aggregated_phq8_na(file_id="m2", condition="mdd", na_items=set(), base_score=2),
        make_minimal_aggregated_phq8_na(file_id="c1", condition="control", na_items={"sleep"}, base_score=0),
        make_minimal_aggregated_phq8_na(file_id="c2", condition="control", na_items=set(), base_score=0),
    ]

    lines: list[str] = []
    for r in rows:
        row = r.model_dump(mode="json")
        row["computed_split"] = "train"
        row["scoring_text"] = "Client: ..."
        row["dialogue_view"] = "client_qa"
        lines.append(json.dumps(row))

    scored.write_text("\n".join(lines) + "\n", encoding="utf-8")

    rc = main(["diagnostics", "--scored", str(scored), "--output", str(output), "--format", "json"])
    assert rc == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert "coverage" in payload
    assert "assertion_distribution" in payload
```

---

## 7. Files Affected

| File | Change Type |
|------|-------------|
| `src/vibe_check/diagnostics/runner.py` | **MAJOR** (NA-safe vote tensor; new coverage/assertion/separation fields) |
| `src/vibe_check/diagnostics/report.py` | **MODERATE** (extend report schema) |
| `src/vibe_check/diagnostics/coverage.py` | **NEW** |
| `src/vibe_check/diagnostics/assertions.py` | **NEW** |
| `src/vibe_check/diagnostics/separation.py` | **MODERATE** (add NA separation function) |
| `src/vibe_check/diagnostics/arbitration.py` | **MODERATE** (skip None modes safely) |
| `src/vibe_check/constants.py` | **MINOR** (coverage gate thresholds) |
| `tests/unit/test_diagnostics_coverage.py` | **NEW** |
| `tests/unit/test_diagnostics_assertions.py` | **NEW** |
| `tests/unit/test_diagnostics_separation_na.py` | **NEW** |
| `tests/integration/test_cli_diagnostics_na.py` | **NEW** |

---

## 8. Acceptance Criteria

- [ ] Diagnostics does not crash with juror `score=None` votes
- [ ] Report includes per-item NA rates + coverage histogram
- [ ] Report includes assertion distribution per item + totals
- [ ] Separation reports both imputed and prorated metrics with explicit `gate_basis`
- [ ] `--strict` includes `passes_coverage_gate` in `passes_all_gates`

---

## 9. Sign-Off

| Role | Status |
|------|--------|
| Author | IMPLEMENTED |
| Senior Review | APPROVED |
