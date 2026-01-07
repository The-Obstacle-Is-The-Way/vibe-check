# BUG-053: SPEC-08 Export Crashes on NA Juror Votes

| Field | Value |
|-------|-------|
| **Severity** | P1 (High) |
| **Status** | resolved |
| **Date** | 2026-01-07 |
| **Component** | `export/writer.py` |
| **Impact** | `vibe-check export --format jsonl,csv` can crash on NA-aware runs |

---

## Summary

SPEC-08 export is an **int-only** public contract. After introducing NA-aware juror reports (`score=None` for `assertion="not_mentioned"`), the SPEC-08 writer attempted to build `juror_votes` via `int(score)` and crashed when `score=None`.

---

## Root Cause

- `src/vibe_check/export/writer.py` constructed `juror_votes` with:
  - `int(getattr(r, item).score)` which raises `TypeError` when `score is None`.

---

## Fix

- `src/vibe_check/export/writer.py`: impute `None → 0` when materializing per-juror votes:
  - `int(getattr(r, item).score or 0)`

Note: This is consistent with SSOT §12.5: SPEC-08 outputs are **legacy/imputed** and cannot represent a distinct NA state.

---

## Tests Added

- `tests/integration/test_cli_export_huggingface.py`: `test_cli_export_all_formats` now includes an NA item to ensure SPEC-08 export is NA-safe.
