# Resilience Strategy (Implementation)

vibe-check implements a three-layer resilience strategy for live LLM API calls:

| Layer | Tool | Handles |
|-------|------|---------|
| **Layer 1** | PydanticAI `retries` | Schema validation failures (malformed JSON / wrong types) |
| **Layer 2** | Tenacity (via `with_retry`) | 429s, 5xx, network/timeouts |
| **Layer 3** | Aiolimiter (`AsyncLimiter`) | Proactive throttling per provider (RPM) |

This document describes the **actual wiring in code**. For the decision rationale, see [ADR-001](adr-001-rate-limiting-retries.md).

---

## Where Each Layer Lives

### Layer 1 (Validation Retry)

Layer 1 is configured at the agent level via PydanticAI:

- **File**: `scoring/agent.py` (`build_juror_agent()`)
- **File**: `judge/agent.py` (`build_judge_agent()`)

```python
return Agent(
    model=model,
    output_type=PHQ8Assessment,
    retries=retries,
    system_prompt=...,
)
```

### Layer 2 (Transient Retry)

Layer 2 is implemented with Tenacity:

- **File**: `resilience.py` (`with_retry()`, `_is_transient_error()`)
- **File**: `scoring/juror.py` (`JurorScorer.ascore()`)
- **File**: `run/factory.py` (`build_real_judge_item()`)

`with_retry()` is a decorator factory that wraps an **async** function with exponential backoff + jitter:

```python
@with_retry(max_attempts=5, initial_wait=1.0, max_wait=60.0, jitter=5.0)
async def _call_with_retry() -> Any:
    return await agent.run(prompt)
```

### Layer 3 (Rate Limiting)

Layer 3 is implemented with aiolimiter:

- **File**: `resilience.py` (`ProviderRateLimiters`)
- **File**: `scoring/juror.py` (`JurorScorer.ascore()`)

`ProviderRateLimiters` builds per-provider `AsyncLimiter` instances from settings:

```python
self._openai = AsyncLimiter(settings.openai_rpm, 60.0)
self._anthropic = AsyncLimiter(settings.anthropic_rpm, 60.0)
self._google = AsyncLimiter(settings.google_rpm, 60.0)
```

---

## Juror Wiring (Layers 1–3)

Jurors use all three layers:

- **Layer 1**: PydanticAI validation retries (`Agent(retries=...)`)
- **Layer 2**: Tenacity transient retries (`with_retry`)
- **Layer 3**: Provider rate limiting (`AsyncLimiter`)

**File**: `scoring/juror.py`

```python
@with_retry(max_attempts=..., initial_wait=..., max_wait=..., jitter=...)
async def _call_with_retry() -> Any:
    return await self._agent.run(scoring_text)

async with self._rate_limiter:
    result = await _call_with_retry()
```

---

## Judge Wiring (Layers 1–2)

The judge uses Layers 1–2 but intentionally omits Layer 3 rate limiting:

- Judge calls are conditional (only on contested items)
- The judge is invoked synchronously (one item at a time)

**File**: `run/factory.py` (`build_real_judge_item()`)

---

## Fake Mode (No Network)

Fake mode uses deterministic agents and a no-op limiter:

- **File**: `scoring/fakes.py` (`DeterministicFakeJuror`, `deterministic_fake_judge_item`)
- **File**: `resilience.py` (`NO_OP_LIMITER`)

The no-op limiter is an async context manager that never blocks:

```python
async with NO_OP_LIMITER:
    ...
```

---

## Configuration

Defaults come from `Settings`:

- **File**: `settings.py`

Key fields:

- `openai_rpm`, `anthropic_rpm`, `google_rpm`
- `max_retries`, `retry_initial_wait`, `retry_max_wait`, `retry_jitter`
- `validation_retries`

Env vars follow `pydantic-settings` defaults (uppercased field names), e.g. `OPENAI_RPM`, `MAX_RETRIES`, `VALIDATION_RETRIES`.
