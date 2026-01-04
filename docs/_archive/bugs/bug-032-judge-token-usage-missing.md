---
severity: P3
status: resolved
opened_date: 2026-01-03
resolved_date: 2026-01-03
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
Resolved by:
- Introducing `JudgeItemReport` (resolution + `usage`) for arbitration results.
- Adding `AggregatedPHQ8.judge_usage` to persist per-dialogue judge token usage.
- Including judge usage in ledger/manifest token totals.
- Adding integration coverage to assert totals include judge calls.
