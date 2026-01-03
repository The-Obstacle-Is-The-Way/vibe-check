# SPEC-04: Juror Scoring Agent (Structured PHQ-8 Output)

**Status**: IMPLEMENTED (2026-01-03)
**Slice Type**: Vertical (Single Dialogue → `PHQ8Report`)
**Dependencies**: SPEC-01 (DevEx), SPEC-02 (Dialogue Views), SPEC-03 (PHQ-8 Schemas)
**Estimated Scope**: ~300 lines of code, ~250 lines of tests

---

## 1. Objective

Implement a single-model “juror” scoring agent that:

1. Takes a preprocessed dialogue view (default: `client_qa_text`)
2. Prompts an LLM to score **PHQ-8** (not PHQ-9) with evidence
3. Produces a validated `PHQ8Report` (Pydantic schema)
4. Captures per-call token usage (incl. reasoning tokens when available)
5. Logs transcript text at DEBUG level only (operational hygiene)

This slice is the smallest end-to-end unit that touches LLM I/O while remaining testable and deterministic via a local `TestModel` (no network / no API keys).

### Success Criteria

```python
from vibe_check.preprocessing import preprocess_dialogue
from vibe_check.schemas.input import SQPsychConvDialogue
from vibe_check.schemas.scoring import PHQ8Report
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel

from vibe_check.scoring import JurorScorer

dialogue = SQPsychConvDialogue(
    file_id="active82",
    condition="mdd",
    client_model="qwen25",
    therapist_model="qwen25",
    dialogue="Therapist: ...\nClient: ...",
    computed_split="train",
)
views = preprocess_dialogue(dialogue)

model = TestModel(custom_output_args={"...": "fixture-loaded"})
agent = Agent(model=model, output_type=dict, system_prompt="...")
scorer = JurorScorer(agent=agent, model_id="fake-model", run_number=1, prompt_version="v1")

report: PHQ8Report = scorer.score(views.client_qa_text)
assert report.total_score == sum(report.item_scores.values())
```

---

## 2. Deliverables

### 2.1 New Source Files

| File | Purpose |
|------|---------|
| `src/vibe_check/scoring/__init__.py` | Public API exports |
| `src/vibe_check/scoring/juror.py` | `JurorScorer` wrapper (Agent → `PHQ8Report`) |
| `src/vibe_check/scoring/prompting.py` | Prompt builder + prompt versioning |
| `src/vibe_check/scoring/agent.py` | PydanticAI agent builder (providers + `TestModel`) |
| `src/vibe_check/scoring/fakes.py` | Deterministic fake jurors/judge for offline runs |
| `src/vibe_check/settings.py` | Pydantic-settings for API keys/model IDs (no secrets committed) |

### 2.2 New Test Files

| File | Purpose |
|------|---------|
| `tests/unit/test_prompting.py` | Prompt structure + PHQ-8 invariants |
| `tests/unit/test_parsing.py` | Parse/canonicalize raw model output into `PHQ8Report` |
| `tests/integration/test_juror_scorer.py` | End-to-end scoring via PydanticAI `TestModel` |
| `tests/fixtures/juror_outputs/*.json` | Golden juror outputs for deterministic tests |

### 2.3 pyproject.toml Updates

Add required dependencies:

- `pydantic-ai>=1.0.0` (SSOT: structured outputs / provider abstraction)

Optional (e2e only):

- Provider SDKs only if required by the chosen PydanticAI model adapters

Hard requirement: tests must not require network or API keys; any real-provider tests must be `@pytest.mark.e2e` and skipped by default.

---

## 3. Core Design

### 3.1 Public API

Expose a small stable surface:

- `JurorScorer.score(text: str) -> PHQ8Report`
- `JurorScorer` wraps a PydanticAI `Agent` (model selection is a config detail)
- Deterministic tests use `pydantic_ai.models.test.TestModel`

### 3.2 Prompting Requirements

The prompt must:

- Score **PHQ-8 items only**
- Include the PHQ-8 item definitions (0–3 rubric) in the prompt
- Require JSON-only output (no markdown, no prose wrapper)
- Allow `insufficient_evidence=true` per item
- Include self-harm as a **separate boolean tag** (not a PHQ-9 item)
- Use the preprocessed view text (default `client_qa_text`) and explicitly forbid using dropped preamble content

### 3.3 Parsing + Canonicalization

We rely on **PydanticAI structured outputs** (`output_type=PHQ8Assessment`) to avoid an ad-hoc JSON parsing layer.

Canonicalization rule (implemented in `PHQ8Assessment` validators):
- `total_score` is computed from the 8 item scores if missing/incorrect.

Validation failures remain strict and machine-actionable via Pydantic/PydanticAI error types.

---

## 4. Testing Strategy

### 4.1 Unit Tests (Deterministic)

- Prompt invariants: PHQ-8 only; JSON-only response instruction; includes view name/version
- Parser invariants: handles missing/incorrect totals via canonicalization

### 4.2 Integration Tests (Deterministic)

Use PydanticAI `TestModel` with golden fixture dicts and assert:

- `PHQ8Report` validates
- Evidence lists are capped at 3
- `insufficient_evidence` paths work (ties into SPEC-03 arbitration)

### 4.3 Optional E2E Tests (Off by Default)

- One test per provider, marked `e2e`, requiring API keys
- Only asserts: call succeeds + output parses into `PHQ8Report`

---

## 5. Resilience (ADR-001)

The juror scoring system implements a **three-layer resilience strategy** per ADR-001:

### 5.1 Layer 1: PydanticAI Validation Retries

```python
# agent.py
agent = Agent(
    model=model,
    output_type=PHQ8Assessment,
    retries=settings.validation_retries,  # Default: 2
)
```

Handles: Schema validation failures when the LLM produces malformed JSON.

### 5.2 Layer 2: Tenacity Transient Retry

```python
# juror.py (inside ascore)
@with_retry(
    max_attempts=settings.max_retries,       # Default: 5
    initial_wait=settings.retry_initial_wait, # Default: 1.0s
    max_wait=settings.retry_max_wait,         # Default: 60.0s
    jitter=settings.retry_jitter,             # Default: 5.0s
)
async def _call_with_retry():
    return await self._agent.run(scoring_text)
```

Handles: HTTP 429 (rate limit), 5xx errors, network timeouts, connection errors.

### 5.3 Layer 3: Aiolimiter Rate Limiting

```python
# resilience.py
class ProviderRateLimiters:
    def __init__(self, settings: Settings):
        self._openai = AsyncLimiter(settings.openai_rpm, 60.0)    # Default: 100
        self._anthropic = AsyncLimiter(settings.anthropic_rpm, 60.0)  # Default: 60
        self._google = AsyncLimiter(settings.google_rpm, 60.0)    # Default: 100
```

Handles: Proactive throttling to prevent 429 errors before they happen.

### 5.4 Wiring in Factory

`build_real_jury()` in `factory.py` wires all three layers:

```python
def build_real_jury(settings: Settings) -> Sequence[Juror]:
    rate_limiters = ProviderRateLimiters(settings)
    # ... for each provider:
    limiter = rate_limiters.get_limiter(model_id)
    agent = build_juror_agent(..., retries=settings.validation_retries)
    scorer = JurorScorer(
        agent=agent,
        rate_limiter=limiter,
        max_retries=settings.max_retries,
        # ... other retry settings
    )
```

---

## 6. Non-Goals

- Multi-agent orchestration (SPEC-05)
- Batch scoring across the full corpus (SPEC-06)
- Any attempt to "optimize" prompts based on SQPsychConv artifacts (avoid overfitting to synthetic generator leakage)
