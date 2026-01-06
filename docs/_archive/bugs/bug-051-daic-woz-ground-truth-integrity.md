---
severity: P1
status: resolved
opened_date: 2026-01-06
resolved_date: 2026-01-06
---

# BUG-051: DAIC-WOZ PHQ-8 Ground Truth Integrity

## Summary

Two upstream inconsistencies in DAIC-WOZ/AVEC2017 label files can silently corrupt evaluation:

- **PID 319**: A missing PHQ-8 item value (`PHQ8_Sleep`) despite an authoritative `PHQ8_Score` total.
- **PID 409**: A binary label inconsistency (`PHQ8_Score = 10` but `PHQ8_Binary = 0`) in at least one upstream source; this repo standardizes to `PHQ8_Binary = 1 iff PHQ8_Score >= 10`.

## Impact

- Incorrect ground truth for even a small number of participants can bias reported metrics (e.g., MAE, binary accuracy), and can propagate into any derived split files.
- If `full_test_split.csv` is treated as “official AVEC test labels”, it creates an **evaluation protocol mismatch** (label leakage relative to AVEC).

## Root Cause

- Upstream dataset packaging issues and inconsistencies across DAIC-WOZ/AVEC2017 distributions.
- Derived splits can inherit errors unless explicitly validated.

## Fix

- Deterministic reconstruction of a single missing item from the invariant:
  `PHQ8_Score == sum(PHQ8 item columns)`.
- Deterministic correction of `PHQ8_Binary` to match `PHQ8_Score >= 10`.
- Document `full_test_split.csv` as a **non-AVEC** file and avoid using it for model selection/tuning under an AVEC protocol.
- Add `scripts/patch_missing_phq8_values.py` to verify invariants and (optionally) apply deterministic fixes.

## Verification

- `uv run python scripts/patch_missing_phq8_values.py --dry-run` reports no proposed patches and confirms invariants.
- `PHQ8_Score == sum(items)` holds for all participants in train/dev and paper splits.
- `PHQ8_Binary == 1 iff PHQ8_Score >= 10` holds for all participants in train/dev and paper splits.

## References

- `data/daic-woz/DATA_PROVENANCE.md`
- `_reference/daic_woz_process/config_files/config_process.py` (`wrong_labels = {409: 1}`)
