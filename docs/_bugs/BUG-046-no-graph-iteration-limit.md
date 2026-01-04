# BUG-046: No Maximum Iteration Limit on LangGraph Execution

| Field | Value |
|-------|-------|
| **Severity** | P3 (Medium - Resilience Gap) |
| **Status** | open |
| **Date** | 2026-01-04 |
| **Component** | `graph/single_dialogue.py` |
| **Impact** | Potential infinite loop, resource exhaustion |

---

## Summary

The LangGraph workflow has **no maximum iteration limit**. If a node hangs or repeatedly fails, the graph could loop indefinitely via checkpoint/resume, consuming resources without termination.

---

## Current State

`graph/single_dialogue.py:169-175`:

```python
async def invoke_with_checkpoint_resume(
    app: Any,
    *,
    checkpointer: Any,
    initial_state: ScoringState,
    thread_id: str,
    graph_max_concurrency: int | None = None,
) -> ScoringState:
    config: dict[str, Any] = {"configurable": {"thread_id": thread_id}}
    if graph_max_concurrency is not None:
        config["max_concurrency"] = graph_max_concurrency
    # ← No recursion_limit or max_iterations set
    ...
```

**No guard against**:
- Infinite retry loops
- Nodes that never complete
- Checkpoint/resume cycles that never terminate

---

## Risk Scenario

1. Juror node fails with transient error
2. Tenacity retries exhaust (5 attempts)
3. Exception propagates, graph checkpoints partial state
4. Resume tries again from checkpoint
5. Same failure → same checkpoint → **infinite loop**

With `fail_fast=False`, this could run forever.

---

## Fix

### Add `recursion_limit` to LangGraph Config

```python
async def invoke_with_checkpoint_resume(
    app: Any,
    *,
    checkpointer: Any,
    initial_state: ScoringState,
    thread_id: str,
    graph_max_concurrency: int | None = None,
    max_iterations: int = 100,  # ← NEW
) -> ScoringState:
    config: dict[str, Any] = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": max_iterations,  # ← LangGraph setting
    }
    ...
```

### Add Iteration Tracking

```python
# In ScoringState TypedDict
class ScoringState(TypedDict):
    ...
    iteration_count: int  # ← Track how many times we've looped
```

### Fail Explicitly on Limit

```python
if iteration_count >= max_iterations:
    raise RuntimeError(
        f"Graph exceeded {max_iterations} iterations for {thread_id}. "
        "Possible infinite loop detected."
    )
```

---

## Why This Matters

For a **research codebase** processing hundreds of dialogues:
- One stuck dialogue shouldn't block the entire batch
- Resource exhaustion (memory, API quota) is a real risk
- Silent hangs are worse than explicit failures

---

## Test Plan

1. Add `recursion_limit` to graph config
2. Create test that forces repeated failures
3. Verify graph terminates after limit
4. Verify error message is clear

---

## Related

- [LangGraph Recursion Limit Docs](https://langchain-ai.github.io/langgraph/)
- Three-layer resilience (ADR-001) handles transient errors, but not infinite loops
