# Juror Agent

The juror agent is a PydanticAI-powered LLM that independently scores PHQ-8 items from therapy dialogue text.

---

## Overview

Each juror:
1. Receives preprocessed dialogue text
2. Scores all 8 PHQ-8 items (0-3 scale)
3. Extracts supporting evidence quotes
4. Detects self-harm mentions
5. Returns a structured `PHQ8Report`

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      JUROR AGENT                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  scoring_text (client_qa view)                              │
│         │                                                   │
│         ▼                                                   │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ Layer 3: Rate Limiting (aiolimiter)                 │    │
│  │ Wait for provider token before proceeding           │    │
│  └─────────────────────────────────────────────────────┘    │
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
│  │ • Model: openai:gpt-5.2 / anthropic:claude / etc    │    │
│  │ • Output: PHQ8Assessment (structured JSON)          │    │
│  │ • Retries: 2 (validation failures)                  │    │
│  └─────────────────────────────────────────────────────┘    │
│         │                                                   │
│         ▼                                                   │
│  PHQ8Report (with metadata)                                 │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## JurorScorer Class

The main interface for juror scoring:

```python
class JurorScorer:
    def __init__(
        self,
        *,
        agent: Agent[Any, PHQ8Assessment],
        model_id: str,
        run_number: int,
        prompt_version: str,
        rate_limiter: AsyncLimiter | None = None,
        max_retries: int = 5,
        retry_initial_wait: float = 1.0,
        retry_max_wait: float = 60.0,
        retry_jitter: float = 5.0,
    ): ...

    def score(self, scoring_text: str) -> PHQ8Report:
        """Synchronous scoring."""

    async def ascore(self, scoring_text: str) -> PHQ8Report:
        """Asynchronous scoring with full resilience."""
```

---

## System Prompt

The juror system prompt instructs the model:

```
You are a clinical scoring juror. Score PHQ-8.

Input: a preprocessed dialogue view named `client_qa` from a synthetic therapy conversation.
Prompt version: v1.0.

Rules:
- Use ONLY the provided text. Do not assume facts not stated.
- Score PHQ-8 items only (8 items). Self-harm is a separate boolean tag, not an extra item.
- Therapist lines are context; evidence should quote/paraphrase CLIENT statements.
- If evidence is insufficient for an item, set `insufficient_evidence=true` and still choose the best score (0-3).

For each item, return:
- score: integer 0-3
- confidence: float 0.0-1.0
- evidence: list of up to 3 short snippets (each <= 50 words)
- insufficient_evidence: boolean

Also return:
- mentions_self_harm: boolean (true if the client expresses self-harm/suicidal ideation)
- self_harm_evidence: list of up to 3 short snippets
- total_score: sum of the 8 item scores (0-24)

Return JSON ONLY. No markdown, no code fences, no prose.

Items (PHQ-8):
- anhedonia
- depressed_mood
- sleep
- fatigue
- appetite
- guilt
- concentration
- psychomotor
```

---

## PHQ-8 Items

| Item | Description | Score Meaning |
|------|-------------|---------------|
| `anhedonia` | Little interest or pleasure | 0=not at all, 3=nearly every day |
| `depressed_mood` | Feeling down, depressed | 0=not at all, 3=nearly every day |
| `sleep` | Trouble sleeping or sleeping too much | 0=not at all, 3=nearly every day |
| `fatigue` | Feeling tired or little energy | 0=not at all, 3=nearly every day |
| `appetite` | Poor appetite or overeating | 0=not at all, 3=nearly every day |
| `guilt` | Feeling bad about self or failure | 0=not at all, 3=nearly every day |
| `concentration` | Trouble concentrating | 0=not at all, 3=nearly every day |
| `psychomotor` | Moving/speaking slowly or fidgety | 0=not at all, 3=nearly every day |

---

## Output Schema

### PHQ8Assessment (Raw LLM Output)

```python
class PHQ8Assessment(BaseModel):
    anhedonia: PHQ8ItemScore
    depressed_mood: PHQ8ItemScore
    sleep: PHQ8ItemScore
    fatigue: PHQ8ItemScore
    appetite: PHQ8ItemScore
    guilt: PHQ8ItemScore
    concentration: PHQ8ItemScore
    psychomotor: PHQ8ItemScore

    total_score: int  # 0-24

    mentions_self_harm: bool
    self_harm_evidence: list[str]
```

### PHQ8ItemScore

```python
class PHQ8ItemScore(BaseModel):
    score: Literal[0, 1, 2, 3]
    confidence: float  # 0.0-1.0
    evidence: list[str]  # Up to 3 quotes, max 50 words each
    insufficient_evidence: bool
```

### PHQ8Report (With Metadata)

```python
class PHQ8Report(PHQ8Assessment):
    model_id: str       # "gpt-5.2"
    run_number: int     # 1 or 2
    usage: TokenUsage | None
    scored_at: datetime
```

---

## Example Output

```json
{
  "anhedonia": {
    "score": 2,
    "confidence": 0.85,
    "evidence": ["I just don't enjoy things anymore", "Nothing feels fun"],
    "insufficient_evidence": false
  },
  "depressed_mood": {
    "score": 3,
    "confidence": 0.92,
    "evidence": ["I feel hopeless every day", "I can't shake this sadness"],
    "insufficient_evidence": false
  },
  "sleep": {
    "score": 2,
    "confidence": 0.78,
    "evidence": ["I wake up at 3am most nights"],
    "insufficient_evidence": false
  },
  ...
  "total_score": 15,
  "mentions_self_harm": false,
  "self_harm_evidence": [],
  "model_id": "gpt-5.2",
  "run_number": 1,
  "scored_at": "2026-01-03T12:34:56Z"
}
```

---

## Building Jurors

### Real Jurors (Live API)

```python
from vibe_check.run.factory import build_real_jury

jurors = build_real_jury(settings)
# Returns 6 jurors: 3 models × 2 runs
```

### Fake Jurors (Testing)

```python
from vibe_check.run.factory import build_fake_jury

jurors = build_fake_jury()
# Returns 6 deterministic fake jurors
```

---

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `juror_gpt_model` | `gpt-5.2` | OpenAI model ID |
| `juror_claude_model` | `claude-sonnet-4-5-20250929` | Anthropic model ID |
| `juror_gemini_model` | `gemini-3-pro-preview` | Google model ID |
| `runs_per_model` | `2` | Runs per model |
| `validation_retries` | `2` | PydanticAI retries |
| `max_retries` | `5` | Tenacity retries |

---

## Code Reference

| File | Component | Purpose |
|------|-----------|---------|
| `scoring/juror.py` | `JurorScorer` | Main scoring class |
| `scoring/agent.py` | `build_juror_agent()` | PydanticAI agent builder |
| `scoring/prompting.py` | `build_juror_system_prompt()` | System prompt builder |
| `scoring/fakes.py` | `DeterministicFakeJuror` | Testing fake |
| `schemas/scoring.py` | `PHQ8Report` | Output schema |
| `run/factory.py` | `build_real_jury()` | Factory function |

---

## Related Documentation

- [Concepts: Jury Consensus](../concepts/jury-consensus.md) - How jurors work together
- [Concepts: Resilience](../concepts/resilience.md) - Three-layer error handling
- [Judge](judge.md) - Arbitration agent
