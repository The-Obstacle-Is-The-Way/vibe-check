---
severity: P4
status: open
opened_date: 2026-01-03
---

# BUG-039: `max_concurrency` Parameter Misleading for Intra-Dialogue Parallelism

## Summary

The `max_concurrency` parameter is passed to the LangGraph config but has no effect on juror parallelism within a single dialogue. Jurors run sequentially regardless of this setting.

This is related to BUG-035 (sequential juror execution) but is a separate documentation/API issue.

## Evidence

In `src/vibe_check/graph/single_dialogue.py:160-163`:

```python
config: dict[str, Any] = {
    "configurable": {"thread_id": thread_id},
    "max_concurrency": max_concurrency,
}
```

The `max_concurrency` is passed to the LangGraph invoke config, but:

1. LangGraph's `max_concurrency` controls parallel execution of nodes that **can run in parallel**
2. The graph has sequential edges: `juror_1 → juror_2 → ...`
3. Sequential nodes cannot run in parallel regardless of `max_concurrency`

## Impact

- **Confusion**: Users might expect `--max-concurrency 50` to parallelize jurors within a dialogue
- **Misleading docs**: If `max_concurrency` implies parallelism, but jurors are sequential, users get less performance than expected

## Root Cause

The parameter exists but the graph structure prevents it from having any effect on juror parallelism.

## Relationship to BUG-035

- **BUG-035**: Root cause (sequential edges in graph)
- **BUG-039**: Symptom (misleading parameter)

Fixing BUG-035 would make `max_concurrency` meaningful for jurors.

## Proposed Fix

### Option 1: Fix the Graph (addresses both bugs)

Make jurors parallel (BUG-035 fix), then `max_concurrency` becomes meaningful.

### Option 2: Clarify Documentation

Update CLI help and docs to clarify:

```python
score.add_argument(
    "--max-concurrency",
    type=int,
    default=None,
    help=(
        "Max concurrent DIALOGUES to process simultaneously. "
        "Does not affect juror parallelism within a dialogue (jurors run sequentially)."
    ),
)
```

### Option 3: Remove the Confusing Parameter

If `max_concurrency` only controls inter-dialogue parallelism (via the runner's asyncio workers), remove it from the graph config to reduce confusion.

## Verification

- [ ] Clarify documentation on what `max_concurrency` affects
- [ ] Consider renaming to `max_concurrent_dialogues` for clarity
