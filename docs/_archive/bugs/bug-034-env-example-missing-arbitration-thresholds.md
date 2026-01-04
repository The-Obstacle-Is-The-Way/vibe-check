---
severity: P4
status: resolved
opened_date: 2026-01-03
resolved_date: 2026-01-03
---

# BUG-034: `.env.example` missing `ARBITRATION_MAX_PROB_THRESHOLD` / `ARBITRATION_ENTROPY_THRESHOLD`

## Summary
`Settings` defines two arbitration threshold settings that affect scoring behavior, but `.env.example` does not include them. This makes local configuration incomplete and increases the chance teams run with unintended defaults.

## Evidence
- `src/vibe_check/settings.py`
  - `arbitration_max_prob_threshold: float = 0.60`
  - `arbitration_entropy_threshold: float = 1.2`
- `.env.example`
  - Includes `ARBITRATION_TOTAL_STD_THRESHOLD` and `DIRICHLET_ALPHA`
  - Missing `ARBITRATION_MAX_PROB_THRESHOLD` and `ARBITRATION_ENTROPY_THRESHOLD`

## Impact
- Harder to tune arbitration sensitivity without reading source code.
- Encourages “mystery defaults” in experiments.

## Fix Plan
Resolved by adding the missing keys to `.env.example` and adding a unit test to prevent drift.
