# SPEC-10: Parallel Juror Execution

**Status**: IMPLEMENTED
**Priority**: P1 (Performance Critical)
**Author**: First-principles analysis + 2025 best practices research
**Created**: 2026-01-04

---

## Executive Summary

Switch juror execution from **sequential** to **parallel** within each dialogue. This provides **3-4x batch throughput improvement** with no correctness impact—the codebase is already designed for parallel execution (state reducer, rate limiters, sorting).

---

## Problem Statement

### Current Behavior (Sequential)

```
START → juror_1 → juror_2 → juror_3 → juror_4 → juror_5 → juror_6 → aggregate
```

- **Single dialogue latency**: 12-15 seconds (6 × ~2s per API call)
- **Batch (50 dialogues)**: ~12.5 minutes
- **API utilization**: Underutilizes rate limits (e.g., Anthropic allows 60 RPM, sequential uses ~5)

### Proposed Behavior (Parallel)

```
         ┌─ juror_1 ─┐
         ├─ juror_2 ─┤
START ───┼─ juror_3 ─┼─── aggregate ─── [arbitrate?] ─── END
         ├─ juror_4 ─┤
         ├─ juror_5 ─┤
         └─ juror_6 ─┘
```

- **Single dialogue latency**: 2-3 seconds (all jurors in parallel, rate limiter serializes Anthropic pair)
- **Batch (50 dialogues)**: ~3-4 minutes
- **API utilization**: Fully utilizes rate limits per provider

---

## Why This Is Safe (Race Condition Analysis)

### 1. State Reducer Is Designed for Concurrency

From `src/vibe_check/graph/state.py:26`:
```python
jury_results: Annotated[list[PHQ8Report], operator.add]
```

`operator.add` performs **list concatenation**, which is:
- Order-independent (any arrival order produces same final list)
- Atomic per-superstep in LangGraph (all parallel nodes complete before next step)

### 2. Aggregation Is Order-Independent

From `src/vibe_check/graph/single_dialogue.py:68`:
```python
reports = sorted(state["jury_results"], key=lambda r: (r.model_id, r.run_number))
```

Results are **sorted before processing**—arrival order doesn't matter.

### 3. Rate Limiters Are Async-Safe

From research on [aiolimiter](https://github.com/mjpieters/aiolimiter):
- Uses leaky bucket algorithm
- Thread-safe for concurrent awaits
- Multiple coroutines can safely share one limiter

Current architecture already shares limiters per-provider:
- 2 OpenAI jurors → share `AsyncLimiter(100, 60.0)`
- 2 Anthropic jurors → share `AsyncLimiter(60, 60.0)`
- 2 Google jurors → share `AsyncLimiter(100, 60.0)`

### 4. LangGraph Superstep Semantics

From [LangGraph documentation](https://docs.langchain.com/oss/python/langgraph/use-graph-api):
> "If any of these branches raises an exception, none of the updates are applied to the state (the entire superstep errors)."

This means:
- All 6 jurors execute in ONE superstep
- If any juror fails, the entire superstep fails atomically
- On resume, all 6 jurors re-execute (not individually checkpointed)
- This is **correct behavior**—no partial state corruption

---

## Implementation

### File: `src/vibe_check/graph/single_dialogue.py`

**Current** (lines 56-65):
```python
previous = START
for idx, juror in enumerate(jurors, start=1):
    node_name = f"juror_{idx}"
    graph.add_node(node_name, make_juror_node(juror), input_schema=ScoringState)
    graph.add_edge(previous, node_name)  # Sequential chain
    previous = node_name

# ... later:
graph.add_edge(previous, "aggregate")
```

**Proposed**:
```python
juror_node_names: list[str] = []
for idx, juror in enumerate(jurors, start=1):
    node_name = f"juror_{idx}"
    graph.add_node(node_name, make_juror_node(juror), input_schema=ScoringState)
    graph.add_edge(START, node_name)       # Fan-out: all from START
    juror_node_names.append(node_name)

# All jurors fan-in to aggregate
for node_name in juror_node_names:
    graph.add_edge(node_name, "aggregate")
```

### File: `src/vibe_check/cli.py`

Update help text (line 60-66):
```python
help=(
    "Max concurrent dialogues to process (jurors run in parallel within each dialogue; "
    "defaults to Settings.max_concurrent_dialogues)."
),
```

### File: `docs/architecture/langgraph-workflow.md`

Update workflow diagram to reflect parallel fan-out/fan-in pattern.

---

## API Load Analysis

### With 50 Concurrent Dialogues

| Metric | Sequential | Parallel |
|--------|------------|----------|
| Peak concurrent API calls | 50 | 300 |
| OpenAI calls/min | ~50 | ~100 (at limit) |
| Anthropic calls/min | ~50 | ~60 (at limit) |
| Google calls/min | ~50 | ~100 (at limit) |
| Single dialogue latency | 12-15s | 2-3s |
| Batch completion | ~12.5 min | ~3-4 min |

### Rate Limiter Behavior

With parallel execution, Anthropic's 60 RPM limit becomes the bottleneck:
- 50 dialogues × 2 Anthropic jurors = 100 requests
- Limiter queues requests and releases 1/second
- Net effect: Anthropic jurors serialize (~2s wait), others complete in parallel

This is **correct**—the rate limiter is doing its job.

---

## Checkpoint/Resume Tradeoff

| Aspect | Sequential | Parallel |
|--------|------------|----------|
| Checkpoint granularity | Per-juror | Per-superstep (all 6 jurors) |
| On juror_3 failure | Resume from juror_3 | Resume all 6 jurors |
| Wasted API calls on failure | 0 | Up to 5 |
| Latency | Slow | Fast |

**Decision**: Accept atomic superstep behavior. The latency improvement (6x) outweighs the rare case of wasted API calls on failure. Rate limiting + retries make failures rare anyway.

---

## Testing Requirements

### Unit Tests

1. **Parallel timing**: Verify all 6 jurors execute concurrently (mock with delays, assert total time < 2 × single juror time)

2. **Result ordering**: Verify `aggregate_reports` receives all 6 reports regardless of completion order

3. **Rate limiter integration**: Verify Anthropic limiter serializes its 2 jurors while others run in parallel

### Integration Tests

1. **Checkpoint resume**: Verify entire superstep re-executes on failure (not individual jurors)

2. **Batch throughput**: Measure wall-clock time for 50 dialogues, verify ~3-4x improvement

---

## Research Sources

### LangGraph Best Practices (2025)

- [LangGraph Performance Optimization](https://sumanmichael.github.io/langgraph-cheatsheet/cheatsheet/performance-optimization/)
- [Parallel Nodes in LangGraph](https://medium.com/@gmurro/parallel-nodes-in-langgraph-managing-concurrent-branches-with-the-deferred-execution-d7e94d03ef78)
- [Scaling LangGraph Agents](https://aipractitioner.substack.com/p/scaling-langgraph-agents-parallelization)
- [LangGraph Forum: Best Practices for Fanouts](https://forum.langchain.com/t/best-practices-for-parallel-nodes-fanouts/1900)

Key findings:
> "With sequential execution, if ArXiv takes 2 seconds and Wikipedia takes 2 seconds, the total wait time is 4 seconds. With parallel execution, both APIs are called simultaneously. The total wait time becomes only 2 seconds."

> "Running both tools sequentially took 61.46s, compared to just 0.45s when executed in parallel, a 137× speedup!"

### Python Asyncio Rate Limiting (2025)

- [Avoiding Race Conditions in Python 2025](https://medium.com/pythoneers/avoiding-race-conditions-in-python-in-2025-best-practices-for-async-and-threads-4e006579a622)
- [aiolimiter Documentation](https://github.com/mjpieters/aiolimiter)
- [Concurrent OpenAI API Calls with Rate Limiting](https://villoro.com/blog/async-openai-calls-rate-limiter/)

Key findings:
> "aiolimiter implements the Leaky bucket algorithm, giving you precise control over the rate a code section can be entered."

> "Semaphores help you be a good citizen of the internet by respecting external service limits, prevent resource exhaustion, and make your applications more predictable."

---

## Acceptance Criteria

- [x] Jurors execute in parallel (fan-out from START, fan-in to aggregate)
- [x] State reducer (`operator.add`) correctly merges concurrent results
- [x] Rate limiters correctly throttle per-provider
- [x] Aggregate node sorts results before processing (order-independent)
- [x] CLI help text updated to reflect parallel execution
- [x] Tests verify parallel execution
- [x] No race conditions (verified by analysis above)

---

## Related Issues

- **BUG-035**: Sequential Juror Execution Limits Throughput → RESOLVED by this spec
- **ADR-001**: Rate Limiting and Retries → Unchanged (per-provider limiters still apply)

---

## Appendix: Why Sequential Was Originally Used

The original implementation likely used sequential execution for simplicity:
```python
previous = START
for idx, juror in enumerate(jurors, start=1):
    graph.add_edge(previous, node_name)
    previous = node_name
```

This is the simplest graph wiring pattern—just chain nodes. However, the state reducer (`operator.add`) and sorting in aggregate were always designed to handle any order, making parallel execution a drop-in improvement.
