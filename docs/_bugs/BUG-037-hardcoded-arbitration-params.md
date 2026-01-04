---
severity: P4
status: open
opened_date: 2026-01-03
---

# BUG-037: Arbitration Parameters Hardcoded in disagreement.py

## Summary

Two arbitration trigger parameters are hardcoded as function defaults and not exposed in `Settings`:

1. `clinical_ambiguity_band: tuple[float, float] = (0.4, 0.6)`
2. `insufficient_evidence_threshold: int = 2`

Users cannot tune these without modifying source code.

## Evidence

In `src/vibe_check/aggregation/disagreement.py:15-26`:

```python
def should_arbitrate_item(
    posterior: np.ndarray,
    votes: Sequence[int],
    *,
    max_prob_threshold: float = 0.60,          # Exposed in Settings ✓
    entropy_threshold: float = 1.2,             # Exposed in Settings ✓
    clinical_ambiguity_band: tuple[float, float] = (0.4, 0.6),  # Hardcoded ✗
    range_threshold: int = 2,                   # Exposed in Settings ✓
    insufficient_evidence_count: int = 0,
    insufficient_evidence_threshold: int = 2,    # Hardcoded ✗
) -> tuple[bool, str | None]:
```

Compare to `src/vibe_check/settings.py`:

```python
# These are exposed:
disagreement_range_threshold: int = 2
arbitration_total_std_threshold: float = 2.0
arbitration_max_prob_threshold: float = 0.60
arbitration_entropy_threshold: float = 1.2

# These are NOT:
# clinical_ambiguity_band
# insufficient_evidence_threshold
```

## Impact

- **clinical_ambiguity_band**: When P(score >= 2) falls in [0.4, 0.6], arbitration triggers. Users can't adjust this range for different clinical thresholds.

- **insufficient_evidence_threshold**: When 2+ jurors flag `insufficient_evidence=true`, arbitration triggers. With 6 jurors, 2 is 33%. Users can't adjust this ratio.

## Root Cause

Initial implementation exposed some thresholds but not all. These two were overlooked.

## Proposed Fix

### Option 1: Expose in Settings (Recommended)

Add to `src/vibe_check/settings.py`:

```python
clinical_ambiguity_band_low: float = 0.4
clinical_ambiguity_band_high: float = 0.6
insufficient_evidence_threshold: int = 2
```

Thread through `aggregate.py` → `disagreement.py`.

### Option 2: Keep Hardcoded with Documentation

Document the hardcoded values clearly in `concepts/arbitration.md` and explain why they're not configurable (e.g., clinical validity requires fixed thresholds).

## Verification

- [ ] Add settings if Option 1
- [ ] Update `.env.example` with new keys
- [ ] Add integration test with custom thresholds
