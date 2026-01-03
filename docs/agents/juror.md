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

```text
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

**File**: `scoring/juror.py`

```python
class JurorScorer:
    """Score PHQ-8 for a single dialogue view with one model run.

    Implements ADR-001's three-layer resilience strategy:
    - Layer 1: PydanticAI validation retries (configured in Agent)
    - Layer 2: Tenacity transient retry (for 429, 5xx, network errors)
    - Layer 3: Aiolimiter rate limiting (proactive throttling)
    """

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

    @property
    def model_id(self) -> str: ...

    @property
    def run_number(self) -> int: ...

    @property
    def prompt_version(self) -> str: ...

    def score(self, scoring_text: str) -> PHQ8Report:
        """Synchronous scoring (simple use cases)."""

    async def ascore(self, scoring_text: str) -> PHQ8Report:
        """Async scoring with full resilience (production)."""
```

---

## System Prompt

The juror system prompt instructs the model:

**File**: `scoring/prompting.py`

```text
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

## Output Schemas

**File**: `schemas/scoring.py`

### PHQ8ItemScore

Single PHQ-8 item score from one model run:

```python
class PHQ8ItemScore(BaseModel):
    """Single PHQ-8 item score from one model run."""

    model_config = ConfigDict(extra="forbid")

    score: Literal[0, 1, 2, 3] = Field(
        description="0=Not at all, 1=Several days, 2=More than half, 3=Nearly every day",
    )
    confidence: float = Field(ge=0.0, le=1.0, description="Model's self-reported confidence")
    evidence: list[str] = Field(default_factory=list, max_length=3)
    insufficient_evidence: bool = Field(default=False)
```

### PHQ8Assessment

The raw output from the LLM (items + total + safety):

```python
class PHQ8Assessment(BaseModel):
    """The raw output from the LLM (items + total + safety)."""

    model_config = ConfigDict(extra="forbid")

    anhedonia: PHQ8ItemScore
    depressed_mood: PHQ8ItemScore
    sleep: PHQ8ItemScore
    fatigue: PHQ8ItemScore
    appetite: PHQ8ItemScore
    guilt: PHQ8ItemScore
    concentration: PHQ8ItemScore
    psychomotor: PHQ8ItemScore

    total_score: int = Field(ge=0, le=24)

    mentions_self_harm: bool = False
    self_harm_evidence: list[str] = Field(default_factory=list, max_length=3)

    @property
    def item_scores(self) -> dict[str, int]:
        """Return a dict of item name → score."""
        ...
```

### PHQ8Report

Complete PHQ-8 assessment with metadata (provenance):

```python
class PHQ8Report(PHQ8Assessment):
    """Complete PHQ-8 assessment with metadata (provenance)."""

    model_id: str = Field(min_length=1, description="e.g., 'gpt-5.2'")
    run_number: int = Field(ge=1, le=2, description="Run 1 or 2")
    usage: TokenUsage | None = None
    scored_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

---

## Validation and Auto-Fix Logic

The schemas include validators to ensure data quality and automatically fix common LLM errors.

### Evidence Snippet Validation

**File**: `schemas/scoring.py:36-49`

```python
@field_validator("evidence")
@classmethod
def _validate_evidence_snippets(cls, value: list[str]) -> list[str]:
    for snippet in value:
        cleaned = snippet.strip()
        if not cleaned:
            raise ValueError("evidence snippets must be non-empty strings")
        if len(cleaned) > MAX_EVIDENCE_SNIPPET_CHARS:  # 400 chars
            raise ValueError(
                f"evidence snippet exceeds {MAX_EVIDENCE_SNIPPET_CHARS} characters"
            )
        if len(cleaned.split()) > MAX_EVIDENCE_SNIPPET_WORDS:  # 50 words
            raise ValueError(f"evidence snippet exceeds {MAX_EVIDENCE_SNIPPET_WORDS} words")
    return value
```

### Total Score Auto-Fix

LLMs sometimes miscalculate `total_score`. This pre-validator automatically corrects it:

**File**: `schemas/scoring.py:84-112`

```python
@model_validator(mode="before")
@classmethod
def _canonicalize_total_score(cls, data: Any) -> Any:
    """Auto-fix total_score if LLM miscalculated it."""
    if not isinstance(data, dict):
        return data

    item_keys = (
        "anhedonia", "depressed_mood", "sleep", "fatigue",
        "appetite", "guilt", "concentration", "psychomotor",
    )
    expected = 0
    for key in item_keys:
        item = data.get(key)
        if item is None:
            return data
        score = item.get("score") if isinstance(item, dict) else getattr(item, "score", None)
        if score is None:
            return data
        expected += int(score)

    # Silently fix if LLM miscalculated
    if data.get("total_score") != expected:
        data["total_score"] = expected
    return data
```

### Total Score Post-Validation

After auto-fix, a post-validator confirms the sum is correct:

**File**: `schemas/scoring.py:114-119`

```python
@model_validator(mode="after")
def _check_total_score(self) -> PHQ8Assessment:
    expected = sum(self.item_scores.values())
    if self.total_score != expected:
        raise ValueError(f"total_score={self.total_score} does not match item sum={expected}")
    return self
```

---

## Evidence Limits

| Constant | Value | Location | Purpose |
|----------|-------|----------|---------|
| `MAX_EVIDENCE_SNIPPET_WORDS` | 50 | `constants.py` | Max words per quote |
| `MAX_EVIDENCE_SNIPPET_CHARS` | 400 | `constants.py` | Max chars per quote |
| `max_length=3` | 3 | `schemas/scoring.py` | Max evidence list size |

These limits prevent:

- Token explosion in downstream prompts
- Context window overflow for judge
- Cost overruns from verbose LLM outputs

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
  "fatigue": {
    "score": 2,
    "confidence": 0.80,
    "evidence": ["I'm exhausted all the time"],
    "insufficient_evidence": false
  },
  "appetite": {
    "score": 1,
    "confidence": 0.70,
    "evidence": ["I've been eating less"],
    "insufficient_evidence": false
  },
  "guilt": {
    "score": 3,
    "confidence": 0.88,
    "evidence": ["I feel like a failure", "Everything is my fault"],
    "insufficient_evidence": false
  },
  "concentration": {
    "score": 2,
    "confidence": 0.75,
    "evidence": ["I can't focus on anything"],
    "insufficient_evidence": false
  },
  "psychomotor": {
    "score": 1,
    "confidence": 0.65,
    "evidence": ["I've been moving slowly"],
    "insufficient_evidence": true
  },
  "total_score": 16,
  "mentions_self_harm": false,
  "self_harm_evidence": [],
  "model_id": "gpt-5.2",
  "run_number": 1,
  "usage": {
    "input_tokens": 1250,
    "output_tokens": 450,
    "reasoning_tokens": null,
    "total_tokens": 1700
  },
  "scored_at": "2026-01-03T12:34:56Z"
}
```

---

## Building Jurors

### Real Jurors (Live API)

**File**: `run/factory.py`

```python
from vibe_check.run.factory import build_real_jury

jurors = build_real_jury(settings)
# Returns 6 JurorScorer instances: 3 models × 2 runs

# Each juror is wired with:
# - PydanticAI agent with validation retries
# - Per-provider rate limiter (aiolimiter)
# - Tenacity retry decorator for transient errors
```

**What `build_real_jury()` does:**

1. Creates rate limiters for OpenAI, Anthropic, Google
2. For each provider, builds PydanticAI agents with proper model prefix
3. Wraps each agent in `JurorScorer` with resilience settings
4. Returns 6 jurors (3 models × 2 runs each)

### Fake Jurors (Testing)

```python
from vibe_check.run.factory import build_fake_jury

jurors = build_fake_jury()
# Returns 6 DeterministicFakeJuror instances
```

**How fake jurors score:**

```python
# Hash-based scoring for reproducibility
seed = f"{model_id}|{run_number}|{item}|{scoring_text}"
score = int(hashlib.sha256(seed.encode()).hexdigest(), 16) % 4
```

Same input always produces same output, enabling deterministic tests.

---

## Deterministic Fake Juror

**File**: `scoring/fakes.py`

```python
@dataclass(frozen=True)
class DeterministicFakeJuror:
    """A fake juror that returns deterministic scores based on hash of input."""

    model_id: str
    run_number: int

    def score(self, scoring_text: str) -> PHQ8Report:
        """Synchronous scoring."""
        ...

    async def ascore(self, scoring_text: str) -> PHQ8Report:
        """Async scoring (just calls sync)."""
        return self.score(scoring_text)
```

Features:

- Immutable (`frozen=True`)
- Hash-based scoring (deterministic)
- Returns fake `TokenUsage` for completeness
- No API calls, instant execution

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
| `retry_initial_wait` | `1.0` | Initial backoff (seconds) |
| `retry_max_wait` | `60.0` | Max backoff (seconds) |
| `retry_jitter` | `5.0` | Jitter range (seconds) |

---

## Code Reference

| File | Component | Purpose |
|------|-----------|---------|
| `scoring/juror.py` | `JurorScorer` | Main scoring class with resilience |
| `scoring/agent.py` | `build_juror_agent()` | PydanticAI agent builder |
| `scoring/prompting.py` | `build_juror_system_prompt()` | System prompt builder |
| `scoring/fakes.py` | `DeterministicFakeJuror` | Hash-based fake for testing |
| `schemas/scoring.py` | `PHQ8ItemScore` | Single item schema |
| `schemas/scoring.py` | `PHQ8Assessment` | Raw LLM output schema |
| `schemas/scoring.py` | `PHQ8Report` | Full report with metadata |
| `schemas/scoring.py` | `TokenUsage` | Token usage tracking |
| `run/factory.py` | `build_real_jury()` | Factory for real jurors |
| `run/factory.py` | `build_fake_jury()` | Factory for fake jurors |
| `constants.py` | `PHQ8_ITEMS` | Tuple of 8 item names |
| `constants.py` | `MAX_EVIDENCE_*` | Evidence size limits |

---

## Related Documentation

- [Scoring: Jury Consensus](../scoring/jury-consensus.md) - How jurors work together
- [Reliability: Resilience](../reliability/resilience.md) - Three-layer error handling
- [Judge](judge.md) - Arbitration agent
- [Agents Overview](index.md) - Agent protocols and constants
