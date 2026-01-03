# Judge Agent

The judge agent is a PydanticAI-powered LLM that arbitrates contested PHQ-8 items when jurors disagree.

---

## Overview

The judge:

1. Reviews contested items identified by aggregation
2. Sees all juror votes and evidence
3. Has access to the scoring view text (`scoring_text`, typically `client_qa`)
4. Renders a final decision with rationale

---

## When Is the Judge Invoked?

The judge is called only when arbitration is triggered. See [Arbitration](../scoring/arbitration.md) for trigger conditions:

- Low max probability (< 0.60)
- High entropy (> 1.2)
- Clinical ambiguity (P(score >= 2) in [0.4, 0.6])
- Wide vote range (>= 2)
- Multiple insufficient_evidence flags
- High total score std (> 2.0)

---

## Architecture

```text
┌─────────────────────────────────────────────────────────────┐
│                      JUDGE AGENT                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  AggregatedPHQ8 with arbitration_items                      │
│         │                                                   │
│         ▼                                                   │
│  For each contested item:                                   │
│         │                                                   │
│         ├── Collect juror votes [1, 2, 1, 2, 1, 2]          │
│         ├── Collect juror evidence (up to 10 snippets)      │
│         ├── Build judge prompt                              │
│         │                                                   │
│         ▼                                                   │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ Layer 2: Transient Retry (tenacity)                 │    │
│  │ Retry on 429, 5xx, network errors                   │    │
│  └─────────────────────────────────────────────────────┘    │
│         │                                                   │
│         ▼                                                   │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ Layer 1: Validation Retry (PydanticAI)              │    │
│  │ Re-prompt on schema validation failures             │    │
│  └─────────────────────────────────────────────────────┘    │
│         │                                                   │
│         ▼                                                   │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ PydanticAI Agent                                    │    │
│  │ • Model: anthropic:claude-opus-4-5-20251101         │    │
│  │ • Output: JudgeItemResolution (structured JSON)     │    │
│  │ • Retries: 2 (validation failures)                  │    │
│  └─────────────────────────────────────────────────────┘    │
│         │                                                   │
│         ▼                                                   │
│  JudgeItemResolution                                        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Prompt Building

The judge uses a two-part prompting strategy: a system prompt and a per-item user prompt.

**File**: `judge/prompting.py`

### System Prompt

```python
def build_judge_system_prompt(prompt_version: str) -> str:
    return f"""You are an expert judge resolving contested PHQ-8 item scores.
Prompt version: {prompt_version}.

Return JSON ONLY. No markdown, no code fences, no prose.
"""
```

### Item Prompt

For each contested item, the judge receives detailed context:

```python
def build_judge_item_prompt(
    *,
    scoring_text: str,
    item: str,
    juror_votes: list[int],
    juror_evidence: list[str],
) -> str:
    if item not in PHQ8_ITEMS:
        raise ValueError(f"Unknown PHQ-8 item: {item!r}")

    # Limit evidence to MAX_JUDGE_EVIDENCE_SNIPPETS (10)
    evidence_block = "\n".join(f"- {e}" for e in juror_evidence[:MAX_JUDGE_EVIDENCE_SNIPPETS])

    return f"""Contested item: {item}

Juror votes: {juror_votes}
Juror evidence snippets:
{evidence_block}

Dialogue (view text):
{scoring_text}

Respond with JSON:
{{"item": "{item}", "final_score": 0, "confidence": 0.0, "rationale": "..."}}
"""
```

### Evidence Limit Constant

**File**: `constants.py`

```python
MAX_JUDGE_EVIDENCE_SNIPPETS = 10
```

This limit prevents context window overflow when many jurors provide extensive evidence. With 6 jurors each providing up to 3 snippets (18 total), the judge sees at most 10 to keep prompts manageable.

---

## Output Schema

**File**: `judge/schema.py`

### JudgeItemResolution

```python
class JudgeItemResolution(BaseModel):
    """Judge decision for a single contested PHQ-8 item."""

    model_config = ConfigDict(extra="forbid")

    item: str = Field(min_length=1)
    final_score: Literal[0, 1, 2, 3]
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str = Field(min_length=1)
```

Key constraints:

- `extra="forbid"` - No extra fields allowed
- `final_score` - Must be exactly 0, 1, 2, or 3
- `confidence` - Must be between 0.0 and 1.0
- `rationale` - Must be non-empty (requires explanation)

### Example Output

```json
{
  "item": "anhedonia",
  "final_score": 2,
  "confidence": 0.85,
  "rationale": "The client explicitly states 'I just don't enjoy things anymore' and describes previously enjoyable activities as now feeling 'empty'. This suggests more than half the days, consistent with a score of 2."
}
```

---

## Judge vs Juror

| Aspect | Juror | Judge |
|--------|-------|-------|
| **Purpose** | Independent scoring | Arbitration |
| **Model** | Mixed (GPT, Claude, Gemini) | Claude Opus (most capable) |
| **Scope** | All 8 items | Only contested items |
| **Context** | `scoring_text` view | `scoring_text` + juror votes + evidence |
| **Invocation** | Always (6 per dialogue) | Conditional (contested items only) |
| **Rate Limiting** | Yes (Layer 3) | No (Layer 1–2 only) |

---

## Why Claude Opus for Judge?

The judge role requires:

- Careful deliberation over conflicting evidence
- Clinical reasoning about symptom severity
- Synthesis of multiple perspectives
- Explicit rationale generation

Claude Opus is chosen for its:

- Strong clinical reasoning capabilities
- Careful, nuanced responses
- High instruction following
- Explicit reasoning traces

---

## Resilience Strategy

The judge uses **two layers** of ADR-001's three-layer resilience strategy:

### Layer 1: Validation Retry (PydanticAI)

```python
agent = build_judge_agent(
    model=full_model_name,
    prompt_version=settings.prompt_version,
    retries=settings.validation_retries,  # Default: 2
)
```

If the LLM returns malformed JSON or fails schema validation, PydanticAI automatically re-prompts with error context.

### Layer 2: Transient Retry (Tenacity)

```python
@retry(
    stop=stop_after_attempt(max_retries),  # Default: 5
    wait=wait_exponential_jitter(
        initial=retry_initial_wait,  # Default: 1.0s
        max=retry_max_wait,          # Default: 60.0s
        jitter=retry_jitter,         # Default: 5.0s
    ),
    retry=retry_if_exception(_is_transient_error),
    reraise=True,
)
def _call_with_retry() -> JudgeItemResolution:
    result = agent.run_sync(prompt)
    return result.data
```

### Why No Layer 3 (Rate Limiting)?

The judge does **not** use Layer 3 rate limiting because:

- Judge calls are conditional (only on contested items)
- Calls are sequential (one contested item at a time)
- Layer 2 retry handles 429s when they occur
- Synchronous execution makes async rate limiting complex

---

## Building the Judge

**File**: `run/factory.py`

### Real Judge (Live API)

```python
from vibe_check.run.factory import build_real_judge_item

judge_fn = build_real_judge_item(settings)
```

**What `build_real_judge_item()` does:**

1. Creates PydanticAI agent with Claude Opus model
2. Configures validation retries
3. Returns a closure that:
   - Collects votes and evidence from juror reports
   - Builds the item prompt
   - Wraps the API call with tenacity retry
   - Returns `JudgeItemResolution`

### Fake Judge (Testing)

```python
from vibe_check.run.factory import build_fake_judge_item

judge_fn = build_fake_judge_item()
```

**How the fake judge works:**

```python
def deterministic_fake_judge_item(
    scoring_text: str,
    item: str,
    juror_reports: list[PHQ8Report],
    prompt_version: str,
) -> JudgeItemResolution:
    # Collect votes from all jurors
    votes = [int(getattr(r, item).score) for r in juror_reports]

    # Calculate mean and round to nearest score
    avg = sum(votes) / float(len(votes))
    final = max(0, min(3, round(avg)))

    return JudgeItemResolution(
        item=item,
        final_score=final,
        confidence=0.7,
        rationale="Deterministic fake judge (mean of juror votes).",
    )
```

Features:

- Deterministic (mean of juror votes)
- No API calls, instant execution
- Fixed confidence (0.7)
- Clear rationale indicating fake

---

## Usage in Workflow

**File**: `graph/single_dialogue.py`

The judge is called from the `arbitrate` node in the LangGraph workflow:

```python
def arbitrate_node(state: ScoringState) -> dict[str, Any]:
    agg = state["final_output"]

    # Determine which items need arbitration
    contested = [item for item in agg.arbitration_items if item in PHQ8_ITEMS]

    # If "__total__" is flagged, arbitrate all items
    if "__total__" in agg.arbitration_items:
        contested = list(PHQ8_ITEMS)

    if not contested:
        return {"final_output": agg, "needs_arbitration": False}

    # Call judge for each contested item
    resolutions: dict[str, JudgeItemResolution] = {}
    for item in contested:
        resolutions[item] = judge_item(
            state["scoring_text"],
            item,
            agg.juror_reports,
            state["prompt_version"],
        )

    # Update final scores with judge decisions
    final_item_scores = dict(agg.final_item_scores)
    for item, resolution in resolutions.items():
        final_item_scores[item] = int(resolution.final_score)

    final_total_score = sum(final_item_scores.values())

    # Create updated output with judge_override as source
    updated = agg.model_copy(
        update={
            "final_item_scores": final_item_scores,
            "final_total_score": final_total_score,
            "final_severity_bucket": get_severity_bucket(final_total_score),
            "final_source": "judge_override",
            "judge_resolution": {k: v.model_dump() for k, v in resolutions.items()},
        }
    )
    return {"final_output": updated, "needs_arbitration": False}
```

---

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `judge_model` | `claude-opus-4-5-20251101` | Model for judge |
| `validation_retries` | `2` | PydanticAI retries |
| `max_retries` | `5` | Tenacity retries |
| `retry_initial_wait` | `1.0` | Initial backoff (seconds) |
| `retry_max_wait` | `60.0` | Max backoff (seconds) |
| `retry_jitter` | `5.0` | Jitter range (seconds) |

---

## Constants Used

| Constant | Value | Location | Purpose |
|----------|-------|----------|---------|
| `MAX_JUDGE_EVIDENCE_SNIPPETS` | 10 | `constants.py` | Max evidence shown to judge |
| `PHQ8_ITEMS` | 8-tuple | `constants.py` | Valid item names for validation |

---

## Code Reference

| File | Component | Purpose |
|------|-----------|---------|
| `judge/agent.py` | `build_judge_agent()` | PydanticAI agent builder |
| `judge/prompting.py` | `build_judge_system_prompt()` | System prompt builder |
| `judge/prompting.py` | `build_judge_item_prompt()` | Item-specific prompt builder |
| `judge/schema.py` | `JudgeItemResolution` | Output schema with constraints |
| `run/factory.py` | `build_real_judge_item()` | Factory with resilience wiring |
| `run/factory.py` | `build_fake_judge_item()` | Factory for testing |
| `scoring/fakes.py` | `deterministic_fake_judge_item()` | Mean-based fake |
| `constants.py` | `MAX_JUDGE_EVIDENCE_SNIPPETS` | Evidence limit (10) |
| `constants.py` | `PHQ8_ITEMS` | Valid item names |
| `graph/single_dialogue.py` | `arbitrate_node()` | Workflow integration |

---

## Related Documentation

- [Scoring: Arbitration](../scoring/arbitration.md) - When judge is invoked
- [Reliability: Resilience](../reliability/resilience.md) - Error handling
- [Juror](juror.md) - Independent scoring agent
- [Agents Overview](index.md) - Agent protocols and constants
