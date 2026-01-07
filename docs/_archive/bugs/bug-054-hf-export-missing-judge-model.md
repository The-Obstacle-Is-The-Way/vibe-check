# BUG-054: HuggingFace Export Missing `judge_model` Provenance

| Field | Value |
|-------|-------|
| **Severity** | P2 (Medium) |
| **Status** | resolved |
| **Date** | 2026-01-07 |
| **Component** | `run/runner.py`, `run/factory.py`, `export/huggingface.py` |
| **Impact** | Research export omits judge model ID even when arbitration occurs |

---

## Summary

The NA-aware HuggingFace export schema (SSOT §12.4 / SPEC-16) includes `scoring_metadata.judge_model` for provenance. The exporter attempted to infer this from `run_manifest.json`, but `run_manifest.json` did not record the judge model ID anywhere, so `judge_model` was always `null`.

---

## Root Cause

- `src/vibe_check/export/huggingface.py` tries to read `judge_model` from:
  - `manifest["run_config"]["judge_model"]` / `judge_model_id`, or
  - `manifest["run_config"]["judge_item"]["model_id"]`
- `src/vibe_check/run/runner.py` recorded only `judge_item.module/name/class` and omitted any model identifier.

---

## Fix

- `src/vibe_check/run/factory.py`: attach `model_id` to the live judge function (`judge_item.model_id = settings.judge_model`)
- `src/vibe_check/run/runner.py`: persist `judge_item.model_id` into `run_manifest.json` under `run_config.judge_item.model_id`
- `src/vibe_check/export/huggingface.py`: already supports `judge_item.model_id`, so provenance now flows through without schema changes.

---

## Tests Added

- `tests/integration/test_cli_export_huggingface.py`: `test_cli_export_huggingface_only` now writes a `run_manifest.json` with `judge_item.model_id` and asserts the exported record includes `scoring_metadata.judge_model`.
