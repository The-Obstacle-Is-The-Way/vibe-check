# SPEC-18: Diagnostics NA Updates

> **Status**: DRAFT - Pending Senior Review
> **Depends On**: SPEC-13 (Schema), SPEC-15 (Aggregation)
> **Blocks**: Quality gates for NA-aware runs
> **Created By**: Senior review identified this as missing spec

---

## 1. Overview

The diagnostics module (SPEC-07) computes quality metrics and gates for scored runs. With NA-aware scoring, the diagnostics need updates to:

1. **Track coverage metrics** - How many items are NA per dialogue
2. **Handle NA in reliability** - Krippendorff/ICC with missing data
3. **Report NA-specific arbitration** - Mixed NA + numeric arbitration rates
4. **Gate on coverage** - Reject runs with too much missing data

---

## 2. Design Decisions

### 2.1 Coverage Thresholds

| Threshold | Value | Rationale |
|-----------|-------|-----------|
| `MIN_ITEM_COVERAGE` | 0.50 | At least 50% of dialogues must discuss each item |
| `MIN_DIALOGUE_COVERAGE` | 0.50 | At least 4/8 items discussed per dialogue |
| `MAX_CORPUS_NA_RATE` | 0.25 | At most 25% of all (dialogue × item) cells are NA |

### 2.2 Reliability with NA

Krippendorff's alpha handles missing data natively. For ICC, we have options:

1. **Exclude NA rows** - ICC on only fully-observed units
2. **Impute NA as 0** - Compute ICC with NA→0 (biased)
3. **Item-level ICC** - ICC per item, excluding NA dialogues

**Decision**: Use option 3 (item-level ICC excluding NA) for reliability metrics.

### 2.3 Separation with NA

The MDD vs control separation uses totals. With NA:

1. **Imputed totals** - Use `imputed_total` (NA→0), biased toward 0
2. **Prorated totals** - Use `prorated_total` where valid, exclude others
3. **Both metrics** - Report both for transparency

**Decision**: Report both metrics; gate on prorated if coverage allows.

---

## 3. New Coverage Metrics

### 3.1 Schema

```python
# src/vibe_check/diagnostics/coverage.py
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from vibe_check.constants import PHQ8_ITEMS


class CoverageMetrics(BaseModel):
    """NA coverage statistics for a scored run."""

    model_config = ConfigDict(extra="forbid")

    # Corpus-level
    total_cells: int = Field(ge=0, description="n_dialogues × 8")
    na_cells: int = Field(ge=0, description="Count of NA item scores")
    corpus_na_rate: float = Field(
        ge=0.0, le=1.0, description="na_cells / total_cells"
    )

    # Per-item coverage (what % of dialogues discuss each item)
    item_coverage: dict[str, float] = Field(description="Per-item discussion rate")
    min_item_coverage: float = Field(ge=0.0, le=1.0, description="Lowest item coverage")
    max_item_coverage: float = Field(ge=0.0, le=1.0, description="Highest item coverage")

    # Per-dialogue coverage
    dialogues_with_min_coverage: int = Field(
        ge=0, description="Dialogues with >= 4 items discussed"
    )
    dialogues_with_proration_valid: int = Field(
        ge=0, description="Dialogues with >= 7 items discussed"
    )
    dialogue_coverage_mean: float = Field(
        ge=0.0, le=1.0, description="Mean coverage across dialogues"
    )
    dialogue_coverage_std: float = Field(ge=0.0, description="Std dev of coverage")

    # Distribution
    coverage_histogram: dict[int, int] = Field(
        description="Count of dialogues by discussed_count (0-8)"
    )


def compute_coverage_metrics(
    rows: list["AggregatedPHQ8NA"],
) -> CoverageMetrics:
    """Compute coverage metrics from NA-aware aggregated results.

    Args:
        rows: List of AggregatedPHQ8NA results.

    Returns:
        CoverageMetrics with corpus and per-item statistics.
    """
    import numpy as np

    n_dialogues = len(rows)
    n_items = len(PHQ8_ITEMS)
    total_cells = n_dialogues * n_items

    # Count NAs per item
    item_na_counts: dict[str, int] = {item: 0 for item in PHQ8_ITEMS}
    na_cells = 0

    dialogue_coverages: list[float] = []
    coverage_hist: dict[int, int] = {i: 0 for i in range(9)}

    min_coverage_count = 0
    proration_valid_count = 0

    for row in rows:
        discussed_count = row.total_aggregation.discussed_count
        coverage_hist[discussed_count] += 1
        dialogue_coverages.append(discussed_count / 8)

        if row.total_aggregation.is_min_coverage:
            min_coverage_count += 1
        if row.total_aggregation.is_proration_valid:
            proration_valid_count += 1

        for item in PHQ8_ITEMS:
            item_agg = row.item_aggregations[item]
            if item_agg.consensus_assertion == "not_mentioned":
                item_na_counts[item] += 1
                na_cells += 1

    # Per-item coverage (% of dialogues that discuss each item)
    item_coverage = {
        item: (n_dialogues - na_count) / n_dialogues if n_dialogues > 0 else 0.0
        for item, na_count in item_na_counts.items()
    }

    coverage_values = list(item_coverage.values())
    dialogue_coverages_arr = np.array(dialogue_coverages)

    return CoverageMetrics(
        total_cells=total_cells,
        na_cells=na_cells,
        corpus_na_rate=na_cells / total_cells if total_cells > 0 else 0.0,
        item_coverage=item_coverage,
        min_item_coverage=min(coverage_values) if coverage_values else 0.0,
        max_item_coverage=max(coverage_values) if coverage_values else 0.0,
        dialogues_with_min_coverage=min_coverage_count,
        dialogues_with_proration_valid=proration_valid_count,
        dialogue_coverage_mean=float(np.mean(dialogue_coverages_arr)) if dialogue_coverages else 0.0,
        dialogue_coverage_std=float(np.std(dialogue_coverages_arr)) if dialogue_coverages else 0.0,
        coverage_histogram=coverage_hist,
    )
```

---

## 4. Updated Report Schema

### 4.1 DiagnosticReportNA

```python
# src/vibe_check/diagnostics/report.py (additions)

from vibe_check.diagnostics.coverage import CoverageMetrics


class SeparationMetricsNA(BaseModel):
    """NA-aware separation metrics with both imputed and prorated totals."""

    model_config = ConfigDict(extra="forbid")

    # Imputed totals (NA=0, all dialogues)
    mdd_mean_imputed: float
    mdd_std_imputed: float
    control_mean_imputed: float
    control_std_imputed: float
    cohens_d_imputed: float
    p_value_imputed: float

    # Prorated totals (only dialogues with is_proration_valid=True)
    n_mdd_prorated: int = Field(ge=0, description="MDD dialogues with valid proration")
    n_control_prorated: int = Field(ge=0, description="Control dialogues with valid proration")
    mdd_mean_prorated: float | None = Field(description="None if n_mdd_prorated == 0")
    mdd_std_prorated: float | None
    control_mean_prorated: float | None = Field(description="None if n_control_prorated == 0")
    control_std_prorated: float | None
    cohens_d_prorated: float | None
    p_value_prorated: float | None

    # Validity flags
    is_imputed_valid: bool = Field(description="Imputed separation passes gates")
    is_prorated_valid: bool = Field(description="Prorated separation passes gates (if available)")


class ArbitrationMetricsNA(BaseModel):
    """NA-aware arbitration metrics."""

    model_config = ConfigDict(extra="forbid")

    # Overall arbitration (same as v1)
    overall_rate: float = Field(ge=0.0, le=1.0)
    total_contested: int = Field(ge=0)
    total_arbitrated: int = Field(ge=0)

    # NA-specific arbitration
    na_to_numeric_count: int = Field(
        ge=0, description="Judge overrode NA to numeric"
    )
    numeric_to_na_count: int = Field(
        ge=0, description="Judge overrode numeric to NA"
    )
    mixed_arbitration_rate: float = Field(
        ge=0.0, le=1.0, description="Rate of mixed NA+numeric arbitrations"
    )

    # Judge behavior
    judge_agreement_with_mode: float = Field(ge=0.0, le=1.0)
    judge_na_confirmation_rate: float | None = Field(
        description="When majority voted NA, how often judge confirmed"
    )


class DiagnosticReportNA(BaseModel):
    """NA-aware diagnostic report."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    computed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    n_dialogues: int = Field(ge=0)
    n_mdd: int = Field(ge=0)
    n_control: int = Field(ge=0)

    # NEW: Coverage metrics
    coverage: CoverageMetrics

    reliability: ReliabilityMetrics  # Updated to handle NA
    consistency: ConsistencyMetrics
    separation: SeparationMetricsNA  # Updated with dual metrics
    arbitration: ArbitrationMetricsNA  # Updated with NA-specific stats

    # Gates
    passes_coverage_gate: bool  # NEW
    passes_reliability_gate: bool
    passes_consistency_gate: bool
    passes_separation_gate: bool
    passes_arbitration_gate: bool

    @property
    def passes_all_gates(self) -> bool:
        return all([
            self.passes_coverage_gate,
            self.passes_reliability_gate,
            self.passes_consistency_gate,
            self.passes_separation_gate,
            self.passes_arbitration_gate,
        ])
```

---

## 5. TDD Test Cases

### 5.1 Coverage Metrics Tests

```python
# tests/unit/test_diagnostics_coverage.py
import pytest

from vibe_check.constants import PHQ8_ITEMS
from vibe_check.diagnostics.coverage import CoverageMetrics, compute_coverage_metrics


def make_mock_aggregated_na(
    file_id: str,
    na_items: set[str],
    condition: str = "mdd",
) -> "AggregatedPHQ8NA":
    """Create mock AggregatedPHQ8NA for testing."""
    from vibe_check.schemas.output import (
        AggregatedPHQ8NA,
        ItemAggregationNA,
        TotalAggregationNA,
    )

    item_aggregations = {}
    discussed_count = 8 - len(na_items)

    for item in PHQ8_ITEMS:
        if item in na_items:
            item_aggregations[item] = ItemAggregationNA(
                votes=[None] * 6,
                assertions=["not_mentioned"] * 6,
                numeric_votes=[],
                consensus_score=None,
                consensus_assertion="not_mentioned",
                confidence=None,
                evidence=[],
                na_count=6,
                p_not_mentioned=1.0,
            )
        else:
            item_aggregations[item] = ItemAggregationNA(
                votes=[1] * 6,
                assertions=["present"] * 6,
                numeric_votes=[1] * 6,
                consensus_score=1,
                consensus_assertion="present",
                confidence=0.8,
                evidence=["test"],
                na_count=0,
                p_not_mentioned=0.0,
            )

    return AggregatedPHQ8NA(
        file_id=file_id,
        condition=condition,
        item_aggregations=item_aggregations,
        total_aggregation=TotalAggregationNA(
            discussed_count=discussed_count,
            discussed_sum=discussed_count,  # score=1 for each
            coverage=discussed_count / 8,
            prorated_total=(
                discussed_count * 8 / discussed_count if discussed_count >= 7 else None
            ),
            prorated_total_rounded=8 if discussed_count >= 7 else None,
            imputed_total=discussed_count,
            na_count=len(na_items),
            is_min_coverage=discussed_count >= 4,
            is_proration_valid=discussed_count >= 7,
            severity_bucket_phq_like="mild" if discussed_count >= 7 else None,
        ),
        prompt_version="v2.0.0",
        juror_models=["test"],
        runs_per_model=2,
        arbitration_triggered=False,
        judge_model=None,
    )


class TestComputeCoverageMetrics:
    """Test coverage metrics computation."""

    def test_full_coverage(self):
        """All items discussed in all dialogues."""
        rows = [make_mock_aggregated_na(f"d{i}", na_items=set()) for i in range(10)]
        metrics = compute_coverage_metrics(rows)

        assert metrics.total_cells == 80  # 10 × 8
        assert metrics.na_cells == 0
        assert metrics.corpus_na_rate == 0.0
        assert metrics.min_item_coverage == 1.0
        assert metrics.max_item_coverage == 1.0
        assert metrics.dialogues_with_proration_valid == 10

    def test_partial_coverage(self):
        """Some items are NA."""
        rows = [
            make_mock_aggregated_na("d1", na_items={"fatigue", "appetite"}),
            make_mock_aggregated_na("d2", na_items={"fatigue"}),
            make_mock_aggregated_na("d3", na_items=set()),
            make_mock_aggregated_na("d4", na_items={"fatigue", "appetite", "psychomotor"}),
        ]
        metrics = compute_coverage_metrics(rows)

        assert metrics.total_cells == 32  # 4 × 8
        assert metrics.na_cells == 6  # 2 + 1 + 0 + 3
        assert metrics.corpus_na_rate == pytest.approx(6 / 32)

        # fatigue is NA in 3/4 dialogues
        assert metrics.item_coverage["fatigue"] == pytest.approx(0.25)
        # anhedonia is never NA
        assert metrics.item_coverage["anhedonia"] == 1.0

    def test_coverage_histogram(self):
        """Coverage histogram counts dialogues by discussed_count."""
        rows = [
            make_mock_aggregated_na("d1", na_items=set()),  # 8 discussed
            make_mock_aggregated_na("d2", na_items={"fatigue"}),  # 7 discussed
            make_mock_aggregated_na("d3", na_items={"fatigue", "appetite"}),  # 6 discussed
        ]
        metrics = compute_coverage_metrics(rows)

        assert metrics.coverage_histogram[8] == 1
        assert metrics.coverage_histogram[7] == 1
        assert metrics.coverage_histogram[6] == 1
        assert metrics.coverage_histogram[5] == 0

    def test_proration_validity_count(self):
        """Count dialogues with valid proration (>= 7 items)."""
        rows = [
            make_mock_aggregated_na("d1", na_items=set()),  # 8 items, valid
            make_mock_aggregated_na("d2", na_items={"fatigue"}),  # 7 items, valid
            make_mock_aggregated_na("d3", na_items={"fatigue", "appetite"}),  # 6 items, invalid
        ]
        metrics = compute_coverage_metrics(rows)

        assert metrics.dialogues_with_proration_valid == 2
        assert metrics.dialogues_with_min_coverage == 3  # All >= 4

    def test_empty_input(self):
        """Empty input returns zero metrics."""
        metrics = compute_coverage_metrics([])

        assert metrics.total_cells == 0
        assert metrics.na_cells == 0
        assert metrics.corpus_na_rate == 0.0


class TestCoverageGates:
    """Test coverage-based quality gates."""

    def test_passes_coverage_gate_high_coverage(self):
        """High coverage passes gate."""
        rows = [make_mock_aggregated_na(f"d{i}", na_items=set()) for i in range(10)]
        metrics = compute_coverage_metrics(rows)

        # Gate: corpus_na_rate <= 0.25 AND min_item_coverage >= 0.50
        passes = (
            metrics.corpus_na_rate <= 0.25
            and metrics.min_item_coverage >= 0.50
        )
        assert passes is True

    def test_fails_coverage_gate_high_na_rate(self):
        """High NA rate fails gate."""
        # Every dialogue has 3 NA items = 37.5% NA rate
        rows = [
            make_mock_aggregated_na(f"d{i}", na_items={"fatigue", "appetite", "psychomotor"})
            for i in range(10)
        ]
        metrics = compute_coverage_metrics(rows)

        assert metrics.corpus_na_rate > 0.25  # Fails gate

    def test_fails_coverage_gate_low_item_coverage(self):
        """Item with < 50% coverage fails gate."""
        # psychomotor is NA in 6/10 dialogues = 40% coverage
        rows = []
        for i in range(10):
            if i < 6:
                rows.append(make_mock_aggregated_na(f"d{i}", na_items={"psychomotor"}))
            else:
                rows.append(make_mock_aggregated_na(f"d{i}", na_items=set()))

        metrics = compute_coverage_metrics(rows)

        assert metrics.item_coverage["psychomotor"] == pytest.approx(0.4)
        assert metrics.min_item_coverage < 0.50  # Fails gate
```

### 5.2 Separation Metrics Tests

```python
# tests/unit/test_diagnostics_separation_na.py
import pytest
import numpy as np

from vibe_check.diagnostics.separation import compute_separation_metrics_na


class TestComputeSeparationMetricsNA:
    """Test NA-aware separation metrics."""

    def test_imputed_separation_all_dialogues(self):
        """Imputed metrics use all dialogues with NA=0."""
        rows = [
            # MDD with high scores
            make_mock_aggregated_na("m1", na_items=set(), condition="mdd"),
            make_mock_aggregated_na("m2", na_items={"fatigue"}, condition="mdd"),
            # Control with low scores (modified to have score=0)
            make_mock_aggregated_na("c1", na_items=set(), condition="control"),
            make_mock_aggregated_na("c2", na_items={"fatigue", "appetite"}, condition="control"),
        ]

        metrics = compute_separation_metrics_na(rows)

        # All dialogues contribute to imputed metrics
        assert metrics.mdd_mean_imputed > 0
        assert metrics.control_mean_imputed > 0

    def test_prorated_separation_filters_dialogues(self):
        """Prorated metrics only use dialogues with >= 7 items."""
        rows = [
            # MDD: 1 valid proration, 1 invalid
            make_mock_aggregated_na("m1", na_items=set(), condition="mdd"),  # 8 items
            make_mock_aggregated_na("m2", na_items={"fatigue", "appetite"}, condition="mdd"),  # 6 items
            # Control: both valid
            make_mock_aggregated_na("c1", na_items=set(), condition="control"),
            make_mock_aggregated_na("c2", na_items={"fatigue"}, condition="control"),  # 7 items
        ]

        metrics = compute_separation_metrics_na(rows)

        assert metrics.n_mdd_prorated == 1  # Only m1
        assert metrics.n_control_prorated == 2  # c1 and c2

    def test_prorated_none_when_no_valid_dialogues(self):
        """Prorated metrics are None when no dialogues have valid proration."""
        rows = [
            # All have < 7 items
            make_mock_aggregated_na("m1", na_items={"a", "b"}, condition="mdd"),  # 6 items
            make_mock_aggregated_na("c1", na_items={"a", "b", "c"}, condition="control"),  # 5 items
        ]

        metrics = compute_separation_metrics_na(rows)

        assert metrics.n_mdd_prorated == 0
        assert metrics.mdd_mean_prorated is None
        assert metrics.cohens_d_prorated is None
        assert metrics.is_prorated_valid is False


class TestSeparationGates:
    """Test separation gate logic."""

    def test_gate_uses_prorated_when_available(self):
        """Separation gate prefers prorated metrics when available."""
        # Create rows where prorated would pass but imputed would fail
        # (This is conceptual - actual implementation details may vary)
        pass  # Implementation-specific

    def test_gate_falls_back_to_imputed(self):
        """Gate uses imputed when prorated not available."""
        pass  # Implementation-specific
```

### 5.3 Reliability with NA Tests

```python
# tests/unit/test_diagnostics_reliability_na.py
import pytest
import numpy as np

from vibe_check.diagnostics.reliability import (
    compute_krippendorff_alpha_na,
    compute_icc_per_item_na,
)


class TestKrippendorffAlphaNA:
    """Test Krippendorff's alpha with NA data."""

    def test_handles_missing_data(self):
        """Krippendorff's alpha handles NA votes natively."""
        # votes[dialogue, item, juror] with some None values
        votes = np.array([
            [[1, 1, 1], [2, 2, None]],  # Dialogue 0: item 0 complete, item 1 partial
            [[2, 2, 2], [None, None, None]],  # Dialogue 1: item 0 complete, item 1 all NA
        ], dtype=float)

        # Replace None with np.nan for computation
        votes = np.where(votes == None, np.nan, votes)

        alpha = compute_krippendorff_alpha_na(votes)

        # Should not raise, should return valid float
        assert isinstance(alpha, float)
        assert -1.0 <= alpha <= 1.0 or np.isnan(alpha)

    def test_perfect_agreement_with_na(self):
        """Perfect agreement on observed data."""
        votes = np.array([
            [[1, 1, 1], [2, 2, 2]],
            [[1, 1, 1], [np.nan, np.nan, np.nan]],  # Item 1 all NA
        ])

        alpha = compute_krippendorff_alpha_na(votes)

        # Should be high (near 1.0) for observed data
        assert alpha > 0.9 or np.isnan(alpha)


class TestICCPerItemNA:
    """Test ICC computed per-item excluding NA."""

    def test_excludes_na_dialogues_per_item(self):
        """ICC per item excludes dialogues where item is NA."""
        # votes[dialogue, item, juror]
        votes = np.array([
            [[1, 1, 1], [2, 2, 2]],  # Both items observed
            [[1, 1, 1], [np.nan, np.nan, np.nan]],  # Item 1 is NA
            [[2, 2, 2], [2, 2, 2]],  # Both items observed
        ])

        icc_per_item = compute_icc_per_item_na(votes, item_names=["item0", "item1"])

        # Both items should have valid ICC
        assert "item0" in icc_per_item
        assert "item1" in icc_per_item
        # item0 has 3 dialogues, item1 has 2 dialogues
```

### 5.4 Integration Tests

```python
# tests/integration/test_diagnostics_na.py
import pytest
from pathlib import Path

from vibe_check.diagnostics import RunDiagnosticsNA


class TestRunDiagnosticsNA:
    """Integration tests for NA-aware diagnostics."""

    def test_compute_with_na_data(self, tmp_path: Path, scored_na_jsonl_fixture):
        """Full diagnostic computation with NA data."""
        diagnostics = RunDiagnosticsNA(scored_jsonl=scored_na_jsonl_fixture)
        report = diagnostics.compute()

        # Coverage metrics present
        assert report.coverage is not None
        assert report.coverage.corpus_na_rate >= 0.0

        # All gates computed
        assert isinstance(report.passes_coverage_gate, bool)
        assert isinstance(report.passes_reliability_gate, bool)
        assert isinstance(report.passes_separation_gate, bool)

    def test_cli_diagnostics_with_na(self, cli_runner, tmp_path: Path, scored_na_jsonl_fixture):
        """CLI diagnostics command works with NA data."""
        output_path = tmp_path / "report.json"

        result = cli_runner.invoke([
            "diagnostics",
            "--scored", str(scored_na_jsonl_fixture),
            "--output", str(output_path),
            "--format", "json",
        ])

        assert result.exit_code == 0
        assert output_path.exists()

        import json
        report = json.loads(output_path.read_text())

        # Coverage section present
        assert "coverage" in report
        assert "corpus_na_rate" in report["coverage"]
```

---

## 6. Constants

```python
# src/vibe_check/constants.py (additions)

# Coverage gates (SPEC-18)
MIN_ITEM_COVERAGE: float = 0.50  # Each item discussed in >= 50% of dialogues
MIN_DIALOGUE_COVERAGE: float = 0.50  # >= 4/8 items per dialogue (same as is_min_coverage)
MAX_CORPUS_NA_RATE: float = 0.25  # At most 25% of cells are NA
```

---

## 7. Files Affected

| File | Change Type |
|------|-------------|
| `src/vibe_check/diagnostics/coverage.py` | **NEW** |
| `src/vibe_check/diagnostics/report.py` | **EXTEND** - Add NA-aware schemas |
| `src/vibe_check/diagnostics/runner.py` | **EXTEND** - Add `RunDiagnosticsNA` |
| `src/vibe_check/diagnostics/reliability.py` | **EXTEND** - Handle NA in ICC |
| `src/vibe_check/diagnostics/separation.py` | **EXTEND** - Dual imputed/prorated |
| `src/vibe_check/diagnostics/arbitration.py` | **EXTEND** - NA arbitration stats |
| `src/vibe_check/constants.py` | **EXTEND** - Coverage thresholds |
| `tests/unit/test_diagnostics_coverage.py` | **NEW** |
| `tests/unit/test_diagnostics_separation_na.py` | **NEW** |
| `tests/unit/test_diagnostics_reliability_na.py` | **NEW** |
| `tests/integration/test_diagnostics_na.py` | **NEW** |

---

## 8. Acceptance Criteria

- [ ] All test cases in Section 5 pass
- [ ] Coverage metrics computed correctly
- [ ] Krippendorff's alpha handles NA votes
- [ ] ICC computed per-item excluding NA dialogues
- [ ] Separation metrics report both imputed and prorated
- [ ] New `passes_coverage_gate` in report
- [ ] CLI diagnostics works with NA data
- [ ] Ruff + mypy pass

---

## 9. Sign-Off

| Role | Status |
|------|--------|
| Author | DRAFT |
| Senior Review | PENDING |
