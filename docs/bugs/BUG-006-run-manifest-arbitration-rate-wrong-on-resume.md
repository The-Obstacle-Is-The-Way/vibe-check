# BUG-006: `run_manifest.json` arbitration rate is wrong after resume

**Severity**: P2 (incorrect diagnostics; does not block scoring)
**Status**: RESOLVED
**Date**: 2026-01-03

---

## Summary

`score_corpus()` currently computes `arbitration_rate` using a counter that only increments when a dialogue is scored in the **current** process execution. If a run is resumed and most items are already marked `done` in the ledger, those items are skipped and never counted toward arbitration statistics.

Result: `run_manifest.json` is inconsistent across resumes and under-reports arbitration.

---

## Affected Areas

- `src/vibe_check/run/runner.py`
- `src/vibe_check/run/export.py` (potential scan source)

---

## Repro

1. Run `score_corpus(..., limit=5)` to completion.
2. Run the same command again (resume).
3. Compare `run_manifest.json` arbitration rate between runs.

Expected: arbitration rate is stable and reflects all completed rows.
Actual: arbitration rate can drop to `0.0` (or otherwise change) on resume.

---

## Root Cause

`arbitration_count` is calculated only for dialogues that are executed in the current invocation. Skipped `done` dialogues are excluded.

---

## Fix Plan

Compute arbitration stats from persisted outputs:

- After writing `rows/{file_id}.json` (or `scored.jsonl`), compute `arbitration_count` by scanning all completed row files and counting `triggered_arbitration == true`.
- Define `arbitration_rate` as `arbitration_count / completed_count` (not total corpus size), where `completed_count` comes from the ledger.

---

## Verification

- Add/extend an integration test that runs the batch runner twice and asserts:
  - `completed` unchanged on resume
  - `arbitration_rate` unchanged on resume
