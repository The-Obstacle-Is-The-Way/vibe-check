# BUG-010: Token Usage Not Persisted on Resume

**Status**: OPEN
**Severity**: MEDIUM
**Discovered**: 2026-01-02
**Component**: `src/vibe_check/run/runner.py`

---

## Summary

When a scoring run is resumed, the `token_totals` in the run manifest only reflect tokens used in the **current session**, not the cumulative total across all sessions.

## Root Cause

In `runner.py:62-70`, `token_totals` is initialized to zero at the start of every run:

```python
token_totals: dict[str, int] = {
    "input_tokens": 0,
    "output_tokens": 0,
    "reasoning_tokens": 0,
    "total_tokens": 0,
}
```

When resuming, dialogues with `status == "done"` are skipped (line 82-83), but their token usage is never counted.

## Impact

- Run manifest under-reports cumulative token usage
- Users cannot accurately track API costs across resumed runs
- SPEC-06 Section 3.2 explicitly requires: "Token Usage Totals: Must account for *all* items in the corpus, even if the run was resumed"

## Reproduction

```python
# Run 1: Score 5 dialogues → tokens = 50,000
# Run 2 (resume): Score 5 more → tokens = 50,000 (WRONG - should be 100,000)
```

## Fix Options

Per SPEC-06, two acceptable approaches:

1. **Re-scan existing rows** (simpler): At initialization, scan `output_dir/rows/*.json` and sum up token usage from `juror_reports[*].usage`

2. **Persist in ledger** (more complex): Store cumulative token totals in the ledger SQLite database

## Recommended Fix

Option 1 - add a helper function in `export.py`:

```python
def scan_existing_token_usage(output_dir: Path) -> dict[str, int]:
    """Reconstruct token totals from existing row files."""
    totals = {"input_tokens": 0, "output_tokens": 0, "reasoning_tokens": 0, "total_tokens": 0}
    rows_dir = output_dir / ROWS_DIR
    if not rows_dir.exists():
        return totals
    for row_file in rows_dir.glob("*.json"):
        row = json.loads(row_file.read_text())
        for jr in row.get("juror_reports", []):
            usage = jr.get("usage") or {}
            for key in totals:
                totals[key] += usage.get(key) or 0
    return totals
```

Then in `runner.py`:

```python
token_totals = scan_existing_token_usage(output_dir)
```
