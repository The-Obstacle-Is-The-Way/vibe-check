# Agents

This section documents the LLM agents used in vibe-check: jurors for scoring and a judge for arbitration.

---

## Overview

vibe-check uses PydanticAI agents with structured outputs:

| Agent | Purpose | Model | Count |
|-------|---------|-------|-------|
| **Juror** | Score PHQ-8 items independently | Mixed (GPT, Claude, Gemini) | 6 |
| **Judge** | Resolve contested items | Claude Opus | 1 |

---

## Agent Documentation

| Document | Description |
|----------|-------------|
| [Juror](juror.md) | Independent PHQ-8 scoring agents |
| [Judge](judge.md) | Arbitration agent for contested items |

---

## Why Multiple Agents?

### Diversity

Different models have different strengths:

- **GPT**: Strong reasoning and instruction following
- **Claude**: Clinical nuance and safety awareness
- **Gemini**: Cross-validation perspective

### Redundancy

Multiple runs of the same model:

- Captures stochastic variance
- Detects model instability
- Increases vote sample size

### Consensus

Aggregating multiple opinions:

- Reduces individual model bias
- Quantifies uncertainty via disagreement
- Enables principled arbitration

---

## Agent Protocols

The factory module defines protocols that both real and fake agents implement:

**File**: `run/factory.py`

### Juror Protocol

```python
class Juror(Protocol):
    """Protocol for PHQ-8 scoring agents."""

    def score(self, scoring_text: str) -> PHQ8Report:
        """Synchronous scoring (for simple use cases)."""
        ...

    async def ascore(self, scoring_text: str) -> PHQ8Report:
        """Async scoring with full resilience (for production)."""
        ...
```

Both `JurorScorer` (real) and `DeterministicFakeJuror` (fake) implement this protocol.

### JudgeItemFn Protocol

```python
class JudgeItemFn(Protocol):
    """Protocol for judge arbitration functions."""

    def __call__(
        self,
        scoring_text: str,
        item: str,
        juror_reports: list[PHQ8Report],
        prompt_version: str,
    ) -> JudgeItemResolution:
        """Resolve a single contested item."""
        ...
```

Both `build_real_judge_item()` and `deterministic_fake_judge_item()` return callables matching this protocol.

---

## Shared Constants

Agents share constants defined in `constants.py`:

**File**: `constants.py`

### PHQ-8 Items

```python
PHQ8_ITEMS: tuple[str, ...] = (
    "anhedonia",
    "depressed_mood",
    "sleep",
    "fatigue",
    "appetite",
    "guilt",
    "concentration",
    "psychomotor",
)
```

### Evidence Limits

| Constant | Value | Purpose |
|----------|-------|---------|
| `MAX_EVIDENCE_SNIPPET_WORDS` | 50 | Max words per evidence quote |
| `MAX_EVIDENCE_SNIPPET_CHARS` | 400 | Max chars per evidence quote |
| `MAX_JUDGE_EVIDENCE_SNIPPETS` | 10 | Max evidence shown to judge |

These limits are enforced by Pydantic validators in `schemas/scoring.py`.

### Severity Buckets

```python
SeverityBucket = Literal["0-4", "5-9", "10-14", "15-19", "20-24"]

SEVERITY_BUCKETS: dict[SeverityBucket, tuple[int, int]] = {
    "0-4": (0, 4),      # Minimal
    "5-9": (5, 9),      # Mild
    "10-14": (10, 14),  # Moderate
    "15-19": (15, 19),  # Moderately severe
    "20-24": (20, 24),  # Severe
}
```

---

## Real vs Fake Agents

### Real Agents

Use live LLM APIs with ADR-001 resilience (jurors: 3 layers; judge: 2 layers):

```python
from vibe_check.run.factory import build_real_jury, build_real_judge_item

jurors = build_real_jury(settings)  # 6 JurorScorer instances
judge = build_real_judge_item(settings)  # Closure with Agent
```

Resilience layers:

- **Jurors**: Layer 1 (PydanticAI) + Layer 2 (Tenacity) + Layer 3 (Aiolimiter)
- **Judge**: Layer 1 (PydanticAI) + Layer 2 (Tenacity); no Layer 3 rate limiting

### Fake Agents

Deterministic fakes for testing/dry-runs:

```python
from vibe_check.run.factory import build_fake_jury, build_fake_judge_item

jurors = build_fake_jury()  # 6 DeterministicFakeJuror instances
judge = build_fake_judge_item()  # deterministic_fake_judge_item function
```

**How Fake Jurors Work:**

```python
# Hash-based scoring for reproducibility
seed = f"{model_id}|{run_number}|{item}|{scoring_text}"
score = int(hashlib.sha256(seed.encode()).hexdigest(), 16) % 4  # Always 0-3
```

**How Fake Judge Works:**

```python
# Mean of juror votes, rounded
votes = [getattr(report, item).score for report in juror_reports]
final = max(0, min(3, round(sum(votes) / len(votes))))
```

---

## LangGraph Integration

Agents are wired into a LangGraph StateGraph workflow:

**File**: `graph/single_dialogue.py`

### ScoringState

```python
class ScoringState(TypedDict):
    """State for a single-dialogue scoring workflow."""

    # Identity
    file_id: str
    condition: Literal["mdd", "control"]
    prompt_version: str

    # Data
    dialogue: str
    scoring_text: str  # The specific view (e.g., client_qa)

    # Accumulated results (operator.add allows parallel append)
    jury_results: Annotated[list[PHQ8Report], operator.add]

    # Control flow
    needs_arbitration: bool

    # Final output
    final_output: AggregatedPHQ8 | None
```

### Workflow Structure

```
┌─────────────────────────────────────────────────────────────┐
│                  SINGLE-DIALOGUE WORKFLOW                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  START                                                      │
│    │                                                        │
│    ▼                                                        │
│  ┌────────────┐    Each juror node calls:                   │
│  │ juror_1    │    report = await juror.ascore(scoring_text)│
│  └────────────┘    return {"jury_results": [report]}        │
│    │                                                        │
│    ▼                                                        │
│  ┌────────────┐                                             │
│  │ juror_2    │    (Sequential for deterministic results)   │
│  └────────────┘                                             │
│    │                                                        │
│    ▼                                                        │
│   ...  (juror_3 through juror_6)                            │
│    │                                                        │
│    ▼                                                        │
│  ┌────────────┐    Bayesian aggregation of all votes        │
│  │ aggregate  │    Sets needs_arbitration flag              │
│  └────────────┘                                             │
│    │                                                        │
│    ▼                                                        │
│  ┌─────────────────┐                                        │
│  │needs_arbitration?│                                       │
│  └────────┬────────┘                                        │
│           │                                                 │
│     ┌─────┴─────┐                                           │
│     ▼           ▼                                           │
│   FALSE       TRUE                                          │
│     │           │                                           │
│     │     ┌─────▼─────┐   For each contested item:          │
│     │     │ arbitrate │   resolution = judge_item(...)      │
│     │     └─────┬─────┘   Update final_item_scores          │
│     │           │                                           │
│     └─────┬─────┘                                           │
│           ▼                                                 │
│         END                                                 │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Building the Graph

```python
from vibe_check.graph.single_dialogue import build_single_dialogue_graph

graph = build_single_dialogue_graph(
    jurors=jurors,              # Sequence[Juror]
    judge_item=judge_item,      # JudgeItemFn
    dirichlet_alpha=0.5,
    arbitration_total_std_threshold=2.0,
    arbitration_max_prob_threshold=0.60,
    arbitration_entropy_threshold=1.2,
)

# Compile with checkpointer for resume capability
app = graph.compile(checkpointer=saver)
```

---

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `juror_gpt_model` | `gpt-5.2` | OpenAI juror model |
| `juror_claude_model` | `claude-sonnet-4-5-20250929` | Anthropic juror model |
| `juror_gemini_model` | `gemini-3-pro-preview` | Google juror model |
| `judge_model` | `claude-opus-4-5-20251101` | Arbitration model |
| `runs_per_model` | `2` | Runs per juror model |
| `validation_retries` | `2` | PydanticAI retries |

---

## Code Reference

| File | Component | Purpose |
|------|-----------|---------|
| `run/factory.py` | `Juror`, `JudgeItemFn` | Protocol definitions |
| `run/factory.py` | `build_real_jury()` | Create 6 real jurors |
| `run/factory.py` | `build_fake_jury()` | Create 6 fake jurors |
| `run/factory.py` | `build_real_judge_item()` | Create real judge function |
| `run/factory.py` | `build_fake_judge_item()` | Create fake judge function |
| `scoring/agent.py` | `build_juror_agent()` | PydanticAI agent builder |
| `scoring/juror.py` | `JurorScorer` | Real juror with resilience |
| `scoring/fakes.py` | `DeterministicFakeJuror` | Hash-based fake juror |
| `scoring/fakes.py` | `deterministic_fake_judge_item()` | Mean-based fake judge |
| `judge/agent.py` | `build_judge_agent()` | PydanticAI agent builder |
| `constants.py` | `PHQ8_ITEMS` | The 8 item names |
| `constants.py` | `MAX_*` | Evidence limits |
| `graph/single_dialogue.py` | `build_single_dialogue_graph()` | Workflow builder |
| `graph/state.py` | `ScoringState` | LangGraph state definition |

---

## Related Documentation

- [Concepts: Jury Consensus](../concepts/jury-consensus.md) - How jurors work together
- [Concepts: Arbitration](../concepts/arbitration.md) - When judge intervenes
- [Concepts: Resilience](../concepts/resilience.md) - Error handling strategy
- [Architecture: LangGraph Workflow](../architecture/langgraph-workflow.md) - Full workflow details
