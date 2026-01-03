---
severity: P3
status: fixed (schemas)
---

# BUG-003: Token usage (incl. reasoning tokens) not captured in schemas

## Summary

The SSOT cost model explicitly warns that some models (e.g., GPT-5.2 Thinking) can incur significant hidden reasoning-token costs, but the current schemas/outputs do not capture per-call token usage. This makes it impossible to validate or control the cost envelope during batch runs.

## Evidence

- Hidden-token warning and cost assumptions: `docs/research/spec-vibe-check.md:60`
- SPEC-04/06 now require usage tracking (spec-level), but code schemas do not yet include it.

## Impact

- Blind spots in cost monitoring and budgeting.
- Harder to compare providers/models and detect runaway costs early.

## Fix Plan

- Add a `TokenUsage` schema and include it (optional) in:
  - `PHQ8Report` (per juror call)
  - Run manifest aggregation (sum by provider/model; include reasoning tokens when available)
- Ensure tests remain deterministic (usage can be omitted or fixture-set).

## Resolution

- Implemented `TokenUsage` and `PHQ8Report.usage` in `src/vibe_check/schemas/scoring.py:14`.
- Runtime capture/aggregation will be implemented in SPEC-04/06 (populate `usage` from provider responses and summarize in the run manifest).
