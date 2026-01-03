---
severity: P3
status: partially_fixed
acknowledged_date: 2026-01-02
---

# BUG-008: Magic numbers, hardcoded defaults, and DRY violations

## Summary
Multiple files contain "magic numbers" (thresholds, defaults) and repeated constants that should be centralized in `settings.py` or a shared constants file. This violates DRY and makes configuration opaque.

## Evidence
1. **Magic Numbers**:
   - `src/vibe_check/aggregation/aggregate.py`: `dirichlet_alpha=0.5` default.
   - `src/vibe_check/aggregation/aggregate.py`: `juror_total_std >= 2.0` threshold hardcoded.
   - `src/vibe_check/run/runner.py`: `max_concurrency=1` default.
   - `src/vibe_check/scoring/parsing.py`: Evidence limits (3 snippets) hardcoded in logic.

2. **DRY Violations**:
   - `PHQ8_ITEMS`: Defined as a tuple in `scoring/parsing.py` and a list in `aggregation/aggregate.py`.
   - `SEVERITY_BUCKETS`: Defined in `aggregation/aggregate.py` but bucket selection logic is duplicated in `graph/single_dialogue.py` (`_bucket_for_total`).

## Impact
- **Inconsistent behavior**: Changing PHQ-8 items in one place breaks the other.
- **Hidden config**: Tuning arbitration thresholds requires code changes, not config changes.
- **Maintenance risk**: Hardcoded values scatter policies across the codebase.

## Fix Plan
1. Centralize `PHQ8_ITEMS` and `SEVERITY_BUCKETS` in `src/vibe_check/schemas/scoring.py` or a new `src/vibe_check/constants.py`.
2. Move all scoring thresholds (alpha, std dev limit) to `Settings` (BUG-007).
3. Update consumers to import from the single source of truth.

## Partial Resolution (2026-01-02)

**Fixed**:
- Added `dirichlet_alpha`, `disagreement_range_threshold`, `arbitration_total_std_threshold` to `Settings` (BUG-007 fix).

**Remaining**:
- `PHQ8_ITEMS` defined in both `scoring/parsing.py` and `aggregation/aggregate.py`
- `SEVERITY_BUCKETS` logic duplicated in `graph/single_dialogue.py`
- These are P3 and can be addressed in a future cleanup pass.
