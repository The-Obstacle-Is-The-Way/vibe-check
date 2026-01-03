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

## Agent Protocol

All agents implement a common interface:

```python
class Juror(Protocol):
    def score(self, scoring_text: str) -> PHQ8Report: ...
    async def ascore(self, scoring_text: str) -> PHQ8Report: ...

class JudgeItemFn(Protocol):
    def __call__(
        self,
        scoring_text: str,
        item: str,
        juror_reports: list[PHQ8Report],
        prompt_version: str,
    ) -> JudgeItemResolution: ...
```

---

## Real vs Fake Agents

### Real Agents

Use live LLM APIs with full resilience:

```python
from vibe_check.run.factory import build_real_jury, build_real_judge_item

jurors = build_real_jury(settings)
judge = build_real_judge_item(settings)
```

### Fake Agents

Deterministic fakes for testing/dry-runs:

```python
from vibe_check.run.factory import build_fake_jury, build_fake_judge_item

jurors = build_fake_jury()
judge = build_fake_judge_item()
```

Fake agents use hash-based scoring for reproducibility.

---

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `juror_gpt_model` | `gpt-5.2` | OpenAI juror model |
| `juror_claude_model` | `claude-sonnet-4-5-20250929` | Anthropic juror model |
| `juror_gemini_model` | `gemini-3-pro-preview` | Google juror model |
| `judge_model` | `claude-opus-4-5-20250929` | Arbitration model |
| `runs_per_model` | `2` | Runs per juror model |
| `validation_retries` | `2` | PydanticAI retries |

---

## Related Documentation

- [Concepts: Jury Consensus](../concepts/jury-consensus.md) - How jurors work together
- [Concepts: Arbitration](../concepts/arbitration.md) - When judge intervenes
- [Concepts: Resilience](../concepts/resilience.md) - Error handling strategy
