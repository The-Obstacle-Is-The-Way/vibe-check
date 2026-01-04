# BUG-047: Bare `pass` Statement in Runner

| Field | Value |
|-------|-------|
| **Severity** | P5 (Trivial - Code Smell) |
| **Status** | resolved |
| **Date** | 2026-01-04 |
| **Component** | `run/runner.py` |
| **Impact** | Code clarity, maintainability |

---

## Summary

There's a bare `pass` statement with a comment admitting "We don't have a logger here yet." This is sloppy and should either log properly or be removed.

---

## Current State

`run/runner.py:221-224`:

```python
reset_count = ledger.reset_running_items()
if reset_count > 0:
    # We don't have a logger here yet, but it's fine.
    # Could print or just rely on the fact it's handled.
    pass
```

**Problems**:
1. Comment admits a gap exists
2. `pass` does nothing - why have the `if` at all?
3. If reset_count matters, it should be logged or returned

---

## Fix

### Option A: Add Logging (Recommended)

```python
import logging

logger = logging.getLogger(__name__)

...

reset_count = ledger.reset_running_items()
if reset_count > 0:
    logger.info("Reset %d running items from previous interrupted run", reset_count)
```

### Option B: Remove the Dead Code

If the information truly doesn't matter:

```python
ledger.reset_running_items()  # Reset any items stuck in "running" state
```

No `if`, no `pass`, no comment about missing logger.

### Option C: Return the Count

If callers might care:

```python
reset_count = ledger.reset_running_items()
# Return or include in manifest for audit
manifest["reset_from_previous_run"] = reset_count
```

---

## Recommendation

**Option A** - Add logging. The reset count is operationally relevant:
- Tells user their previous run was interrupted
- Helps debug "why did this dialogue get re-scored?"
- Takes 2 lines to fix

---

## Test Plan

1. Add logger to `runner.py`
2. Replace `pass` with `logger.info()`
3. Verify log message appears when resuming interrupted run

---

## Resolution (Implemented)

Removed the `if reset_count > 0: ... pass` block and always call `ledger.reset_running_items()` directly.
