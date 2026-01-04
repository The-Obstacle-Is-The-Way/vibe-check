# BUG-046: No Maximum Iteration Limit on LangGraph Execution

| Field | Value |
|-------|-------|
| **Severity** | P3 (Medium - Resilience Gap) |
| **Status** | resolved |
| **Date** | 2026-01-04 |
| **Component** | `graph/single_dialogue.py` |
| **Impact** | Potential infinite loop, resource exhaustion |

---

## Summary

The LangGraph workflow does not set an explicit `recursion_limit` in its runnable config. While LangGraph 1.0.5 has a **default recursion limit (25)**, leaving this implicit makes behavior:

- Dependent on library defaults / env var overrides (`LANGGRAPH_DEFAULT_RECURSION_LIMIT`)
- Harder to audit/reproduce from run manifests

This is primarily a **defense-in-depth** and **reproducibility** gap (not a confirmed infinite-loop bug in the current acyclic graph).

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
    # ← recursion_limit is not set explicitly (LangGraph default is used)
    ...
```

**What this means today**:
- The graph uses LangGraph's default recursion limit (25 steps) unless overridden externally.
- The current single-dialogue graph is acyclic, so unbounded looping is unlikely.
- A true “hang forever” risk is more about request timeouts than iteration count.

---

## Risk Scenario

A more realistic failure mode is a **stuck dialogue** due to a hanging model call (no request timeout) or repeated external failures across manual resumes. This won’t necessarily spin in an internal loop, but it can still waste time/cost and complicate batch runs.

---

## Fix

### Add explicit `recursion_limit` to LangGraph config (Recommended)

```python
async def invoke_with_checkpoint_resume(
    app: Any,
    *,
    checkpointer: Any,
    initial_state: ScoringState,
    thread_id: str,
    graph_max_concurrency: int | None = None,
    recursion_limit: int = 25,  # ← NEW (explicit; match LangGraph default)
) -> ScoringState:
    config: dict[str, Any] = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": recursion_limit,
    }
    ...
```

### Complementary: ensure request timeouts exist

If model calls can hang, set explicit request timeouts via PydanticAI `ModelSettings(timeout=...)` so a single dialogue can’t stall indefinitely.

---

## Why This Matters

For a **research codebase** processing hundreds of dialogues:
- One stuck dialogue shouldn't block the entire batch
- Resource exhaustion (memory, API quota) is a real risk
- Silent hangs are worse than explicit failures

---

## Test Plan

1. Add `recursion_limit` to graph config and expose it via run config/settings
2. Add a unit test that asserts the config passed to `ainvoke()` includes `recursion_limit`

---

## Related

- [LangGraph Recursion Limit Docs](https://langchain-ai.github.io/langgraph/)
- Three-layer resilience (ADR-001) handles transient errors, but not infinite loops

---

## Resolution (Implemented)

Added an explicit `graph_recursion_limit` setting in `src/vibe_check/settings.py`, carried it through `RunConfig`, and passed it into LangGraph execution via `src/vibe_check/graph/single_dialogue.py` so iteration bounds are explicit and recorded in the run manifest.
