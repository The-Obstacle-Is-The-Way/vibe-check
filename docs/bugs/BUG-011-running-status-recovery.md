# BUG-011: Running Status Never Recovers After Crash

**Status**: OPEN
**Severity**: LOW
**Discovered**: 2026-01-02
**Component**: `src/vibe_check/run/runner.py`, `src/vibe_check/run/ledger.py`

---

## Summary

If a scoring process crashes mid-dialogue (e.g., SIGKILL, OOM, network timeout), items with `status='running'` are never automatically recovered on the next run.

## Current Behavior

1. Runner calls `ledger.mark_running(file_id)` before scoring
2. Process crashes before `mark_done` or `mark_failed`
3. On resume, runner checks `if ledger.get_status(file_id) == "done": continue`
4. Since status is `running` (not `done`), item is reprocessed
5. `mark_running` increments `attempts` counter again, even though this is a retry

## Issues

1. **LangGraph checkpoint may have partial state**: If graph completed some juror nodes but not all, the checkpoint contains partial jury_results. Resume may produce inconsistent results.

2. **No explicit "retry" semantics**: The attempts counter increments on every run start, not just failures. This conflates "first try" with "retry after crash".

3. **Status ambiguity**: There's no way to distinguish between:
   - Item currently being processed by another worker
   - Item that crashed and needs retry

## Impact

- Low severity because LangGraph checkpointing generally handles mid-run recovery well
- The item will still complete on retry
- But `attempts` count is misleading (shows 2 even if first run crashed)

## Reproduction

```python
ledger.initialize(["a", "b", "c"])
ledger.mark_running("b")  # Process crashes here

# On resume:
ledger.get_status("b")  # Returns "running", not "pending"
ledger.mark_running("b")  # Increments attempts to 2
```

## Fix Options

1. **Reset on initialization**: In `runner.py`, reset all `running` items to `pending` at the start of a run (after ledger.initialize)

2. **Add timeout**: In ledger, add `started_at` timestamp and auto-reset items running longer than X minutes

3. **Accept current behavior**: Document that `running` items are retried automatically (current behavior is mostly correct, just noisy)

## Recommended Fix

Option 1 - minimal change:

```python
def reset_running_items(self) -> int:
    """Reset any 'running' items to 'pending' (crash recovery)."""
    with self._connect() as conn:
        cursor = conn.execute(
            """
            UPDATE jobs SET status = 'pending', updated_at = ?
            WHERE status = 'running'
            """,
            (_utc_now_iso(),),
        )
        return cursor.rowcount
```

Call in runner.py after `ledger.initialize()`:
```python
reset_count = ledger.reset_running_items()
if reset_count:
    logger.info(f"Reset {reset_count} crashed items to pending")
```
