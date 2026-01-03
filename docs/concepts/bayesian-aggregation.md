# Bayesian Aggregation

Bayesian aggregation transforms raw juror votes into probability distributions, quantifying both the consensus score and the uncertainty around it.

---

## Why Bayesian?

Simple voting (e.g., majority rule) loses information:

| Approach | Problem |
|----------|---------|
| **Majority vote** | Ignores margin of victory |
| **Mean** | Sensitive to outliers |
| **Median** | Loses distribution shape |

Bayesian aggregation preserves the **full distribution** of possible scores, enabling:
- Uncertainty quantification
- Arbitration triggering
- Clinical probability estimation

---

## Dirichlet Posterior

For each PHQ-8 item (0-3 scale), we compute a **Dirichlet-smoothed posterior**.

### Formula

Given votes `[v₁, v₂, ..., vₙ]` and smoothing parameter `α`:

```
counts[k] = number of votes for score k
posterior[k] = (counts[k] + α) / (n + 4α)
```

Where `k ∈ {0, 1, 2, 3}` and `n` is the total number of votes.

### Example

```python
votes = [1, 2, 1, 2, 1, 2]  # 6 jurors voted
alpha = 0.5                  # Jeffreys prior

# Count votes per score
counts = [0, 3, 3, 0]  # 0 zeros, 3 ones, 3 twos, 0 threes

# Compute posterior
posterior = [
    (0 + 0.5) / (6 + 2.0),  # P(score=0) = 0.0625
    (3 + 0.5) / (6 + 2.0),  # P(score=1) = 0.4375
    (3 + 0.5) / (6 + 2.0),  # P(score=2) = 0.4375
    (0 + 0.5) / (6 + 2.0),  # P(score=3) = 0.0625
]
```

### Smoothing Parameter (α)

| Value | Name | Effect |
|-------|------|--------|
| 0.0 | Maximum likelihood | No smoothing; zero counts stay zero |
| 0.5 | Jeffreys prior | **Default**; mild smoothing |
| 1.0 | Uniform prior | Strong smoothing toward uniform |

The default `α = 0.5` prevents zero probabilities while minimally distorting the observed distribution.

---

## Posterior Convolution

To get the **total score distribution** (0-24 scale), we convolve all 8 item posteriors.

### How It Works

```
┌────────────────────────────────────────────────────────────────┐
│                    POSTERIOR CONVOLUTION                       │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  Item 1 posterior: [p₀, p₁, p₂, p₃]  (4 values, sum=1)         │
│  Item 2 posterior: [p₀, p₁, p₂, p₃]  (4 values, sum=1)         │
│  ...                                                           │
│  Item 8 posterior: [p₀, p₁, p₂, p₃]  (4 values, sum=1)         │
│                                                                │
│         ↓ Convolve all 8                                       │
│                                                                │
│  Total posterior: [p₀, p₁, ..., p₂₄]  (25 values, sum=1)       │
│                                                                │
│  Each p_k = P(total_score = k)                                 │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

Convolution combines independent distributions:
- First, convolve items 1 and 2 → distribution over 0-6
- Then convolve result with item 3 → distribution over 0-9
- Continue until all 8 items → distribution over 0-24

---

## Uncertainty Metrics

### Shannon Entropy

Measures "spread" of the distribution in nats:

```python
H = -Σ p[k] * log(p[k])  for p[k] > 0
```

| Entropy | Interpretation |
|---------|----------------|
| 0.0 | Perfect certainty (one score has 100% probability) |
| ~0.7 | Moderate uncertainty |
| 1.39 | Maximum for 4-outcome item (uniform distribution) |

### Credible Interval

The 90% credible interval `[lower, upper]` contains 90% of the posterior mass.

For total score:
```python
ci_90 = (8, 16)  # 90% confident total is between 8 and 16
```

---

## Derived Statistics

From the posterior, we compute:

| Statistic | Formula | Purpose |
|-----------|---------|---------|
| **Mode** | `argmax(posterior)` | Most likely score |
| **Expected** | `Σ k * posterior[k]` | Mean of distribution |
| **Std** | `sqrt(Var(posterior))` | Spread measure |
| **Clinical Prob** | `posterior[2] + posterior[3]` | P(item ≥ 2), clinically significant |

---

## Severity Bucket Probabilities

The total posterior maps to severity buckets:

| Bucket | Score Range | Severity |
|--------|-------------|----------|
| 0-4 | 0-4 | Minimal |
| 5-9 | 5-9 | Mild |
| 10-14 | 10-14 | Moderate |
| 15-19 | 15-19 | Moderately Severe |
| 20-24 | 20-24 | Severe |

```python
severity_bucket_probs = {
    "0-4": sum(posterior[0:5]),
    "5-9": sum(posterior[5:10]),
    "10-14": sum(posterior[10:15]),
    "15-19": sum(posterior[15:20]),
    "20-24": sum(posterior[20:25]),
}
```

---

## Code Reference

The aggregation math lives in:

| File | Function | Purpose |
|------|----------|---------|
| `aggregation/posterior.py` | `compute_item_posterior()` | Dirichlet posterior per item |
| `aggregation/posterior.py` | `convolve_posteriors()` | Total score distribution |
| `aggregation/posterior.py` | `compute_credible_interval()` | CI calculation |
| `aggregation/entropy.py` | `shannon_entropy()` | Entropy in nats |
| `aggregation/aggregate.py` | `aggregate_reports()` | Orchestrates full aggregation |

---

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `dirichlet_alpha` | `0.5` | Smoothing parameter for posteriors |

---

## Related Concepts

- [Jury Consensus](jury-consensus.md) - How votes are collected
- [Arbitration](arbitration.md) - How entropy triggers judge intervention
