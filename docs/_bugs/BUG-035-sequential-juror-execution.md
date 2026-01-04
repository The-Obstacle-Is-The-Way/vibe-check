---
severity: P2
status: open
opened_date: 2026-01-03
---

# BUG-035: Sequential Juror Execution Limits Throughput

## Summary

The 6 jurors in the LangGraph workflow are wired sequentially (each waits for the previous to complete), when they could run in parallel. This causes:

- **6x slower** single-dialogue latency for live API runs
- Underutilization of concurrent API capacity

## Evidence

In `src/vibe_check/graph/single_dialogue.py:54-63`:

```python
previous = START
for idx, juror in enumerate(jurors, start=1):
    node_name = f"juror_{idx}"
    graph.add_node(
        node_name,
        cast("Any", make_juror_node(juror)),
        input_schema=ScoringState,
    )
    graph.add_edge(previous, node_name)  # Sequential chain
    previous = node_name
```

This creates: `START → juror_1 → juror_2 → juror_3 → juror_4 → juror_5 → juror_6 → aggregate`

## Impact

- **Latency**: If each juror takes ~2s (typical LLM call), a single dialogue takes ~12s instead of ~2s
- **Throughput**: At 50 concurrent dialogues, we get 50 × 6 = 300 concurrent API calls sequentialized to 50 × 1 = 50 at a time
- **Rate limiting**: We're not utilizing our full RPM allocation efficiently

## Root Cause

The graph was designed with sequential edges, likely for simplicity or checkpointing granularity. However:

1. Each juror only needs `scoring_text` from initial state (no inter-juror dependencies)
2. LangGraph's `operator.add` reducer on `jury_results` supports concurrent appends
3. Rate limiting is per-provider, so parallel calls to different providers are safe

## Proposed Fix

Use parallel juror execution in the graph:

```python
# Instead of sequential edges, fan-out from START to all jurors
for idx, juror in enumerate(jurors, start=1):
    node_name = f"juror_{idx}"
    graph.add_node(node_name, make_juror_node(juror), input_schema=ScoringState)
    graph.add_edge(START, node_name)  # Parallel from START
    graph.add_edge(node_name, "aggregate")  # All fan-in to aggregate

# LangGraph will run all jurors concurrently, aggregate waits for all
```

## Considerations

1. **Checkpointing**: With parallel nodes, checkpoint resume might restart all jurors if any failed (vs. resuming from last successful sequential node). Need to test LangGraph behavior.

2. **Rate limiting**: With 6 parallel calls across 3 providers (2 per provider), we might hit rate limits faster. The existing `aiolimiter` per-provider limiters should handle this.

3. **Error handling**: If one juror fails, what happens to others in flight? LangGraph's error handling needs review.

## Verification

- [ ] Benchmark single-dialogue latency: sequential vs parallel
- [ ] Verify checkpoint resume works correctly with parallel nodes
- [ ] Confirm rate limiters throttle correctly under parallel load
