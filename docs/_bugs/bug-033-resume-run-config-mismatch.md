---
severity: P3
status: open
opened_date: 2026-01-03
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
- Persist a run config fingerprint (hash) and validate on start:
  - Include: input path + dataset hash (or dataset_dict.json digest), prompt_version, dialogue_view, model IDs, runs_per_model, arbitration thresholds
  - Store in `run_manifest.json` and in `ledger.sqlite` (single-row table)
- On resume, refuse to run when the fingerprint differs unless an explicit `--force` is provided.
- Add a test that reuses an output dir with different config and asserts the runner fails fast with a clear error.
