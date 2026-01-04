# BUG-045: Synchronous Judge Function in Async Graph

| Field | Value |
|-------|-------|
| **Severity** | P4 (Low - Architectural Friction) |
| **Status** | open |
| **Date** | 2026-01-04 |
| **Component** | `run/factory.py`, `graph/single_dialogue.py` |
| **Impact** | Performance (minor), code consistency |

---

## Summary

The judge function (`judge_item`) is **synchronous** while jurors are **asynchronous**. This creates architectural inconsistency and forces sync-to-async context switching inside the LangGraph workflow.

---

## Current State

### Jurors: Async

`scoring/juror.py`:
```python
async def ascore(self, scoring_text: str) -> PHQ8Report:
    """Async scoring method."""
    ...
```

### Judge: Sync

`run/factory.py:179-221`:
```python
def judge_fn(
    scoring_text: str,
    item: str,
    juror_reports: list[PHQ8Report],
    prompt_version: str,
) -> JudgeItemReport:
    """Synchronous judge function."""
    ...
```

### Comment Explains Why

`run/factory.py:147-150`:
```python
# Note (design choice): judge_item is synchronous because:
# 1. It's called infrequently (only on arbitration)
# 2. Wrapping sync in async adds complexity
# 3. The retry decorator works fine synchronously
```

---

## Why This Matters

1. **Inconsistency**: Jurors are async, judge is sync - mixed paradigms
2. **Context switching**: When graph calls sync judge from async context, there's overhead
3. **Future-proofing**: If judge needs parallel item resolution, sync blocks it

---

## Fix

### Option A: Make Judge Async (Recommended)

```python
async def judge_fn(
    scoring_text: str,
    item: str,
    juror_reports: list[PHQ8Report],
    prompt_version: str,
) -> JudgeItemReport:
    """Async judge function."""
    async with rate_limiter:
        result = await agent.run(user_prompt, ...)
    ...
```

Update `JudgeItemFn` type:
```python
JudgeItemFn = Callable[[str, str, list[PHQ8Report], str], Awaitable[JudgeItemReport]]
```

### Option B: Document as Intentional

If the sync design is truly intentional for simplicity, add explicit documentation:

```python
# ADR: Judge is intentionally synchronous
# - Called ~5% of dialogues (only on arbitration)
# - Simplifies retry logic (tenacity works better with sync)
# - Overhead is negligible for single-item resolution
```

---

## Impact Assessment

**Low priority** because:
- Judge is called infrequently (only when arbitration triggers)
- Current implementation works correctly
- Performance impact is minimal

**Consider fixing** if:
- Arbitration rate increases significantly
- Parallel item judging becomes desirable
- Code consistency is prioritized

---

## Test Plan

1. Convert `judge_fn` to async
2. Update graph `arbitrate_node` to await judge calls
3. Verify arbitration still works correctly
4. Benchmark to confirm no regression
