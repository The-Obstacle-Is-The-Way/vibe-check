---
severity: P2
status: open
opened_date: 2026-01-03
---

# BUG-031: `DISAGREEMENT_RANGE_THRESHOLD` is exposed but unused (hardcoded range threshold)

## Summary
`Settings.disagreement_range_threshold` is exposed via `.env.example` as `DISAGREEMENT_RANGE_THRESHOLD`, but it is not referenced anywhere in the scoring/aggregation pipeline. The arbitration logic uses the default `range_threshold=2` in `should_arbitrate_item(...)`, regardless of the configured setting.

## Evidence
- `src/vibe_check/settings.py`
  - Defines `disagreement_range_threshold: int = 2`
- `.env.example`
  - Documents `DISAGREEMENT_RANGE_THRESHOLD=2`
- `src/vibe_check/aggregation/disagreement.py`
  - `should_arbitrate_item(..., range_threshold: int = 2, ...)`
- `src/vibe_check/aggregation/aggregate.py`
  - Calls `should_arbitrate_item(...)` without passing `range_threshold`
- `rg -n disagreement_range_threshold src/vibe_check` returns only `settings.py`

## Impact
- Users think they can tune arbitration behavior, but the knob is a no-op.
- This is a “silent fallback” style failure: configuration is accepted but ignored.

## Fix Plan
- Thread the value through (single SSOT path):
  - CLI → runner → graph → `aggregate_reports(...)` → `aggregate_votes(...)` → `should_arbitrate_item(range_threshold=...)`
- Or remove the setting + `.env.example` entry entirely if range threshold must be fixed.
- Add a unit test that changes the setting and asserts arbitration behavior changes accordingly.
