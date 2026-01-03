# Judge Agent

The judge agent is a PydanticAI-powered LLM that arbitrates contested PHQ-8 items when jurors disagree.

---

## Overview

The judge:
1. Reviews contested items identified by aggregation
2. Sees all juror votes and evidence
3. Has access to the full dialogue
4. Renders a final decision with rationale

---

## When Is the Judge Invoked?

The judge is called only when arbitration is triggered. See [Arbitration](../concepts/arbitration.md) for trigger conditions:

- Low max probability (< 0.60)
- High entropy (> 1.2)
- Clinical ambiguity (P(score ≥ 2) ∈ [0.4, 0.6])
- Wide vote range (≥ 2)
- Multiple insufficient_evidence flags

---

## Architecture

```
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
│  │ • Model: anthropic:claude-opus-4-5                  │    │
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

## System Prompt

```
You are an expert judge resolving contested PHQ-8 item scores.
Prompt version: v1.0.

Return JSON ONLY. No markdown, no code fences, no prose.
```

---

## Item Prompt

The judge receives detailed context for each contested item:

```
Contested item: anhedonia

Juror votes: [1, 2, 1, 2, 1, 2]
Juror evidence snippets:
- "I just don't enjoy things anymore"
- "Nothing feels fun"
- "I used to love reading, but now..."
- "Activities I used to enjoy feel empty"

Dialogue (view text):
Therapist: How have you been feeling lately?
Client: Not great. I just don't enjoy things anymore...
[... full dialogue ...]

Respond with JSON:
{"item": "anhedonia", "final_score": 0, "confidence": 0.0, "rationale": "..."}
```

---

## Output Schema

### JudgeItemResolution

```python
class JudgeItemResolution(BaseModel):
    item: str           # "anhedonia"
    final_score: int    # 0, 1, 2, or 3
    confidence: float   # 0.0-1.0
    rationale: str      # Explanation for the decision
```

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
| **Context** | Dialogue only | Dialogue + juror votes + evidence |
| **Invocation** | Always (6 per dialogue) | Conditional (~30% of dialogues) |
| **Cost** | ~$0.05/dialogue | ~$0.50/item |

---

## Why Claude Opus for Judge?

The judge role requires:
- Careful deliberation over conflicting evidence
- Clinical reasoning about symptom severity
- Synthesis of multiple perspectives

Claude Opus is chosen for its:
- Strong clinical reasoning capabilities
- Careful, nuanced responses
- Explicit rationale generation

---

## Rate Limiting

The judge does **not** use Layer 3 rate limiting because:
- Judge calls are infrequent (only on arbitration)
- Sequential calls for multiple items
- Layer 2 retry handles 429s if they occur

---

## Building the Judge

### Real Judge (Live API)

```python
from vibe_check.run.factory import build_real_judge_item

judge_fn = build_real_judge_item(settings)
```

### Fake Judge (Testing)

```python
from vibe_check.run.factory import build_fake_judge_item

judge_fn = build_fake_judge_item()
```

---

## Usage in Workflow

The judge is called from the `arbitrate` node in the LangGraph workflow:

```python
for item in contested_items:
    resolution = judge_fn(
        scoring_text=state["scoring_text"],
        item=item,
        juror_reports=agg.juror_reports,
        prompt_version=state["prompt_version"],
    )
    final_item_scores[item] = resolution.final_score
```

---

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `judge_model` | `claude-opus-4-5-20250929` | Model for judge |
| `validation_retries` | `2` | PydanticAI retries |
| `max_retries` | `5` | Tenacity retries |

---

## Code Reference

| File | Component | Purpose |
|------|-----------|---------|
| `judge/agent.py` | `build_judge_agent()` | PydanticAI agent builder |
| `judge/prompting.py` | `build_judge_system_prompt()` | System prompt |
| `judge/prompting.py` | `build_judge_item_prompt()` | Item-specific prompt |
| `judge/schema.py` | `JudgeItemResolution` | Output schema |
| `run/factory.py` | `build_real_judge_item()` | Factory function |
| `scoring/fakes.py` | `deterministic_fake_judge_item()` | Testing fake |

---

## Related Documentation

- [Concepts: Arbitration](../concepts/arbitration.md) - When judge is invoked
- [Concepts: Resilience](../concepts/resilience.md) - Error handling
- [Juror](juror.md) - Independent scoring agent
