---
severity: P3
status: open
opened_date: 2026-01-03
---

# BUG-032: Token usage totals omit judge calls (manifest undercounts arbitration cost)

## Summary
The batch runner aggregates token usage into `ledger.sqlite` and `run_manifest.json`, but it only sums usage from `AggregatedPHQ8.juror_reports`. Judge arbitration calls are not tracked (no `usage` field on judge outputs, and the real judge implementation discards `result.usage()`), so runs with arbitration will undercount total tokens/cost.

## Evidence
- `src/vibe_check/run/runner.py`
  - Aggregates per-dialogue tokens by summing `report.usage` across `result.juror_reports`
  - Writes manifest key `token_usage_totals` from the ledger
- `src/vibe_check/graph/single_dialogue.py`
  - Calls `judge_item(...)` when arbitration triggers
  - Stores `judge_resolution`, but no usage metadata
- `src/vibe_check/run/factory.py`
  - `build_real_judge_item(...)` calls `agent.run_sync(prompt)` and returns structured output, but does not capture `result.usage()`

## Impact
- Cost monitoring is systematically low when arbitration triggers (exactly when extra calls happen).
- “Hidden reasoning tokens” visibility is incomplete for the judge model.

## Fix Plan
- Capture judge usage and persist it:
  - Extend judge return type to include `TokenUsage` (either inside the resolution model or alongside it)
  - Store judge usage in `AggregatedPHQ8` (e.g., `judge_usage`) and/or ledger aggregation
- Add a unit test using PydanticAI `TestModel` (or a fake) to ensure judge usage is captured and included in manifest totals.
