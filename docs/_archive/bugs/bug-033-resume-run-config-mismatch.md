---
severity: P3
status: resolved
opened_date: 2026-01-03
resolved_date: 2026-01-03
---

# BUG-033: Resume can silently mix runs (no run-config hash / ledger reuse footgun)

## Summary
The batch runner is designed to resume safely using `ledger.sqlite` and the LangGraph checkpoint DB, but it does not record or validate a “run configuration” (input dataset identity, prompt version, dialogue view, model IDs). Reusing an existing `--output` directory (or checkpoint DB) for a different run can silently mix artifacts and produce misleading `run_manifest.json` counts.

## Evidence
- `src/vibe_check/run/runner.py`
  - Always uses `JobLedger(output_dir / "ledger.sqlite")`
  - `ledger.initialize([...])` uses `INSERT OR IGNORE` (stale jobs remain in DB)
  - Manifest `completed`/`failed` counts are computed from `ledger.list_all()` (all jobs ever seen in that output dir), not just the current corpus slice
  - `compute_arbitration_rate_from_rows(output_dir)` scans all `rows/*.json` present (including stale rows)
- `src/vibe_check/graph/single_dialogue.py`
  - Resume path passes `input_state=None` when a checkpoint exists, so updated `prompt_version` / `scoring_text` will not overwrite the persisted state

## Impact
- Reproducibility risk: a run directory can contain outputs produced with different prompt versions or dialogue views.
- Diagnostics and exports can be computed over a mixed set without an explicit error.
- Hard to audit runs after the fact (manifest counts can be wrong for the current invocation).

## Fix Plan
Resolved by:
- Storing a run configuration fingerprint in `ledger.sqlite`.
- Writing `run_fingerprint` and `run_config` into `run_manifest.json`.
- Failing fast on config mismatch unless `--force` is provided, in which case the runner resets run artifacts and the checkpoint DB.
- Adding integration coverage for mismatch refusal.
