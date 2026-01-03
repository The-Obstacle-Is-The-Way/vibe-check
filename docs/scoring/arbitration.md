# Arbitration

Arbitration is the process by which contested items are escalated to a "judge" LLM for resolution. The judge reviews the evidence and renders a final decision.

---

## When Is Arbitration Triggered?

Arbitration is triggered when any of these conditions is met for an item:

| Trigger | Threshold | Meaning |
|---------|-----------|---------|
| **Low max probability** | `max_prob < 0.60` | No score has strong consensus |
| **High entropy** | `entropy > 1.2` | Votes are spread across scores |
| **Clinical ambiguity** | `P(score ≥ 2) ∈ [0.4, 0.6]` | Uncertain if clinically significant |
| **Wide vote range** | `max - min ≥ 2` | Jurors disagree by 2+ points |
| **Insufficient evidence** | `count ≥ 2` | 2+ jurors flagged no evidence |

If **any** trigger fires, the item is flagged for arbitration.

---

## Arbitration Flow

```
┌────────────────────────────────────────────────────────────────┐
│                     ARBITRATION PROCESS                        │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  AggregatedPHQ8 (after jury aggregation)                       │
│         │                                                      │
│         ▼                                                      │
│  ┌──────────────────┐                                          │
│  │ Check each item  │                                          │
│  │ for triggers     │                                          │
│  └────────┬─────────┘                                          │
│           │                                                    │
│     Any triggers?                                              │
│           │                                                    │
│     ┌─────┴─────┐                                              │
│     ▼           ▼                                              │
│    NO          YES                                             │
│     │           │                                              │
│     │     ┌─────▼─────────────────────────────────────┐        │
│     │     │ For each contested item:                  │        │
│     │     │                                           │        │
│     │     │  1. Collect all juror votes               │        │
│     │     │  2. Collect all juror evidence            │        │
│     │     │  3. Build judge prompt                    │        │
│     │     │  4. Call judge LLM                        │        │
│     │     │  5. Receive JudgeItemResolution           │        │
│     │     │  6. Override final_item_scores[item]      │        │
│     │     └───────────────────────────────────────────┘        │
│     │           │                                              │
│     └─────┬─────┘                                              │
│           ▼                                                    │
│  Return updated AggregatedPHQ8                                 │
│  - final_source = "jury_mode" or "judge_override"              │
│  - judge_resolution populated (if arbitrated)                  │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

---

## The Judge's Role

The judge is a specialized LLM agent (default: Claude Opus) that:

1. **Reviews the evidence**: Sees all juror votes and their supporting evidence
2. **Considers the dialogue**: Has access to the full scoring text
3. **Renders a decision**: Returns a single final score with confidence and rationale

### Judge Output

```python
class JudgeItemResolution:
    item: str           # e.g., "anhedonia"
    final_score: int    # 0, 1, 2, or 3
    confidence: float   # 0.0 to 1.0
    rationale: str      # Why this score was chosen
```

---

## Why Not Always Use the Judge?

The judge is more expensive and slower than jurors:

| Factor | Jurors | Judge |
|--------|--------|-------|
| Model | Mixed (GPT, Claude, Gemini) | Claude Opus (most capable) |
| Cost | ~$0.05/dialogue | ~$0.50/item |
| Purpose | Fast parallel scoring | Careful deliberation |

Using the judge for every item would be:
- 10x more expensive
- Much slower (sequential vs. parallel)
- Unnecessary when jurors agree

The arbitration threshold (~30% of items) balances quality and cost.

---

## Arbitration Reasons

When arbitration is triggered, the reason is recorded:

```python
arbitration_reasons = {
    "anhedonia": "low_max_prob=0.52; high_entropy=1.35",
    "sleep": "vote_range=2",
}
```

This provides transparency into why the judge was invoked.

---

## Final Score Sources

The `final_source` field indicates how the final score was determined:

| Source | Meaning |
|--------|---------|
| `jury_mode` | Jury consensus (mode of posterior) |
| `judge_override` | Judge resolved at least one contested item |

---

## Total Score Arbitration

Besides per-item triggers, the **total score** can trigger arbitration:

```python
juror_totals = [r.total_score for r in juror_reports]
juror_total_std = std(juror_totals)

if juror_total_std >= arbitration_total_std_threshold:  # default: 2.0
    # Flag "__total__" for arbitration
    # Judge reviews all items
```

If jurors' total scores differ by more than 2 points (std), the judge reviews all items.

---

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `arbitration_max_prob_threshold` | `0.60` | Min probability for consensus |
| `arbitration_entropy_threshold` | `1.2` | Max entropy before arbitration |
| `arbitration_total_std_threshold` | `2.0` | Max juror total std |
| `judge_model` | `claude-opus-4-5-20251101` | Model for judge |

---

## Code Reference

| File | Function | Purpose |
|------|----------|---------|
| `aggregation/disagreement.py` | `should_arbitrate_item()` | Trigger logic |
| `aggregation/aggregate.py` | `aggregate_reports()` | Orchestrates aggregation + arbitration detection |
| `judge/agent.py` | `build_judge_agent()` | Creates judge agent |
| `run/factory.py` | `build_real_judge_item()` | Wires up judge with resilience |

---

## Related Concepts

- [Bayesian Aggregation](bayesian-aggregation.md) - How posteriors and entropy are computed
- [Jury Consensus](jury-consensus.md) - What happens before arbitration
