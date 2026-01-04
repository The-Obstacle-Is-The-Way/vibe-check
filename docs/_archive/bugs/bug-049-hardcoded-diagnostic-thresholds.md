# BUG-049: Hardcoded Diagnostic Thresholds

| Field | Value |
|-------|-------|
| **Severity** | P3 (Medium - Configuration Gap) |
| **Status** | resolved |
| **Date** | 2026-01-04 |
| **Component** | `diagnostics/runner.py`, `diagnostics/separation.py`, `diagnostics/report.py` |
| **Impact** | Cannot tune quality gates without code changes |

---

## Summary

The SPEC-07 diagnostic thresholds (Krippendorff α, Cronbach α, arbitration rate, Cohen's d, p-value) are **duplicated as hardcoded literals across multiple files** (logic + report rendering).

This prevents:
- Changing thresholds in one place without missing another (DRY violation)
- Reliably auditing “what gates were applied” without reading code

Note: `docs/reference/thresholds.md` documents these as **not user-configurable** today; this bug is about centralization and drift-prevention, not necessarily exposing knobs.

---

## Hardcoded Values Found

### `diagnostics/runner.py:105-108`

```python
passes_reliability = reliability.krippendorff_alpha >= 0.67
passes_consistency = consistency.cronbach_alpha >= 0.70
passes_arbitration = arbitration.overall_rate < 0.30
```

### `diagnostics/separation.py:55`

```python
is_valid = (mdd_mean > control_mean) and (float(p_value) < 0.01) and (cohens_d >= 0.5)
```

### `diagnostics/report.py:99-117`

```python
f"- Reliability (Krippendorff alpha >= 0.67): "
f"- Consistency (Cronbach alpha >= 0.70): "
f"- Separation (MDD > control, p<0.01, d>=0.5): "
f"- Arbitration (rate < 0.30): "
```

---

## Full List of Hardcoded Thresholds

| Threshold | Value | Location |
|-----------|-------|----------|
| Krippendorff α minimum | 0.67 | `runner.py:105`, `report.py:99` |
| Cronbach α minimum | 0.70 | `runner.py:106`, `report.py:104` |
| Arbitration rate maximum | 0.30 | `runner.py:108`, `report.py:117` |
| Cohen's d minimum | 0.5 | `separation.py:55`, `report.py:109` |
| p-value maximum | 0.01 | `separation.py:55`, `report.py:109` |

**Note**: The same values appear in multiple places, violating DRY.

---

## Fix

### Put thresholds in `constants.py` (Recommended)

Even if thresholds remain non-configurable, they should be single-sourced in code.

```python
# SPEC-07 Quality Gate Thresholds (research-defined, not configurable)
KRIPPENDORFF_ALPHA_MIN = 0.67
CRONBACH_ALPHA_MIN = 0.70
ARBITRATION_RATE_MAX = 0.30
COHENS_D_MIN = 0.5
P_VALUE_MAX = 0.01
```

### Update Diagnostic Code

```python
from vibe_check.constants import (
    KRIPPENDORFF_ALPHA_MIN,
    CRONBACH_ALPHA_MIN,
    ARBITRATION_RATE_MAX,
    COHENS_D_MIN,
    P_VALUE_MAX,
)

passes_reliability = reliability.krippendorff_alpha >= KRIPPENDORFF_ALPHA_MIN
passes_consistency = consistency.cronbach_alpha >= CRONBACH_ALPHA_MIN
passes_arbitration = arbitration.overall_rate < ARBITRATION_RATE_MAX
```

---

## Recommendation

**Keep in `constants.py`** (not settings), because:

1. These are **research-defined standards**, not operational tuning
2. Changing them mid-study would invalidate comparisons
3. They should be consistent across all runs

But **document them prominently** so users know what gates exist.

---

## Test Plan

1. Extract constants to `constants.py`
2. Update all diagnostic code to use constants
3. Verify no hardcoded values remain (grep)
4. Add constants to manifest for audit trail

---

## Related

- [SPEC-07: Run Diagnostics](../specs/spec-07-run-diagnostics.md)
- Quality gate definitions in master spec

---

## Resolution (Implemented)

Extracted SPEC-07 quality gate thresholds into `src/vibe_check/constants.py` and updated `src/vibe_check/diagnostics/{runner,report,separation}.py` to reference the shared constants instead of duplicating literals.
