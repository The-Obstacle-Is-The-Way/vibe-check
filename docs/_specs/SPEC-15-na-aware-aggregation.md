# SPEC-15: NA-Aware Aggregation

> **Status**: DRAFT v2 - Revised per senior review
> **Depends On**: SPEC-13 (NA-Aware Schema)
> **Blocks**: SPEC-16 (Export), SPEC-17 (Judge)

---

## 1. Overview

This spec defines TDD requirements for updating the aggregation engine to handle NA (not_mentioned) votes while maintaining compatibility with existing systems.

**Core Change**: NA votes excluded from 0-3 posterior; `total_posterior` remains 25 bins (NA items contribute point-mass at 0).

---

## 2. Design Decisions

### 2.1 Posterior Semantics (Compatibility)

**Decision**: Keep `total_posterior` as 25 bins (0-24) for compatibility.

- NA items contribute a **point-mass at 0** to convolution (equivalent to imputed_total)
- This preserves existing severity bucket logic, diagnostics, and export
- A separate `discussed_sum_posterior` can be computed for research if needed

### 2.2 Severity Bucket Handling (SSOT §14)

**Decision**: Add `severity_bucket_phq_like` gated by `is_proration_valid`.

- `severity_bucket`: Always computed from `imputed_total` (for ML use)
- `severity_bucket_phq_like`: Only set when `discussed_count >= 7` (clinically comparable)

### 2.3 Consensus Assertion Rules

**Decision**: Preserve `possible` as a first-class consensus outcome.

| NA Rate | Numeric Mode | Consensus Assertion |
|---------|--------------|---------------------|
| > 50% (`na_count > juror_count / 2`) | N/A | `not_mentioned` |
| ≤ 50% | Mode = 0 | `denied` |
| ≤ 50% | Mode = 1 AND majority `possible` | `possible` |
| ≤ 50% | Mode = 1-3 (not majority `possible`) | `present` |

### 2.4 Arbitration on Total Score

**Decision**: Use `imputed_total` for global arbitration threshold (total_std).

- Under NA, per-juror `imputed_total` is used (NA→0)
- High NA dispersion may inflate std but doesn't invalidate the check

---

## 3. Schema: `ItemAggregationNA`

```python
# File: src/vibe_check/schemas/output.py (updated)

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

Assertion = Literal["present", "denied", "possible", "not_mentioned"]


class ItemAggregationNA(BaseModel):
    """Aggregated statistics for one PHQ-8 item with NA handling."""

    model_config = ConfigDict(extra="forbid")

    # Raw votes (including None for not_mentioned)
    votes: list[int | None]
    assertions: list[Assertion]

    # Numeric vote stats (excluding NA)
    numeric_votes: list[int]
    vote_counts: dict[str, int]  # "0", "1", "2", "3" counts
    posterior: dict[str, float] | None  # None if all votes are NA

    # Aggregated stats (from numeric votes only)
    mode: int | None  # None if all NA
    expected: float | None
    entropy: float | None
    vote_range: int | None
    clinical_prob: float | None  # P(score >= 2) among numeric votes

    # NA tracking
    na_count: int
    p_not_mentioned: float  # na_count / len(votes)

    # Consensus
    consensus_score: int | None  # None if consensus is not_mentioned
    consensus_assertion: Assertion

    # Arbitration
    needs_arbitration: bool = False
    arbitration_reason: str | None = None
```

---

## 4. TDD Test Cases

### 4.1 `compute_item_posterior` (No Change Needed)

The existing function works on `list[int]`, which is the filtered numeric votes.

```python
# File: tests/unit/test_posterior.py

class TestPosteriorWithFilteredVotes:
    """Posterior tests with pre-filtered numeric votes."""

    def test_empty_numeric_raises(self):
        """All-NA case: empty numeric list raises."""
        numeric_votes: list[int] = []
        with pytest.raises(ValueError, match="votes must be non-empty"):
            compute_item_posterior(numeric_votes)

    def test_filtered_votes_valid(self):
        """Numeric votes after filtering NA."""
        numeric_votes = [1, 2, 1, 1]  # Filtered from [1, None, 2, 1, None, 1]
        posterior = compute_item_posterior(numeric_votes)
        assert posterior.shape == (4,)
        assert abs(posterior.sum() - 1.0) < 1e-6
        assert np.argmax(posterior) == 1  # Mode is 1
```

### 4.2 `compute_item_aggregation_with_na`

```python
# File: tests/unit/test_aggregate.py

from vibe_check.aggregation.aggregate import compute_item_aggregation_with_na
from vibe_check.schemas.output import ItemAggregationNA


class TestItemAggregationNA:
    """Item aggregation with NA handling."""

    def test_unanimous_present(self):
        """All jurors agree: score=2, assertion=present."""
        result = compute_item_aggregation_with_na(
            votes=[2, 2, 2, 2, 2, 2],
            assertions=["present", "present", "present", "present", "present", "present"],
        )
        assert result.consensus_score == 2
        assert result.consensus_assertion == "present"
        assert result.p_not_mentioned == 0.0
        assert result.na_count == 0
        assert result.numeric_votes == [2, 2, 2, 2, 2, 2]
        assert result.mode == 2

    def test_unanimous_not_mentioned(self):
        """All jurors say not_mentioned."""
        result = compute_item_aggregation_with_na(
            votes=[None, None, None, None, None, None],
            assertions=["not_mentioned"] * 6,
        )
        assert result.consensus_score is None
        assert result.consensus_assertion == "not_mentioned"
        assert result.p_not_mentioned == 1.0
        assert result.na_count == 6
        assert result.numeric_votes == []
        assert result.posterior is None
        assert result.mode is None

    def test_majority_not_mentioned_4_of_6(self):
        """4/6 jurors say not_mentioned (> 50%)."""
        result = compute_item_aggregation_with_na(
            votes=[2, None, None, None, None, 1],
            assertions=["present", "not_mentioned", "not_mentioned",
                       "not_mentioned", "not_mentioned", "present"],
        )
        # 4/6 = 66.7% > 50% → consensus is not_mentioned
        assert result.consensus_assertion == "not_mentioned"
        assert result.consensus_score is None
        assert result.p_not_mentioned == pytest.approx(4/6)

    def test_exactly_50_percent_na_uses_numeric(self):
        """3/6 jurors say not_mentioned (== 50%): use numeric votes."""
        result = compute_item_aggregation_with_na(
            votes=[1, None, 2, 1, None, None],
            assertions=["present", "not_mentioned", "present",
                       "present", "not_mentioned", "not_mentioned"],
        )
        # 3/6 = 50% is NOT > 50%, so use numeric mode
        assert result.consensus_assertion == "present"
        assert result.consensus_score == 1  # Mode of [1, 2, 1]
        assert result.p_not_mentioned == 0.5

    def test_minority_not_mentioned_uses_numeric_mode(self):
        """2/6 jurors say not_mentioned: use numeric mode."""
        result = compute_item_aggregation_with_na(
            votes=[1, None, 2, 1, None, 1],
            assertions=["present", "not_mentioned", "present",
                       "present", "not_mentioned", "present"],
        )
        # 2/6 = 33% < 50% → use numeric mode
        assert result.consensus_assertion == "present"
        assert result.consensus_score == 1  # Mode of [1, 2, 1, 1]
        assert result.p_not_mentioned == pytest.approx(2/6)

    def test_denied_consensus(self):
        """Numeric mode is 0 → consensus is denied."""
        result = compute_item_aggregation_with_na(
            votes=[0, 0, 0, 0, None, 0],
            assertions=["denied", "denied", "denied", "denied",
                       "not_mentioned", "denied"],
        )
        assert result.consensus_score == 0
        assert result.consensus_assertion == "denied"

    def test_possible_consensus_majority(self):
        """Mode=1 with majority 'possible' → consensus is possible."""
        result = compute_item_aggregation_with_na(
            votes=[1, 1, 1, 1, None, None],
            assertions=["possible", "possible", "possible", "possible",
                       "not_mentioned", "not_mentioned"],
        )
        # Mode = 1, majority of numeric assertions are "possible"
        assert result.consensus_score == 1
        assert result.consensus_assertion == "possible"

    def test_possible_minority_becomes_present(self):
        """Mode=1 but majority 'present' → consensus is present."""
        result = compute_item_aggregation_with_na(
            votes=[1, 1, 1, 2, None, None],
            assertions=["present", "present", "possible", "present",
                       "not_mentioned", "not_mentioned"],
        )
        # Mode = 1, but majority of numeric assertions are "present"
        assert result.consensus_score == 1
        assert result.consensus_assertion == "present"


class TestItemAggregationArbitration:
    """Arbitration trigger tests."""

    def test_high_na_rate_triggers_arbitration(self):
        """NA rate > threshold triggers arbitration."""
        result = compute_item_aggregation_with_na(
            votes=[1, None, None, None, None, None],
            assertions=["present"] + ["not_mentioned"] * 5,
            na_rate_arbitration_threshold=0.67,
        )
        # 5/6 = 83% > 67% → arbitration
        assert result.needs_arbitration is True
        assert "high_na_rate" in result.arbitration_reason

    def test_high_vote_range_triggers_arbitration(self):
        """Vote range > threshold triggers arbitration."""
        result = compute_item_aggregation_with_na(
            votes=[0, 3, 0, 3, None, None],
            assertions=["denied", "present", "denied", "present",
                       "not_mentioned", "not_mentioned"],
            range_threshold=2,
        )
        # Range = 3 > 2 → arbitration
        assert result.needs_arbitration is True
        assert "vote_range" in result.arbitration_reason or "range" in result.arbitration_reason

    def test_no_arbitration_for_agreement(self):
        """No arbitration when jurors agree."""
        result = compute_item_aggregation_with_na(
            votes=[2, 2, 2, 2, 2, 2],
            assertions=["present"] * 6,
        )
        assert result.needs_arbitration is False
```

### 4.3 Total Score Computation

```python
# File: tests/unit/test_aggregate.py

from vibe_check.aggregation.aggregate import compute_total_score_with_na
from vibe_check.schemas.scoring import PHQ8TotalScore


class TestTotalScoreNA:
    """Total score computation with NA."""

    def test_full_coverage(self):
        """All 8 items scored."""
        item_consensus = {
            "anhedonia": 2, "depressed_mood": 3, "sleep": 1, "fatigue": 2,
            "appetite": 0, "guilt": 1, "concentration": 2, "psychomotor": 0,
        }
        total = compute_total_score_with_na(item_consensus)
        assert total.discussed_count == 8
        assert total.discussed_sum == 11
        assert total.imputed_total == 11
        assert total.is_proration_valid is True
        assert total.prorated_total == 11.0

    def test_partial_coverage_5_items(self):
        """5/8 items scored, 3 NA."""
        item_consensus = {
            "anhedonia": 2, "depressed_mood": 3, "sleep": None, "fatigue": 2,
            "appetite": None, "guilt": None, "concentration": 1, "psychomotor": None,
        }
        # Wait, that's 4 items. Let me fix:
        item_consensus = {
            "anhedonia": 2, "depressed_mood": 3, "sleep": 1, "fatigue": 2,
            "appetite": None, "guilt": None, "concentration": 1, "psychomotor": None,
        }
        # That's 5 scored (2+3+1+2+1=9), 3 NA
        total = compute_total_score_with_na(item_consensus)
        assert total.discussed_count == 5
        assert total.discussed_sum == 9
        assert total.imputed_total == 9
        assert total.is_proration_valid is False  # 5 < 7
        assert total.prorated_total is None

    def test_high_coverage_7_items(self):
        """7/8 items scored, 1 NA."""
        item_consensus = {
            "anhedonia": 2, "depressed_mood": 3, "sleep": 1, "fatigue": 2,
            "appetite": None, "guilt": 2, "concentration": 2, "psychomotor": 2,
        }
        total = compute_total_score_with_na(item_consensus)
        assert total.discussed_count == 7
        assert total.discussed_sum == 14
        assert total.is_proration_valid is True
        assert total.prorated_total == 16.0  # (14/7)*8

    def test_all_na(self):
        """All items NA."""
        item_consensus = {k: None for k in [
            "anhedonia", "depressed_mood", "sleep", "fatigue",
            "appetite", "guilt", "concentration", "psychomotor"
        ]}
        total = compute_total_score_with_na(item_consensus)
        assert total.discussed_count == 0
        assert total.imputed_total == 0
        assert total.is_min_coverage is False
```

### 4.4 Convolution with NA Items (Point-Mass at 0)

```python
# File: tests/unit/test_posterior.py

from vibe_check.aggregation.posterior import convolve_posteriors_with_na
import numpy as np


class TestConvolutionNA:
    """Convolution with NA items as point-mass at 0."""

    def test_all_discussed_8_items(self):
        """All 8 items have posteriors → 25 bins."""
        posteriors = [np.array([0.1, 0.4, 0.3, 0.2]) for _ in range(8)]
        total_dist = convolve_posteriors_with_na(posteriors, na_indices=[])
        assert total_dist.shape == (25,)
        assert abs(total_dist.sum() - 1.0) < 1e-6

    def test_3_na_items_still_25_bins(self):
        """3 NA items → still 25 bins (NA contributes point-mass at 0)."""
        posteriors = [np.array([0.1, 0.4, 0.3, 0.2]) for _ in range(8)]
        na_indices = [2, 4, 6]  # Items 3, 5, 7 are NA
        total_dist = convolve_posteriors_with_na(posteriors, na_indices=na_indices)
        assert total_dist.shape == (25,)
        assert abs(total_dist.sum() - 1.0) < 1e-6
        # With 3 NA items (contributing 0), max possible is 5*3=15
        # But we still have 25 bins (sparse beyond 15)
        assert total_dist[20:].sum() < 0.01  # Very low prob for high scores

    def test_all_na_items(self):
        """All 8 items NA → point-mass at 0."""
        posteriors = [np.array([0.1, 0.4, 0.3, 0.2]) for _ in range(8)]
        na_indices = list(range(8))  # All NA
        total_dist = convolve_posteriors_with_na(posteriors, na_indices=na_indices)
        assert total_dist.shape == (25,)
        assert total_dist[0] == pytest.approx(1.0)  # All mass at 0
        assert total_dist[1:].sum() < 1e-9
```

### 4.5 Severity Bucket with NA

```python
# File: tests/unit/test_aggregate.py

from vibe_check.aggregation.aggregate import get_severity_bucket, get_severity_bucket_phq_like


class TestSeverityBucketNA:
    """Severity bucket tests with NA."""

    def test_imputed_severity_bucket(self):
        """imputed_total determines severity_bucket (always available)."""
        # imputed_total=12 → moderate (10-14)
        bucket = get_severity_bucket(12)
        assert bucket == "10-14"

    def test_phq_like_bucket_when_valid(self):
        """severity_bucket_phq_like only when proration valid."""
        total = PHQ8TotalScore(
            discussed_count=7, discussed_sum=14, coverage=0.875,
            na_count=1, prorated_total=16.0, prorated_total_rounded=16,
            imputed_total=14, is_min_coverage=True, is_proration_valid=True,
        )
        bucket = get_severity_bucket_phq_like(total)
        # Use prorated_total_rounded=16 → 15-19
        assert bucket == "15-19"

    def test_phq_like_bucket_none_when_invalid(self):
        """severity_bucket_phq_like is None when proration invalid."""
        total = PHQ8TotalScore(
            discussed_count=5, discussed_sum=10, coverage=0.625,
            na_count=3, prorated_total=None, prorated_total_rounded=None,
            imputed_total=10, is_min_coverage=True, is_proration_valid=False,
        )
        bucket = get_severity_bucket_phq_like(total)
        assert bucket is None
```

### 4.6 Global Arbitration on Total Score

```python
# File: tests/unit/test_aggregate.py

class TestGlobalArbitrationNA:
    """Global arbitration uses imputed_total."""

    def test_global_arbitration_uses_imputed(self):
        """Total std computed from per-juror imputed totals."""
        # Simulate 6 jurors with different NA patterns
        juror_imputed_totals = [10, 12, 8, 14, 11, 9]
        std = np.std(juror_imputed_totals)
        threshold = 2.0
        assert std > threshold  # Would trigger arbitration
        # This is what aggregate_reports should check

    def test_no_global_arbitration_when_consistent(self):
        """No global arbitration when imputed totals are consistent."""
        juror_imputed_totals = [10, 10, 11, 10, 10, 11]
        std = np.std(juror_imputed_totals)
        threshold = 2.0
        assert std < threshold  # No arbitration
```

---

## 5. Schema: `AggregatedPHQ8NA` (Updated)

```python
# File: src/vibe_check/schemas/output.py (updated AggregatedPHQ8)

class AggregatedPHQ8(BaseModel):
    """Final aggregated output for one dialogue (NA-aware)."""

    model_config = ConfigDict(extra="forbid")

    file_id: str
    condition: Literal["mdd", "control"]

    # Per-item aggregation (now NA-aware)
    items: dict[str, ItemAggregationNA]

    # Total score aggregation
    totals: PHQ8TotalScore  # NEW: replaces separate fields

    # Total posterior (still 25 bins, NA→0)
    total_mode: int = Field(ge=0, le=24)
    total_expected: float = Field(ge=0.0, le=24.0)
    total_std: float = Field(ge=0.0)
    total_posterior: dict[int, float]
    total_ci_90: tuple[int, int]

    # Severity buckets
    severity_bucket: SeverityBucket  # From imputed_total (always available)
    severity_bucket_phq_like: SeverityBucket | None  # Only if is_proration_valid
    severity_bucket_probs: dict[str, float]

    # Final scores (for compatibility)
    final_item_scores: dict[str, int]  # NA→0 for int-only exports
    final_total_score: int = Field(ge=0, le=24)
    final_severity_bucket: SeverityBucket
    final_source: Literal["jury_mode", "jury_expected", "judge_override"]

    # Arbitration
    triggered_arbitration: bool = False
    arbitration_items: list[str] = Field(default_factory=list)
    arbitration_reasons: dict[str, str] = Field(default_factory=dict)

    # Safety
    mentions_self_harm: bool = False
    self_harm_evidence: list[str] = Field(default_factory=list)

    # Provenance
    juror_reports: list[PHQ8Report]
    judge_resolution: dict[str, Any] | None = None
    judge_usage: TokenUsage | None = None
    prompt_version: str
    scored_at: datetime
```

---

## 6. Files Affected

| File | Change Type | Description |
|------|-------------|-------------|
| `src/vibe_check/aggregation/posterior.py` | **MODERATE** | Add `convolve_posteriors_with_na()` |
| `src/vibe_check/aggregation/aggregate.py` | **MAJOR** | NA-aware aggregation logic |
| `src/vibe_check/schemas/output.py` | **MAJOR** | Update `ItemAggregation` → `ItemAggregationNA`, add `totals` |
| `tests/unit/test_posterior.py` | **MODERATE** | Convolution NA tests |
| `tests/unit/test_aggregate.py` | **MAJOR** | All NA aggregation tests |

---

## 7. Acceptance Criteria

- [ ] All tests in Section 4.1-4.6 pass
- [ ] `total_posterior` always has 25 bins
- [ ] NA items contribute point-mass at 0 to convolution
- [ ] `consensus_assertion` can be `possible` (not erased)
- [ ] Exactly 50% NA uses numeric votes (not NA consensus)
- [ ] `severity_bucket_phq_like` is None when `is_proration_valid=False`
- [ ] Global arbitration uses `imputed_total`
- [ ] `ruff check` + `mypy --strict` pass

---

## 8. Sign-Off

| Role | Status |
|------|--------|
| Author | DRAFT v2 |
| Senior Review | PENDING |
