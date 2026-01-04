# LangGraph Workflow

vibe-check uses LangGraph to orchestrate the single-dialogue scoring workflow. This provides state management, checkpointing, and conditional routing.

---

## Graph Structure

```
┌─────────────────────────────────────────────────────────────┐
│            SINGLE-DIALOGUE LANGGRAPH WORKFLOW               │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  START                                                      │
│    │                                                        │
│    ▼                                                        │
│  ┌────────────┐                                             │
│  │ juror_1    │──▶ PHQ8Report → jury_results               │
│  └────────────┘                                             │
│    │                                                        │
│    ▼                                                        │
│  ┌────────────┐                                             │
│  │ juror_2    │──▶ PHQ8Report → jury_results               │
│  └────────────┘                                             │
│    │                                                        │
│    ▼                                                        │
│  ┌────────────┐                                             │
│  │ juror_3    │──▶ PHQ8Report → jury_results               │
│  └────────────┘                                             │
│    │                                                        │
│    ▼                                                        │
│  ┌────────────┐                                             │
│  │ juror_4    │──▶ PHQ8Report → jury_results               │
│  └────────────┘                                             │
│    │                                                        │
│    ▼                                                        │
│  ┌────────────┐                                             │
│  │ juror_5    │──▶ PHQ8Report → jury_results               │
│  └────────────┘                                             │
│    │                                                        │
│    ▼                                                        │
│  ┌────────────┐                                             │
│  │ juror_6    │──▶ PHQ8Report → jury_results               │
│  └────────────┘                                             │
│    │                                                        │
│    ▼                                                        │
│  ┌────────────┐                                             │
│  │ aggregate  │──▶ AggregatedPHQ8 + needs_arbitration       │
│  └────────────┘                                             │
│    │                                                        │
│    ▼                                                        │
│  ┌────────────────────┐                                     │
│  │ Conditional Edge   │                                     │
│  │ needs_arbitration? │                                     │
│  └─────────┬──────────┘                                     │
│            │                                                │
│      ┌─────┴─────┐                                          │
│      ▼           ▼                                          │
│    FALSE       TRUE                                         │
│      │           │                                          │
│      │     ┌─────▼─────┐                                    │
│      │     │ arbitrate │──▶ Updated AggregatedPHQ8          │
│      │     └─────┬─────┘                                    │
│      │           │                                          │
│      └─────┬─────┘                                          │
│            ▼                                                │
│          END                                                │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## State Schema

The workflow uses a TypedDict state that flows through all nodes:

```python
class ScoringState(TypedDict):
    # Identity
    file_id: str
    condition: Literal["mdd", "control"]
    prompt_version: str

    # Data
    dialogue: str
    scoring_text: str  # The specific view used for scoring

    # Accumulated (grows as jurors complete)
    jury_results: Annotated[list[PHQ8Report], operator.add]

    # Control flow
    needs_arbitration: bool

    # Output (set by aggregate, possibly updated by arbitrate)
    final_output: AggregatedPHQ8 | None
```

### Key Detail: `operator.add`

The `jury_results` field uses `Annotated[list, operator.add]` which means each juror node **appends** its result rather than replacing the list. This enables accumulating results across all 6 juror nodes.

---

## Nodes

### Juror Nodes (juror_1 through juror_6)

Each juror node:
1. Reads `scoring_text` from state
2. Calls `juror.ascore(scoring_text)`
3. Returns `{"jury_results": [report]}`

```python
def make_juror_node(juror: Juror):
    async def node(state: ScoringState) -> dict:
        report = await juror.ascore(state["scoring_text"])
        return {"jury_results": [report]}
    return node
```

### Aggregate Node

After all jurors complete:
1. Calls `aggregate_reports()` with all juror reports (default: 6)
2. Computes posteriors, entropy, arbitration triggers
3. Returns `AggregatedPHQ8` and `needs_arbitration` flag

```python
def aggregate_node(state: ScoringState) -> dict:
    agg = aggregate_reports(
        state["jury_results"],
        file_id=state["file_id"],
        condition=state["condition"],
        ...
    )
    return {
        "final_output": agg,
        "needs_arbitration": agg.triggered_arbitration
    }
```

### Arbitrate Node (Conditional)

Only runs if `needs_arbitration` is True:
1. Identifies contested items
2. Calls `judge_item()` for each
3. Updates `final_item_scores` with judge decisions
4. Returns updated `AggregatedPHQ8` with `final_source="judge_override"`

```python
def arbitrate_node(state: ScoringState) -> dict:
    agg = state["final_output"]
    if agg is None:
        raise RuntimeError("aggregate node did not produce final_output")

    contested = [item for item in agg.arbitration_items if item in PHQ8_ITEMS]
    if "__total__" in agg.arbitration_items:
        contested = list(PHQ8_ITEMS)

    if not contested:
        return {"final_output": agg, "needs_arbitration": False}

    resolutions = {}
    for item in contested:
        resolutions[item] = judge_item(
            state["scoring_text"],
            item,
            agg.juror_reports,
            state["prompt_version"],
        )

    # Aggregate judge token usage across all contested items
    t_input = 0
    t_output = 0
    t_reasoning = 0
    t_total = 0
    for resolution in resolutions.values():
        if resolution.usage:
            t_input += resolution.usage.input_tokens or 0
            t_output += resolution.usage.output_tokens or 0
            t_reasoning += resolution.usage.reasoning_tokens or 0
            t_total += resolution.usage.total_tokens or 0
    judge_usage = (
        TokenUsage(
            input_tokens=t_input,
            output_tokens=t_output,
            reasoning_tokens=t_reasoning,
            total_tokens=t_total,
        )
        if (t_input or t_output or t_reasoning or t_total)
        else None
    )

    # Update final scores with judge decisions
    final_item_scores = dict(agg.final_item_scores)
    for item, resolution in resolutions.items():
        final_item_scores[item] = int(resolution.final_score)
    final_total_score = sum(final_item_scores.values())

    updated = agg.model_copy(
        update={
            "final_item_scores": final_item_scores,
            "final_total_score": final_total_score,
            "final_severity_bucket": get_severity_bucket(final_total_score),
            "final_source": "judge_override",
            "judge_resolution": {k: v.model_dump() for k, v in resolutions.items()},
            "judge_usage": judge_usage,
        }
    )
    return {"final_output": updated, "needs_arbitration": False}
```

---

## Conditional Routing

```python
def route_after_aggregate(state: ScoringState) -> str:
    return "arbitrate" if state["needs_arbitration"] else END
```

This function determines whether to:
- Route to `arbitrate` node if arbitration is needed
- Route to `END` if jury consensus is sufficient

---

## Checkpointing

LangGraph saves state after each node to SQLite, enabling:

### Resume From Failure

```python
async with open_async_sqlite_saver(checkpoint_path) as saver:
    app = graph.compile(checkpointer=saver)

    # Check if we have a checkpoint
    has_checkpoint = await saver.aget_tuple(config) is not None

    # If checkpoint exists, resume; otherwise start fresh
    input_state = None if has_checkpoint else initial_state
    result = await app.ainvoke(input_state, config=config)
```

### Thread ID

Each dialogue uses its `file_id` as the thread ID:

```python
config = {"configurable": {"thread_id": file_id}, "max_concurrency": max_concurrency}
```

This ensures:
- Each dialogue has its own checkpoint namespace
- Resuming uses the correct saved state
- Parallel dialogues don't interfere

---

## Building the Graph

```python
graph = build_single_dialogue_graph(
    jurors=jurors,                           # 3×RUNS_PER_MODEL jurors (default: 6)
    judge_item=judge_item,                   # Judge function
    dirichlet_alpha=0.5,                     # Bayesian smoothing
    arbitration_total_std_threshold=2.0,     # Total score variance trigger
    arbitration_max_prob_threshold=0.60,     # Item probability trigger
    arbitration_entropy_threshold=1.2,       # Item entropy trigger
)
```

---

## Entry Points

### Async API

```python
result = await score_one_dialogue_async(
    file_id="active436",
    corpus_dir="data/sqpsychconv/qwen-2.5",
    prompt_version="v1.0",
    checkpoint_db="sqlite:///checkpoints.db",
    jurors=jurors,
    judge_item=judge_item,
    dialogue_view="client_qa",
)
```

### Sync API

```python
result = score_one_dialogue(
    file_id="active436",
    corpus_dir="data/sqpsychconv/qwen-2.5",
    prompt_version="v1.0",
    checkpoint_db="sqlite:///checkpoints.db",
    jurors=jurors,
    judge_item=judge_item,
)
```

---

## Code Reference

| File | Component | Purpose |
|------|-----------|---------|
| `graph/single_dialogue.py` | `build_single_dialogue_graph()` | Graph construction |
| `graph/single_dialogue.py` | `invoke_with_checkpoint_resume()` | Checkpoint-aware invocation |
| `graph/single_dialogue.py` | `score_one_dialogue_async()` | Single-dialogue entry point |
| `graph/state.py` | `ScoringState` | State TypedDict |
| `sqlite.py` | `open_async_sqlite_saver()` | Async checkpointer |

---

## Related Documentation

- [System Overview](system-overview.md) - High-level pipeline
- [Data Flow](data-flow.md) - Schema transformations
- [Scoring: Jury Consensus](../scoring/jury-consensus.md) - How jurors work
- [Scoring: Arbitration](../scoring/arbitration.md) - When judge is invoked
