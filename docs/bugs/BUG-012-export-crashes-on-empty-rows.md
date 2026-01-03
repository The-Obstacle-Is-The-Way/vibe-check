# BUG-012: write_scored_jsonl Crashes When No Rows Exist

**Status**: OPEN
**Severity**: P2 (Medium - Crash on Edge Case)
**Discovered**: 2026-01-02
**Component**: `src/vibe_check/run/export.py`

---

## Summary

When all dialogues fail (or corpus is empty after initialization), `write_scored_jsonl` raises `FileNotFoundError` because the `rows/` directory doesn't exist.

## Root Cause

In `export.py:36-37`:

```python
rows_dir = output_dir / ROWS_DIR
if not rows_dir.exists():
    raise FileNotFoundError(rows_dir)
```

This assumes at least one row was successfully written. When all dialogues fail, no rows are written, `rows/` is never created, and the export crashes.

## Impact

- Runner crashes at the end even after gracefully handling all failures
- No manifest is written (crash happens before `write_run_manifest`)
- Users cannot see failure statistics or diagnose issues

## Reproduction

```python
# All jurors raise exceptions
class AlwaysFailsJuror:
    def score(self, scoring_text: str):
        raise RuntimeError("Simulated failure!")

score_corpus(jurors=[AlwaysFailsJuror()], fail_fast=False)
# Crashes with: FileNotFoundError: .../output/rows
```

## Expected Behavior

- Write empty `scored.jsonl` (or just a newline)
- Write `run_manifest.json` showing 0 completed, N failed
- Return successfully so manifest is visible

## Fix

In `export.py:write_scored_jsonl`:

```python
def write_scored_jsonl(output_dir: Path) -> None:
    """Materialize scored.jsonl from per-dialogue row files (sorted by file_id)."""
    rows_dir = output_dir / ROWS_DIR
    if not rows_dir.exists():
        # No rows written - write empty JSONL
        _atomic_write_text(output_dir / "scored.jsonl", "")
        return

    row_files = sorted(rows_dir.glob("*.json"), key=lambda p: p.stem)
    # ... rest of function
```
