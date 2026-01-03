# SPEC-03: Aggregation Engine (Scoring Math)

**Status**: IMPLEMENTED (2026-01-02)
**Slice Type**: Vertical (Pure Computation)
**Dependencies**: SPEC-01 (DevEx), SPEC-02 (Schemas only)
**Estimated Scope**: ~300 lines of code, ~250 lines of tests

---

## 1. Objective

Build the mathematical engine that aggregates multiple PHQ-8 scores into a consensus result. This includes:

1. **Dirichlet smoothing** for vote distributions
2. **Posterior convolution** for total score distribution
3. **Entropy/uncertainty** calculation
4. **Disagreement detection** (when to trigger arbitration)
5. **Credible intervals** and severity bucket probabilities

### Why This Slice?

- **Zero LLM dependencies**: Pure numpy/scipy math
- **Fully deterministic**: Same inputs always produce same outputs
- **Testable with synthetic data**: Generate fake votes, verify math
- **Critical for correctness**: If aggregation is wrong, everything is wrong

### Success Criteria

```python
import numpy as np
import pytest

from vibe_check.aggregation import aggregate_votes, should_arbitrate_item

# Given 6 votes per item (3 models × 2 runs)
votes = {
    "anhedonia": [2, 2, 2, 1, 2, 3],
    "depressed_mood": [0, 0, 1, 0, 0, 0],
    # ... 6 more items
}

items, total_posterior, arbitration_items, arbitration_reasons = aggregate_votes(votes)

# Should compute posterior for each item
assert items["anhedonia"].posterior["2"] > 0.5  # Mode is 2
assert items["anhedonia"].entropy < 1.5  # Reasonable agreement

# Should compute total score distribution
assert len(total_posterior) == 25  # Scores 0-24
assert float(total_posterior.sum()) == pytest.approx(1.0)

# Should detect disagreement
needs_arb, _reason = should_arbitrate_item(
    posterior=np.array([items["anhedonia"].posterior[str(k)] for k in range(4)]),
    votes=votes["anhedonia"],
)
assert needs_arb is False  # Good agreement
```

---

## 2. Deliverables

### 2.1 New Files

| File | Purpose |
|------|---------|
| `src/vibe_check/schemas/scoring.py` | `PHQ8ItemScore`, `PHQ8Report` |
| `src/vibe_check/schemas/output.py` | `ItemAggregation`, `AggregatedPHQ8` |
| `src/vibe_check/aggregation/posterior.py` | Dirichlet smoothing + convolution |
| `src/vibe_check/aggregation/entropy.py` | Uncertainty metrics |
| `src/vibe_check/aggregation/disagreement.py` | Arbitration triggers |
| `src/vibe_check/aggregation/aggregate.py` | Main aggregation function |
| `tests/unit/test_posterior.py` | Posterior math tests |
| `tests/unit/test_entropy.py` | Entropy calculation tests |
| `tests/unit/test_disagreement.py` | Arbitration logic tests |
| `tests/unit/test_aggregate.py` | Integration of aggregation |
| `tests/fixtures/sample_votes.py` | Test vote scenarios |

### 2.2 Updated pyproject.toml

Add dependencies:
```toml
"numpy>=2.0.0",
"scipy>=1.14.0",
```

---

## 3. Data Schemas

### 3.1 PHQ8ItemScore (Per-Model Output)

```python
from typing import Literal
from pydantic import BaseModel, Field

class PHQ8ItemScore(BaseModel):
    """Single PHQ-8 item score from one model run."""

    score: Literal[0, 1, 2, 3] = Field(
        description="0=Not at all, 1=Several days, 2=More than half, 3=Nearly every day"
    )
    confidence: float = Field(ge=0.0, le=1.0, description="Model's self-reported confidence")
    evidence: list[str] = Field(
        default_factory=list,
        max_length=3,
        description="Quotes supporting this score (bounded: short snippets only)"
    )
    insufficient_evidence: bool = Field(
        default=False,
        description="Model flagged lack of evidence for this item"
    )
```

### 3.2 PHQ8Report (Full Model Output)

```python
from datetime import datetime
from pydantic import BaseModel, Field

class TokenUsage(BaseModel):
    """Token usage metadata for a single model call."""

    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    reasoning_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)

class PHQ8Report(BaseModel):
    """Complete PHQ-8 assessment from one model run."""

    model_id: str = Field(description="e.g., 'gpt-5.2', 'claude-sonnet-4-5'")
    run_number: int = Field(ge=1, le=2, description="Run 1 or 2")

    # The 8 items
    anhedonia: PHQ8ItemScore
    depressed_mood: PHQ8ItemScore
    sleep: PHQ8ItemScore
    fatigue: PHQ8ItemScore
    appetite: PHQ8ItemScore
    guilt: PHQ8ItemScore
    concentration: PHQ8ItemScore
    psychomotor: PHQ8ItemScore

    # Derived total (computed from items)
    total_score: int = Field(ge=0, le=24)

    # Self-harm flag (separate from PHQ-8)
    mentions_self_harm: bool = False
    self_harm_evidence: list[str] = Field(default_factory=list, max_length=3)

    # Token usage (optional; used for cost visibility)
    usage: TokenUsage | None = None

    # Metadata
    scored_at: datetime = Field(default_factory=datetime.utcnow)

    @property
    def item_scores(self) -> dict[str, int]:
        """Get all 8 item scores as a dict."""
        return {
            "anhedonia": self.anhedonia.score,
            "depressed_mood": self.depressed_mood.score,
            "sleep": self.sleep.score,
            "fatigue": self.fatigue.score,
            "appetite": self.appetite.score,
            "guilt": self.guilt.score,
            "concentration": self.concentration.score,
            "psychomotor": self.psychomotor.score,
        }
```

### 3.3 ItemAggregation

```python
class ItemAggregation(BaseModel):
    """Aggregated statistics for one PHQ-8 item."""

    # Raw vote distribution
    votes: list[int] = Field(description="All votes for this item")
    vote_counts: dict[str, int] = Field(
        description='Count per score: {"0": 1, "1": 2, "2": 3, "3": 0}'
    )

    # Posterior after Dirichlet smoothing
    posterior: dict[str, float] = Field(
        description='P(score=k): {"0": 0.1, "1": 0.2, "2": 0.5, "3": 0.2}'
    )

    # Summary statistics
    mode: int = Field(ge=0, le=3, description="Most probable score")
    expected: float = Field(ge=0.0, le=3.0, description="E[score]")
    entropy: float = Field(ge=0.0, description="Shannon entropy of posterior")
    vote_range: int = Field(ge=0, le=3, description="max(votes) - min(votes)")

    # Clinical threshold probability
    clinical_prob: float = Field(
        ge=0.0, le=1.0,
        description="P(score >= 2), clinically significant threshold"
    )

    # Flags
    needs_arbitration: bool = False
    arbitration_reason: str | None = None
```

### 3.4 AggregatedPHQ8

```python
class AggregatedPHQ8(BaseModel):
    """Final aggregated output for one dialogue."""

    # Identity
    file_id: str
    condition: Literal["mdd", "control"]

    # Per-item aggregations (8 items)
    items: dict[str, ItemAggregation]

    # Total score distribution (from convolution)
    total_mode: int = Field(ge=0, le=24)
    total_expected: float = Field(ge=0.0, le=24.0)
    total_std: float = Field(ge=0.0)
    total_posterior: dict[int, float] = Field(
        description="P(total=k) for k in 0..24"
    )
    total_ci_90: tuple[int, int] = Field(
        description="90% credible interval [lower, upper]"
    )

    # Severity classification
    severity_bucket: Literal["0-4", "5-9", "10-14", "15-19", "20-24"]
    severity_bucket_probs: dict[str, float] = Field(
        description="P(severity=bucket) for each bucket"
    )

    # Export-ready final labels (jury consensus unless overridden later)
    final_item_scores: dict[str, int] = Field(
        description="Per-item final scores (0-3), default = per-item posterior mode"
    )
    final_total_score: int = Field(ge=0, le=24)
    final_severity_bucket: Literal["0-4", "5-9", "10-14", "15-19", "20-24"]
    final_source: Literal["jury_mode", "jury_expected", "judge_override"]

    # Arbitration metadata
    triggered_arbitration: bool = False
    arbitration_items: list[str] = Field(default_factory=list)
    arbitration_reasons: dict[str, str] = Field(default_factory=dict)

    # Self-harm (any model flagged it)
    mentions_self_harm: bool = False
    self_harm_evidence: list[str] = Field(default_factory=list)

    # Audit trail
    juror_reports: list[PHQ8Report] = Field(description="All 6 juror reports")
    judge_resolution: dict | None = Field(
        default=None,
        description="Judge output if arbitration occurred"
    )

    # Provenance
    prompt_version: str
    scored_at: datetime
```

---

## 4. Core Functions

### 4.1 Posterior Computation (`aggregation/posterior.py`)

```python
import numpy as np

def compute_item_posterior(
    votes: list[int],
    alpha: float = 0.5
) -> np.ndarray:
    """Compute posterior distribution for a single PHQ-8 item.

    Uses Dirichlet smoothing with symmetric prior.

    Args:
        votes: List of scores (each 0-3) from all model runs
        alpha: Dirichlet prior parameter (0.5 = Jeffreys prior)

    Returns:
        Array of shape (4,) with P(score=k) for k in 0,1,2,3
    """
    counts = np.zeros(4)
    for v in votes:
        counts[v] += 1

    # Dirichlet smoothing
    posterior = (counts + alpha) / (len(votes) + 4 * alpha)
    return posterior


def convolve_posteriors(item_posteriors: list[np.ndarray]) -> np.ndarray:
    """Compute total score distribution via convolution.

    Args:
        item_posteriors: List of 8 arrays, each shape (4,)

    Returns:
        Array of shape (25,) with P(total=k) for k in 0..24
    """
    from scipy.signal import convolve

    total_dist = item_posteriors[0]
    for item_post in item_posteriors[1:]:
        total_dist = convolve(total_dist, item_post)

    return total_dist


def compute_credible_interval(
    posterior: np.ndarray,
    alpha: float = 0.10
) -> tuple[int, int]:
    """Compute (1-alpha) credible interval.

    Args:
        posterior: Distribution over scores
        alpha: Tail probability (0.10 for 90% CI)

    Returns:
        (lower, upper) bounds inclusive
    """
    cdf = np.cumsum(posterior)
    lower = int(np.searchsorted(cdf, alpha / 2))
    upper = int(np.searchsorted(cdf, 1 - alpha / 2))
    return (lower, upper)
```

### 4.2 Entropy Calculation (`aggregation/entropy.py`)

```python
import numpy as np

def shannon_entropy(posterior: np.ndarray) -> float:
    """Compute Shannon entropy of a discrete distribution.

    H = -sum(p * log(p)) for p > 0

    Returns:
        Entropy in nats (natural log base)
    """
    # Avoid log(0) by filtering zeros
    p = posterior[posterior > 0]
    return -float(np.sum(p * np.log(p)))


def max_entropy_for_k_outcomes(k: int) -> float:
    """Maximum possible entropy for k outcomes (uniform distribution)."""
    return float(np.log(k))


def normalized_entropy(posterior: np.ndarray) -> float:
    """Entropy normalized to [0, 1] range.

    0 = complete certainty (one outcome has P=1)
    1 = maximum uncertainty (uniform distribution)
    """
    max_ent = max_entropy_for_k_outcomes(len(posterior))
    if max_ent == 0:
        return 0.0
    return shannon_entropy(posterior) / max_ent
```

### 4.3 Disagreement Detection (`aggregation/disagreement.py`)

```python
import numpy as np

def should_arbitrate_item(
    posterior: np.ndarray,
    votes: list[int],
    max_prob_threshold: float = 0.60,
    entropy_threshold: float = 1.2,
    clinical_ambiguity_band: tuple[float, float] = (0.4, 0.6),
    range_threshold: int = 2,
    insufficient_evidence_count: int = 0,
    insufficient_evidence_threshold: int = 2,
) -> tuple[bool, str | None]:
    """Determine if an item needs judge arbitration.

    Triggers (any one is sufficient):
    1. Low max posterior: max(posterior) < 0.60
    2. High entropy: H(posterior) > 1.2
    3. Clinical ambiguity: P(score >= 2) in [0.4, 0.6]
    4. Range safety net: max(votes) - min(votes) >= 2
    5. Insufficient evidence: >=2 jurors flagged insufficient_evidence=True

    Args:
        posterior: Item posterior distribution, shape (4,)
        votes: Raw votes for this item
        max_prob_threshold: Trigger if max prob below this
        entropy_threshold: Trigger if entropy above this
        clinical_ambiguity_band: Trigger if P(clinical) in this range
        range_threshold: Trigger if vote range >= this

    Returns:
        (needs_arbitration: bool, reason: str | None)
    """
    reasons = []

    # 1. Low max posterior
    max_prob = float(np.max(posterior))
    if max_prob < max_prob_threshold:
        reasons.append(f"low_max_prob={max_prob:.2f}")

    # 2. High entropy
    entropy = shannon_entropy(posterior)
    if entropy > entropy_threshold:
        reasons.append(f"high_entropy={entropy:.2f}")

    # 3. Clinical threshold ambiguity
    clinical_prob = float(posterior[2] + posterior[3])  # P(score >= 2)
    if clinical_ambiguity_band[0] <= clinical_prob <= clinical_ambiguity_band[1]:
        reasons.append(f"clinical_ambiguity={clinical_prob:.2f}")

    # 4. Range safety net
    vote_range = max(votes) - min(votes)
    if vote_range >= range_threshold:
        reasons.append(f"vote_range={vote_range}")

    # 5. Insufficient evidence
    if insufficient_evidence_count >= insufficient_evidence_threshold:
        reasons.append(f"insufficient_evidence={insufficient_evidence_count}")

    if reasons:
        return True, "; ".join(reasons)
    return False, None
```

### 4.4 Main Aggregation (`aggregation/aggregate.py`)

```python
from datetime import datetime
from vibe_check.schemas.output import AggregatedPHQ8, ItemAggregation
from vibe_check.schemas.scoring import PHQ8Report

PHQ8_ITEMS = [
    "anhedonia", "depressed_mood", "sleep", "fatigue",
    "appetite", "guilt", "concentration", "psychomotor"
]

SEVERITY_BUCKETS = {
    "0-4": (0, 4),
    "5-9": (5, 9),
    "10-14": (10, 14),
    "15-19": (15, 19),
    "20-24": (20, 24),
}

def aggregate_reports(
    reports: list[PHQ8Report],
    file_id: str,
    condition: str,
    prompt_version: str,
    dirichlet_alpha: float = 0.5,
) -> AggregatedPHQ8:
    """Aggregate multiple juror reports into final consensus.

    Args:
        reports: 6 PHQ8Reports (3 models × 2 runs)
        file_id: Dialogue identifier
        condition: "mdd" or "control"
        prompt_version: Version of scoring prompt used
        dirichlet_alpha: Prior for Dirichlet smoothing

    Returns:
        Aggregated result with posteriors, totals, arbitration flags
    """
    # Extract votes per item
    item_votes = {item: [] for item in PHQ8_ITEMS}
    for report in reports:
        scores = report.item_scores
        for item in PHQ8_ITEMS:
            item_votes[item].append(scores[item])

    # Compute per-item aggregations
    item_posteriors = []
    item_aggregations = {}
    arbitration_items = []
    arbitration_reasons = {}

    for item in PHQ8_ITEMS:
        votes = item_votes[item]
        posterior = compute_item_posterior(votes, alpha=dirichlet_alpha)
        item_posteriors.append(posterior)

        mode = int(np.argmax(posterior))
        expected = float(np.dot(posterior, np.arange(4)))
        entropy = shannon_entropy(posterior)
        clinical_prob = float(posterior[2] + posterior[3])

        # Count jurors who explicitly flagged "insufficient evidence" for this item
        insufficient_count = sum(
            1 for r in reports if getattr(r, item).insufficient_evidence
        )
        needs_arb, reason = should_arbitrate_item(
            posterior,
            votes,
            insufficient_evidence_count=insufficient_count,
        )
        if needs_arb:
            arbitration_items.append(item)
            arbitration_reasons[item] = reason

        item_aggregations[item] = ItemAggregation(
            votes=votes,
            vote_counts={str(k): votes.count(k) for k in range(4)},
            posterior={str(k): float(posterior[k]) for k in range(4)},
            mode=mode,
            expected=expected,
            entropy=entropy,
            vote_range=max(votes) - min(votes),
            clinical_prob=clinical_prob,
            needs_arbitration=needs_arb,
            arbitration_reason=reason,
        )

    # Compute total score distribution via convolution
    total_posterior = convolve_posteriors(item_posteriors)
    total_mode = int(np.argmax(total_posterior))
    total_expected = float(np.dot(total_posterior, np.arange(25)))
    total_std = float(np.sqrt(np.dot(total_posterior, (np.arange(25) - total_expected) ** 2)))
    total_ci = compute_credible_interval(total_posterior, alpha=0.10)

    # Compute severity bucket probabilities
    severity_probs = {}
    for bucket, (lo, hi) in SEVERITY_BUCKETS.items():
        severity_probs[bucket] = float(total_posterior[lo:hi+1].sum())

    # Determine severity bucket from mode
    for bucket, (lo, hi) in SEVERITY_BUCKETS.items():
        if lo <= total_mode <= hi:
            severity_bucket = bucket
            break

    # Self-harm: flag if any model flagged it
    any_self_harm = any(r.mentions_self_harm for r in reports)
    all_evidence = [e for r in reports for e in r.self_harm_evidence]

    # Global arbitration safety net: high disagreement on total juror scores.
    # (Distinct from total posterior std, which is distribution-derived.)
    juror_totals = [r.total_score for r in reports]
    juror_total_std = float(np.std(juror_totals))
    global_arb_reason = None
    if juror_total_std >= 2.0:
        global_arb_reason = f"total_score_std={juror_total_std:.2f}"
        arbitration_items.append("__total__")
        arbitration_reasons["__total__"] = global_arb_reason

    return AggregatedPHQ8(
        file_id=file_id,
        condition=condition,
        items=item_aggregations,
        total_mode=total_mode,
        total_expected=total_expected,
        total_std=total_std,
        total_posterior={k: float(total_posterior[k]) for k in range(25)},
        total_ci_90=total_ci,
        severity_bucket=severity_bucket,
        severity_bucket_probs=severity_probs,
        triggered_arbitration=len(arbitration_items) > 0,
        arbitration_items=arbitration_items,
        arbitration_reasons=arbitration_reasons,
        mentions_self_harm=any_self_harm,
        self_harm_evidence=all_evidence,
        juror_reports=reports,
        judge_resolution=None,
        prompt_version=prompt_version,
        scored_at=datetime.utcnow(),
    )
```

---

## 5. Test Specifications

### 5.1 Posterior Tests (`test_posterior.py`)

```python
import numpy as np
import pytest

def test_uniform_votes_give_uniform_posterior():
    """When votes are 1-1-1-1-1-1, posterior is ~uniform."""
    votes = [0, 1, 2, 3, 0, 1]  # 2 each for 0,1; 1 each for 2,3
    posterior = compute_item_posterior(votes, alpha=0.5)

    # With Dirichlet smoothing, should be roughly balanced
    assert all(0.1 < p < 0.4 for p in posterior)
    assert sum(posterior) == pytest.approx(1.0)

def test_unanimous_votes_give_peaked_posterior():
    """When all 6 votes agree, posterior peaks sharply."""
    votes = [2, 2, 2, 2, 2, 2]
    posterior = compute_item_posterior(votes, alpha=0.5)

    assert posterior[2] > 0.8  # Strong peak at 2
    assert sum(posterior) == pytest.approx(1.0)

def test_convolution_produces_correct_range():
    """Convolving 8 items (each 0-3) gives range 0-24."""
    # All items certain at score=1 → total should peak at 8
    item_posteriors = [np.array([0.0, 1.0, 0.0, 0.0]) for _ in range(8)]
    total = convolve_posteriors(item_posteriors)

    assert len(total) == 25
    assert np.argmax(total) == 8
    assert total[8] == pytest.approx(1.0)

def test_convolution_with_uncertainty():
    """Convolution spreads probability when items are uncertain."""
    # Each item has 50/50 between 0 and 1
    item_posteriors = [np.array([0.5, 0.5, 0.0, 0.0]) for _ in range(8)]
    total = convolve_posteriors(item_posteriors)

    # Total should be centered around 4 (8 × 0.5)
    expected_value = np.dot(total, np.arange(25))
    assert expected_value == pytest.approx(4.0)

    # But probability should be spread (not peaked)
    assert max(total) < 0.3  # No single score dominates

def test_credible_interval_covers_mode():
    """90% CI should include the mode."""
    posterior = np.zeros(25)
    posterior[10] = 0.8
    posterior[9] = 0.1
    posterior[11] = 0.1

    lower, upper = compute_credible_interval(posterior, alpha=0.10)
    assert lower <= 10 <= upper
```

### 5.2 Entropy Tests (`test_entropy.py`)

```python
def test_entropy_zero_for_certainty():
    """Entropy is 0 when one outcome has P=1."""
    posterior = np.array([0.0, 0.0, 1.0, 0.0])
    assert shannon_entropy(posterior) == 0.0

def test_entropy_max_for_uniform():
    """Entropy is maximum for uniform distribution."""
    posterior = np.array([0.25, 0.25, 0.25, 0.25])
    max_ent = max_entropy_for_k_outcomes(4)

    assert shannon_entropy(posterior) == pytest.approx(max_ent)
    assert normalized_entropy(posterior) == pytest.approx(1.0)

def test_entropy_increases_with_spread():
    """More spread distribution has higher entropy."""
    peaked = np.array([0.9, 0.05, 0.03, 0.02])
    spread = np.array([0.4, 0.3, 0.2, 0.1])

    assert shannon_entropy(peaked) < shannon_entropy(spread)
```

### 5.3 Disagreement Tests (`test_disagreement.py`)

```python
def test_no_arbitration_for_unanimous():
    """Unanimous votes don't trigger arbitration."""
    votes = [2, 2, 2, 2, 2, 2]
    posterior = compute_item_posterior(votes)

    needs_arb, reason = should_arbitrate_item(posterior, votes)
    assert needs_arb is False
    assert reason is None

def test_arbitration_for_high_range():
    """Range >= 2 triggers arbitration."""
    votes = [0, 0, 2, 2, 2, 2]  # Range = 2
    posterior = compute_item_posterior(votes)

    needs_arb, reason = should_arbitrate_item(posterior, votes)
    assert needs_arb is True
    assert "vote_range" in reason

def test_arbitration_for_low_max_prob():
    """Low max probability triggers arbitration."""
    votes = [0, 1, 2, 0, 1, 2]  # Spread votes
    posterior = compute_item_posterior(votes)

    needs_arb, reason = should_arbitrate_item(
        posterior, votes, max_prob_threshold=0.6
    )
    assert needs_arb is True
    assert "max_prob" in reason or "entropy" in reason

def test_clinical_ambiguity_triggers():
    """Borderline P(clinical) triggers arbitration."""
    # With alpha=0.5 and votes [1,1,1,2,2,2], P(>=2) is exactly 0.50.
    votes = [1, 1, 1, 2, 2, 2]
    posterior = compute_item_posterior(votes)
    clinical_prob = posterior[2] + posterior[3]

    # Should be in ambiguous range
    assert clinical_prob == pytest.approx(0.50)

    needs_arb, reason = should_arbitrate_item(posterior, votes)
    assert needs_arb is True
    assert reason is not None
    assert "clinical_ambiguity" in reason
```

### 5.4 Aggregation Integration Tests (`test_aggregate.py`)

```python
def test_aggregate_six_reports():
    """Can aggregate 6 juror reports into final result."""
    # Create 6 mock reports (no actual LLM calls)
    reports = [create_mock_report(i) for i in range(6)]

    result = aggregate_reports(
        reports=reports,
        file_id="test_file",
        condition="mdd",
        prompt_version="v1.0.0",
    )

    # Basic structure checks
    assert result.file_id == "test_file"
    assert len(result.items) == 8  # 8 PHQ-8 items
    assert 0 <= result.total_mode <= 24
    assert len(result.total_posterior) == 25
    assert sum(result.total_posterior.values()) == pytest.approx(1.0)
    assert result.severity_bucket in ["0-4", "5-9", "10-14", "15-19", "20-24"]

def test_severity_bucket_probs_sum_to_one():
    """Severity bucket probabilities should sum to 1."""
    reports = [create_mock_report(i) for i in range(6)]
    result = aggregate_reports(reports, "test", "mdd", "v1.0.0")

    total_prob = sum(result.severity_bucket_probs.values())
    assert total_prob == pytest.approx(1.0)

def test_arbitration_triggered_when_disagreement():
    """Arbitration flag set when items have high disagreement."""
    # Create reports with high disagreement on one item
    reports = [create_mock_report(i, force_disagreement="anhedonia") for i in range(6)]

    result = aggregate_reports(reports, "test", "mdd", "v1.0.0")

    assert result.triggered_arbitration is True
    assert "anhedonia" in result.arbitration_items

def test_self_harm_flag_propagates():
    """If any report flags self-harm, result flags it."""
    reports = [create_mock_report(i) for i in range(5)]
    reports.append(create_mock_report(5, self_harm=True))

    result = aggregate_reports(reports, "test", "mdd", "v1.0.0")

    assert result.mentions_self_harm is True
```

---

## 6. Test Fixtures (`fixtures/sample_votes.py`)

```python
"""Sample vote scenarios for testing aggregation logic."""

from vibe_check.schemas.scoring import PHQ8ItemScore, PHQ8Report
from datetime import datetime

def create_mock_report(
    run_index: int,
    force_disagreement: str | None = None,
    self_harm: bool = False,
) -> PHQ8Report:
    """Create a mock PHQ8Report for testing.

    Args:
        run_index: 0-5, determines model_id and run_number
        force_disagreement: Item name to give extreme score
        self_harm: Whether to flag self-harm

    No LLM calls - just structured test data.
    """
    model_ids = ["gpt-5.2", "gpt-5.2", "claude-sonnet", "claude-sonnet", "gemini-flash", "gemini-flash"]
    run_numbers = [1, 2, 1, 2, 1, 2]

    # Default scores (moderate consensus)
    base_scores = {
        "anhedonia": 2,
        "depressed_mood": 1,
        "sleep": 2,
        "fatigue": 2,
        "appetite": 1,
        "guilt": 1,
        "concentration": 2,
        "psychomotor": 1,
    }

    # Force disagreement if requested
    if force_disagreement and run_index < 3:
        base_scores[force_disagreement] = 0  # First 3 say 0
    elif force_disagreement:
        base_scores[force_disagreement] = 3  # Last 3 say 3

    def make_item(score: int) -> PHQ8ItemScore:
        return PHQ8ItemScore(
            score=score,
            confidence=0.8,
            evidence=["Test evidence"],
            insufficient_evidence=False,
        )

    return PHQ8Report(
        model_id=model_ids[run_index],
        run_number=run_numbers[run_index],
        anhedonia=make_item(base_scores["anhedonia"]),
        depressed_mood=make_item(base_scores["depressed_mood"]),
        sleep=make_item(base_scores["sleep"]),
        fatigue=make_item(base_scores["fatigue"]),
        appetite=make_item(base_scores["appetite"]),
        guilt=make_item(base_scores["guilt"]),
        concentration=make_item(base_scores["concentration"]),
        psychomotor=make_item(base_scores["psychomotor"]),
        total_score=sum(base_scores.values()),
        mentions_self_harm=self_harm,
        self_harm_evidence=["Test self-harm evidence"] if self_harm else [],
        scored_at=datetime.utcnow(),
    )


# Pre-defined vote scenarios
UNANIMOUS_VOTES = {
    "anhedonia": [2, 2, 2, 2, 2, 2],
    "depressed_mood": [1, 1, 1, 1, 1, 1],
    # ... all items unanimous
}

HIGH_DISAGREEMENT_VOTES = {
    "anhedonia": [0, 0, 0, 3, 3, 3],  # Complete split
    "depressed_mood": [1, 1, 1, 1, 1, 1],  # Unanimous
    # ...
}

CLINICAL_BORDERLINE_VOTES = {
    "anhedonia": [1, 1, 2, 2, 1, 2],  # P(>=2) ≈ 0.5
    # ...
}
```

---

## 7. Definition of Done

- [x] All schemas (`scoring.py`, `output.py`) pass type checking
- [x] `compute_item_posterior()` produces valid distributions
- [x] `convolve_posteriors()` produces 25-element total distribution
- [x] `shannon_entropy()` matches manual calculations
- [x] `should_arbitrate_item()` triggers on all documented conditions
- [x] `aggregate_reports()` produces complete `AggregatedPHQ8`
- [x] Unit test coverage >= 95% for aggregation module
- [x] All tests use synthetic data (no mocks, no LLM calls)
- [x] `make ci` passes

---

## 8. Non-Goals (Deferred)

- Weighted aggregation by model confidence (potential enhancement)
- Model-specific calibration (requires real data analysis)
- Near-duplicate vote detection (edge case)
- Async aggregation (not needed - pure computation is fast)

---

## 9. Testing Philosophy

**Property-Based Testing Opportunity**: The aggregation functions have mathematical properties:
- Posterior sums to 1.0
- Entropy is in [0, log(k)]
- Convolution output has correct length
- CI contains mode (usually)

Consider adding `hypothesis` for property-based tests in a later iteration.

**No Mocks**: All tests use `create_mock_report()` which produces real Pydantic objects, not Mock objects. We're testing that our math is correct, not that we called methods.

---

## 10. Implementation Order

1. Write schemas (`scoring.py`, `output.py`) - contracts first
2. Write `posterior.py` - core math
3. Write `entropy.py` - simple utility
4. Write `disagreement.py` - decision logic
5. Write `aggregate.py` - ties it together
6. Write `fixtures/sample_votes.py` - test data
7. Write unit tests alongside each module
8. Run coverage, add edge case tests until 95%+
