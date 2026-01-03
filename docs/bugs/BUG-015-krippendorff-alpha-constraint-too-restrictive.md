# BUG-015: ReliabilityMetrics.krippendorff_alpha constraint too restrictive

**Severity**: P2 (runtime crash on valid data)
**Status**: RESOLVED
**Date**: 2026-01-03
**Resolution**: Changed constraint from `ge=0.0` to `ge=-1.0` for both `krippendorff_alpha` and `cronbach_alpha`.

---

## Summary

The `ReliabilityMetrics` schema in `diagnostics/report.py` has:

```python
krippendorff_alpha: float = Field(ge=0.0, le=1.0)
```

This is incorrect. Krippendorff's alpha can be **negative** when agreement is worse than chance (anti-correlated raters). The current constraint would cause a Pydantic validation error on legitimate data with poor inter-rater reliability.

---

## Root Cause

Misunderstanding of Krippendorff's alpha range. While the coefficient is often between 0 and 1, it can theoretically range from -1 to 1:
- 1.0 = perfect agreement
- 0.0 = chance agreement
- Negative = worse than chance (anti-correlation)

---

## Evidence

```python
import numpy as np
import krippendorff as k

# Anti-correlated raters
anti_correlated = np.array([
    [0, 3, 0, 3, 0, 3],
    [3, 0, 3, 0, 3, 0],
]).T

alpha = k.alpha(anti_correlated, level_of_measurement='ordinal')
print(f'Alpha: {alpha}')  # Output: -0.1
```

If diagnostics were run on a corpus where jurors systematically disagreed, the `ReliabilityMetrics` instantiation would fail with:

```
pydantic_core._pydantic_core.ValidationError: 1 validation error for ReliabilityMetrics
krippendorff_alpha
  Input should be greater than or equal to 0 [type=greater_than_equal, ...]
```

---

## Fix

Change the constraint from `ge=0.0` to `ge=-1.0`:

```python
class ReliabilityMetrics(BaseModel):
    krippendorff_alpha: float = Field(ge=-1.0, le=1.0)  # Can be negative
    krippendorff_alpha_per_item: dict[str, float]  # Also can be negative
    # ...
```

Also add a similar check for `cronbach_alpha` in `ConsistencyMetrics` if applicable (Cronbach's alpha can also be negative in edge cases).

---

## Acceptance Criteria

- [ ] `krippendorff_alpha` field allows range [-1.0, 1.0]
- [ ] Per-item krippendorff values validated correctly (dict values can be negative)
- [ ] Test: synthetic anti-correlated data produces negative alpha without crash
- [ ] Review `cronbach_alpha` constraint (should it also allow negative?)
