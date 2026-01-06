# SPEC-15: NA-Aware Aggregation

> **Status**: DRAFT - Pending Senior Review
> **Depends On**: SPEC-13 (NA-Aware Schema), SPEC-14 (Clinical Inference Prompts)
> **Blocks**: Pilot scoring run

---

## 1. Overview

This spec defines TDD requirements for updating the aggregation engine to handle NA (not_mentioned) votes.

**Core Change**: When jurors vote `not_mentioned` (score=None), those votes are excluded from the 0-3 posterior calculation. A separate `p_not_mentioned` probability is tracked per item.

---

## 2. Current Aggregation (to be updated)

```python
# Current: All votes are 0-3
votes = [0, 1, 1, 2, 1, 0]  # 6 jurors, all scored
posterior = compute_item_posterior(votes)  # Shape: (4,) for scores 0-3
```

**Problem**: Cannot handle `None` votes.

---

## 3. New Aggregation Logic

### 3.1 Per-Item Vote Handling

```python
# New: Votes can be 0-3 or None
votes = [1, None, 2, 1, None, 1]  # 6 jurors, 2 said "not_mentioned"

# Separate numeric votes from NA votes
numeric_votes = [v for v in votes if v is not None]  # [1, 2, 1, 1]
na_count = sum(1 for v in votes if v is None)  # 2

# Compute posterior over numeric votes only
if numeric_votes:
    posterior = compute_item_posterior(numeric_votes)  # Shape: (4,)
else:
    posterior = None  # All jurors said not_mentioned

# Track NA rate
p_not_mentioned = na_count / len(votes)  # 2/6 = 0.333
```

### 3.2 Consensus Rules for Mixed Votes

| Scenario | Consensus Assertion | Consensus Score |
|----------|-------------------|-----------------|
| All jurors: `not_mentioned` | `not_mentioned` | `None` |
| Majority (>50%) `not_mentioned` | `not_mentioned` | `None` |
| Minority (<50%) `not_mentioned` | Mode of numeric votes | `assertion` from mode |
| Mixed with mode=0 | `denied` | `0` |
| Mixed with mode=1-3 | `present` | Mode value |

---

## 4. TDD Test Cases

### 4.1 `compute_item_posterior` Updates

```python
# TEST: All numeric votes (no change from current)
def test_posterior_all_numeric():
    votes = [0, 1, 1, 2, 1, 0]
    posterior = compute_item_posterior(votes)
    assert posterior.shape == (4,)
    assert abs(posterior.sum() - 1.0) < 1e-6

# TEST: Empty numeric votes raises (all NA)
def test_posterior_all_na_raises():
    votes = [None, None, None, None, None, None]
    numeric = [v for v in votes if v is not None]
    with pytest.raises(ValueError, match="votes must be non-empty"):
        compute_item_posterior(numeric)

# TEST: Mixed votes - NA excluded from posterior
def test_posterior_mixed_votes():
    votes = [1, None, 2, 1, None, 1]
    numeric = [v for v in votes if v is not None]  # [1, 2, 1, 1]
    posterior = compute_item_posterior(numeric)
    assert posterior.shape == (4,)
    # Mode should be 1
    assert np.argmax(posterior) == 1
```

### 4.2 New Function: `compute_item_aggregation_with_na`

```python
def compute_item_aggregation_with_na(
    votes: list[int | None],
    assertions: list[str],  # "present", "denied", "possible", "not_mentioned"
    *,
    dirichlet_alpha: float = 0.5,
) -> ItemAggregationNA:
    """Aggregate item votes with NA handling."""
```

**TDD Test Cases**:

```python
# TEST: All jurors agree on score 2
def test_aggregation_unanimous_present():
    votes = [2, 2, 2, 2, 2, 2]
    assertions = ["present"] * 6
    result = compute_item_aggregation_with_na(votes, assertions)
    assert result.consensus_score == 2
    assert result.consensus_assertion == "present"
    assert result.p_not_mentioned == 0.0
    assert result.na_count == 0

# TEST: All jurors say not_mentioned
def test_aggregation_unanimous_not_mentioned():
    votes = [None, None, None, None, None, None]
    assertions = ["not_mentioned"] * 6
    result = compute_item_aggregation_with_na(votes, assertions)
    assert result.consensus_score is None
    assert result.consensus_assertion == "not_mentioned"
    assert result.p_not_mentioned == 1.0
    assert result.na_count == 6
    assert result.posterior is None  # No numeric votes

# TEST: Majority not_mentioned (4/6)
def test_aggregation_majority_not_mentioned():
    votes = [2, None, None, None, None, 1]
    assertions = ["present", "not_mentioned", "not_mentioned", "not_mentioned", "not_mentioned", "present"]
    result = compute_item_aggregation_with_na(votes, assertions)
    # 4/6 = 66% not_mentioned → consensus is not_mentioned
    assert result.consensus_assertion == "not_mentioned"
    assert result.consensus_score is None
    assert result.p_not_mentioned == pytest.approx(4/6)

# TEST: Minority not_mentioned (2/6), use numeric mode
def test_aggregation_minority_not_mentioned():
    votes = [1, None, 2, 1, None, 1]
    assertions = ["present", "not_mentioned", "present", "present", "not_mentioned", "present"]
    result = compute_item_aggregation_with_na(votes, assertions)
    # 2/6 = 33% not_mentioned → use numeric mode
    assert result.consensus_assertion == "present"
    assert result.consensus_score == 1  # Mode of [1, 2, 1, 1]
    assert result.p_not_mentioned == pytest.approx(2/6)

# TEST: Denied consensus
def test_aggregation_denied_consensus():
    votes = [0, 0, 0, 0, None, 0]
    assertions = ["denied", "denied", "denied", "denied", "not_mentioned", "denied"]
    result = compute_item_aggregation_with_na(votes, assertions)
    assert result.consensus_score == 0
    assert result.consensus_assertion == "denied"

# TEST: Possible in minority doesn't change consensus
def test_aggregation_possible_minority():
    votes = [2, 1, 2, 2, 1, 2]
    assertions = ["present", "possible", "present", "present", "possible", "present"]
    result = compute_item_aggregation_with_na(votes, assertions)
    # Mode is 2, majority assertion is "present"
    assert result.consensus_score == 2
    assert result.consensus_assertion == "present"
```

### 4.3 Total Score Computation with NA

```python
# TEST: Full coverage (8/8 items scored)
def test_total_score_full_coverage():
    item_results = {
        "anhedonia": ItemAggregationNA(consensus_score=2, ...),
        "depressed_mood": ItemAggregationNA(consensus_score=3, ...),
        # ... all 8 items with scores
    }
    total = compute_total_score_with_na(item_results)
    assert total.discussed_count == 8
    assert total.coverage == 1.0
    assert total.is_proration_valid is True
    assert total.prorated_total == total.imputed_total

# TEST: Partial coverage (5/8 items scored)
def test_total_score_partial_coverage():
    item_results = {
        "anhedonia": ItemAggregationNA(consensus_score=2, ...),
        "depressed_mood": ItemAggregationNA(consensus_score=3, ...),
        "sleep": ItemAggregationNA(consensus_score=1, ...),
        "fatigue": ItemAggregationNA(consensus_score=None, ...),  # NA
        "appetite": ItemAggregationNA(consensus_score=None, ...),  # NA
        "guilt": ItemAggregationNA(consensus_score=2, ...),
        "concentration": ItemAggregationNA(consensus_score=None, ...),  # NA
        "psychomotor": ItemAggregationNA(consensus_score=1, ...),
    }
    total = compute_total_score_with_na(item_results)
    assert total.discussed_count == 5
    assert total.discussed_sum == 9  # 2+3+1+2+1
    assert total.na_count == 3
    assert total.coverage == 5/8
    assert total.is_min_coverage is True  # 5 >= 4
    assert total.is_proration_valid is False  # 5 < 7
    assert total.prorated_total is None
    assert total.imputed_total == 9  # NA treated as 0

# TEST: High coverage (7/8) enables proration
def test_total_score_proration_enabled():
    # 7 items scored, sum=14
    item_results = make_item_results(scores=[2, 3, 1, 2, None, 2, 2, 2])
    total = compute_total_score_with_na(item_results)
    assert total.discussed_count == 7
    assert total.discussed_sum == 14
    assert total.is_proration_valid is True
    # prorated = (14/7) * 8 = 16.0
    assert total.prorated_total == 16.0
    assert total.prorated_total_rounded == 16

# TEST: Proration rounding (0.5 rounds up)
def test_total_score_proration_rounding():
    # 7 items, sum=13 → prorated = (13/7)*8 = 14.857... → rounds to 15
    item_results = make_item_results(scores=[2, 2, 2, 2, None, 2, 2, 1])
    total = compute_total_score_with_na(item_results)
    assert total.prorated_total == pytest.approx(14.857, rel=0.01)
    assert total.prorated_total_rounded == 15
```

### 4.4 Convolution with NA Items

```python
# TEST: Convolution excludes NA items
def test_convolve_excludes_na():
    # 5 items have posteriors, 3 are NA
    posteriors = [
        np.array([0.1, 0.6, 0.2, 0.1]),  # item 1
        np.array([0.0, 0.1, 0.3, 0.6]),  # item 2
        None,  # item 3: NA
        np.array([0.2, 0.5, 0.2, 0.1]),  # item 4
        None,  # item 5: NA
        np.array([0.3, 0.4, 0.2, 0.1]),  # item 6
        None,  # item 7: NA
        np.array([0.1, 0.4, 0.3, 0.2]),  # item 8
    ]
    valid_posteriors = [p for p in posteriors if p is not None]
    total_dist = convolve_posteriors(valid_posteriors)
    # 5 items × max 3 each = max total 15
    assert total_dist.shape == (16,)  # 0-15
    assert abs(total_dist.sum() - 1.0) < 1e-6

# TEST: Severity bucket uses imputed total (not prorated)
def test_severity_bucket_uses_imputed():
    # When coverage < 7, severity bucket is based on imputed_total
    total = PHQ8TotalScore(
        discussed_count=5,
        discussed_sum=12,  # 5 items averaging 2.4
        coverage=0.625,
        prorated_total=None,
        prorated_total_rounded=None,
        imputed_total=12,
        na_count=3,
        is_min_coverage=True,
        is_proration_valid=False,
    )
    bucket = get_severity_bucket(total.imputed_total)
    assert bucket == "moderate"  # 10-14 = moderate
```

### 4.5 Arbitration with NA

```python
# TEST: High NA rate triggers arbitration
def test_arbitration_high_na_rate():
    votes = [None, None, None, 1, None, None]  # 5/6 NA
    assertions = ["not_mentioned"] * 5 + ["present"]
    result = compute_item_aggregation_with_na(votes, assertions)
    # When p_not_mentioned > threshold, trigger arbitration
    assert result.needs_arbitration is True
    assert "high_na_rate" in result.arbitration_reason

# TEST: Disagreement between numeric voters triggers arbitration
def test_arbitration_numeric_disagreement():
    votes = [0, 3, 0, 3, None, None]  # High spread in numeric votes
    assertions = ["denied", "present", "denied", "present", "not_mentioned", "not_mentioned"]
    result = compute_item_aggregation_with_na(votes, assertions)
    # vote_range = 3 → triggers arbitration
    assert result.needs_arbitration is True
    assert "vote_range" in result.arbitration_reason or "entropy" in result.arbitration_reason
```

---

## 5. New Schema: `ItemAggregationNA`

```python
class ItemAggregationNA(BaseModel):
    """Aggregated statistics for one PHQ-8 item with NA handling."""

    model_config = ConfigDict(extra="forbid")

    # Raw votes (including None)
    votes: list[int | None]
    assertions: list[str]

    # Numeric vote stats (excluding NA)
    numeric_votes: list[int]
    vote_counts: dict[str, int]  # "0", "1", "2", "3"
    posterior: dict[str, float] | None  # None if all NA

    # Aggregated result
    mode: int | None  # None if all NA
    expected: float | None
    entropy: float | None
    vote_range: int | None
    clinical_prob: float | None  # P(score >= 2)

    # NA tracking
    na_count: int
    p_not_mentioned: float  # na_count / total_votes

    # Consensus
    consensus_score: int | None
    consensus_assertion: Literal["present", "denied", "possible", "not_mentioned"]

    # Arbitration
    needs_arbitration: bool = False
    arbitration_reason: str | None = None
```

---

## 6. Updated `aggregate_reports` Function

```python
def aggregate_reports(
    reports: list[PHQ8Report],
    *,
    file_id: str,
    condition: Literal["mdd", "control"],
    prompt_version: str,
    na_majority_threshold: float = 0.5,  # NEW: when to consensus to NA
    na_rate_arbitration_threshold: float = 0.67,  # NEW: when to arbitrate
    # ... existing params
) -> AggregatedPHQ8NA:
    """Aggregate multiple juror reports with NA handling."""
```

---

## 7. Files Affected

| File | Change Type |
|------|-------------|
| `src/vibe_check/aggregation/posterior.py` | **MODERATE** - Handle empty votes edge case |
| `src/vibe_check/aggregation/aggregate.py` | **MAJOR** - NA-aware aggregation logic |
| `src/vibe_check/schemas/output.py` | **MAJOR** - New `ItemAggregationNA`, update `AggregatedPHQ8` |
| `tests/unit/test_posterior.py` | **MODERATE** - Edge case tests |
| `tests/unit/test_aggregate.py` | **MAJOR** - NA handling tests |

---

## 8. Acceptance Criteria

- [ ] All test cases in Section 4.1-4.5 pass
- [ ] NA votes excluded from 0-3 posterior
- [ ] `p_not_mentioned` tracked per item
- [ ] Majority NA → consensus `not_mentioned`
- [ ] Minority NA → consensus from numeric mode
- [ ] Proration only when `discussed_count >= 7`
- [ ] High NA rate triggers arbitration
- [ ] Ruff + mypy pass

---

## 9. Sign-Off

| Role | Status |
|------|--------|
| Author | DRAFT |
| Senior Review | PENDING |
