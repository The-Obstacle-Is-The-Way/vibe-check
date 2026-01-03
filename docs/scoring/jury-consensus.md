# Jury Consensus Model

The jury consensus model is vibe-check's core approach to reliable PHQ-8 scoring. Instead of trusting a single LLM's judgment, multiple independent "jurors" score each dialogue, and their votes are statistically aggregated.

---

## Why Multiple Jurors?

Single-model scoring has inherent risks:

| Risk | Description |
|------|-------------|
| **Model bias** | Each LLM has systematic tendencies (over/under-scoring) |
| **Stochastic variance** | Same model, same input can produce different outputs |
| **Blind spots** | Models miss evidence that other models catch |
| **Hallucination** | Single model errors go undetected |

Multiple jurors mitigate these risks through **diversity** and **redundancy**.

---

## Jury Composition

The default jury consists of **6 jurors**:

```
3 models × 2 runs each = 6 independent votes per item
```

| Provider | Model | Runs | Purpose |
|----------|-------|------|---------|
| OpenAI | `gpt-5.2` | 2 | Frontier reasoning |
| Anthropic | `claude-sonnet-4-5` | 2 | Clinical nuance |
| Google | `gemini-3-pro-preview` | 2 | Cross-validation |

**Why 2 runs per model?**
- Captures within-model variance
- Detects stochastic instability
- If a model's 2 runs disagree, that signals uncertainty

---

## How Jurors Score

Each juror independently:

1. Receives the same preprocessed dialogue text (`scoring_text`)
2. Evaluates all 8 PHQ-8 items
3. Returns a `PHQ8Report` with:
   - Per-item scores (0-3 scale)
   - Confidence ratings
   - Supporting evidence (quotes from dialogue)
   - Self-harm detection flags

```
┌────────────────────────────────────────────────────────────────┐
│                    JUROR SCORING PROCESS                       │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  Dialogue Text (client_qa view)                                │
│         │                                                      │
│         ├──────────────────────────────────────────────────┐   │
│         │           │           │           │           │  │   │
│         ▼           ▼           ▼           ▼           ▼  ▼   │
│     ┌──────┐   ┌──────┐   ┌──────┐   ┌──────┐   ┌──────┐   │   │
│     │GPT-1 │   │GPT-2 │   │CLD-1 │   │CLD-2 │   │GEM-1 │ ...   │
│     └──┬───┘   └──┬───┘   └──┬───┘   └──┬───┘   └──┬───┘       │
│        │          │          │          │          │           │
│        ▼          ▼          ▼          ▼          ▼           │
│    PHQ8Report PHQ8Report PHQ8Report PHQ8Report PHQ8Report      │
│                                                                │
│    All 6 reports collected → Aggregation                       │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

---

## Independence Guarantee

Jurors operate with strict independence:

- **No cross-talk**: Jurors don't see other jurors' outputs
- **Parallel execution**: All 6 run concurrently (no sequential bias)
- **Identical input**: Same preprocessed text for all jurors
- **Separate prompts**: Each juror uses its own system prompt

This independence ensures votes are truly independent samples, which is mathematically required for valid Bayesian aggregation.

---

## Vote Collection

After all jurors complete, their votes are collected per item:

```python
# Example vote collection for "anhedonia" item
votes = {
    "anhedonia": [1, 2, 1, 2, 1, 2],  # 6 juror votes
    "depressed_mood": [2, 2, 2, 2, 3, 2],
    "sleep": [3, 3, 3, 3, 2, 3],
    # ... 8 items total
}
```

These votes become the input to [Bayesian Aggregation](bayesian-aggregation.md).

---

## Juror Protocol

All jurors implement the `Juror` protocol:

```python
class Juror(Protocol):
    def score(self, scoring_text: str) -> PHQ8Report: ...
    async def ascore(self, scoring_text: str) -> PHQ8Report: ...
```

This allows both:
- **Real jurors**: `JurorScorer` backed by live LLM APIs
- **Fake jurors**: `DeterministicFakeJuror` for testing/dry-runs

---

## Resilience

Each juror implements the [three-layer resilience strategy](../reliability/resilience.md):

1. **Layer 1**: PydanticAI validation retries (malformed JSON)
2. **Layer 2**: Tenacity transient retry (429, 5xx, network errors)
3. **Layer 3**: Aiolimiter rate limiting (proactive throttling)

This ensures reliable scoring even under API instability.

---

## Configuration

Jury composition is configured via `Settings`:

| Setting | Default | Description |
|---------|---------|-------------|
| `juror_gpt_model` | `gpt-5.2` | OpenAI model for jurors |
| `juror_claude_model` | `claude-sonnet-4-5-20250929` | Anthropic model for jurors |
| `juror_gemini_model` | `gemini-3-pro-preview` | Google model for jurors |
| `runs_per_model` | `2` | Number of runs per model |

---

## Related Concepts

- [Bayesian Aggregation](bayesian-aggregation.md) - How votes become posteriors
- [Arbitration](arbitration.md) - What happens when jurors disagree
- [Resilience](../reliability/resilience.md) - How jurors handle API failures
