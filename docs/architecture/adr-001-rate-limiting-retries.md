# ADR-001: Rate Limiting and Retry Strategy for LLM API Calls

**Status**: ACCEPTED
**Date**: 2026-01-03
**Context**: BUG-013 - Rate limiting and retries not implemented

---

## Decision

Implement a **three-layer resilience strategy** combining:

1. **PydanticAI native retries** - For structured output validation failures
2. **Tenacity decorators** - For transient API failures (429, 5xx, network issues)
3. **Aiolimiter rate limiters** - For proactive rate limiting per provider

---

## Context

### Problem

The codebase declares `tenacity>=9.1.2` and `aiolimiter>=1.2.1` as dependencies but neither is used. SPEC-vibe-check Section 16 requires:

> "API rate limits: `aiolimiter` + exponential backoff with jitter + global semaphore"

Production LLM API calls fail 15-30% of the time due to rate limits, network issues, and transient failures. Without retry logic, a single 429 error aborts the entire scoring run.

### Provider Rate Limits (January 2026)

| Provider | Default RPM | Token Bucket? | Retry-After Header? |
|----------|-------------|---------------|---------------------|
| OpenAI | 100 | No (fixed windows) | Yes |
| Anthropic | 60 | Yes (continuous replenishment) | Yes |
| Google | 100 | No | Sometimes |

### Requirements from Spec

- SPEC Section 4.5: "Tenacity decorators on individual functions"
- SPEC Section 12: Settings include `openai_rpm`, `anthropic_rpm`, `google_rpm`
- SPEC Section 16: "aiolimiter + exponential backoff with jitter"

---

## Options Considered

### Option A: PydanticAI Native Retries Only

**Approach**: Set `Agent(retries=3)` and rely on PydanticAI's built-in retry.

**Pros**:
- Simplest implementation (one line change)
- Framework handles all retry logic internally

**Cons**:
- ❌ No rate limiting (still get 429s)
- ❌ Only retries on validation errors, not transient API failures
- ❌ No control over backoff strategy
- ❌ No per-provider configuration

**Decision**: NOT SUFFICIENT for production.

### Option B: Tenacity + Aiolimiter Only (Replace PydanticAI Retries)

**Approach**: Wrap all agent calls with tenacity decorators and aiolimiter.

**Pros**:
- Full control over retry and rate limit behavior
- Industry standard approach for 2026 LLM pipelines
- Per-provider configuration

**Cons**:
- ⚠️ May duplicate retry logic with PydanticAI's internal retries
- More code to maintain
- Need to handle ModelRetry exception correctly

**Decision**: Viable but may cause double-retry issues.

### Option C: Hybrid Three-Layer Strategy (SELECTED)

**Approach**: Use each tool for what it does best:

| Layer | Tool | Handles |
|-------|------|---------|
| 1. Validation | PydanticAI `retries=2` | Schema validation failures (malformed JSON) |
| 2. Transient | Tenacity decorator | 429 rate limits, 5xx errors, network timeouts |
| 3. Proactive | Aiolimiter | Prevent 429s by throttling requests |

**Pros**:
- ✅ Each layer handles different failure modes
- ✅ Follows 2026 best practices (Tenacity 8.3+ with AI-optimized jitter)
- ✅ Respects existing spec architecture
- ✅ Per-provider rate limiters as specified
- ✅ Uses dependencies already declared in pyproject.toml

**Cons**:
- More complex than single-layer approach
- Need to coordinate between layers

**Decision**: SELECTED - Best balance of robustness and maintainability.

---

## Implementation

### Layer 1: PydanticAI Validation Retries

```python
# agent.py
agent = Agent(
    model=model,
    output_type=PHQ8Assessment,
    retries=2,  # Retry on schema validation failures
    ...
)
```

### Layer 2: Tenacity Transient Retry

```python
# resilience.py
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential_jitter,
    retry_if_exception_type,
)
from httpx import HTTPStatusError, NetworkError

TRANSIENT_ERRORS = (HTTPStatusError, NetworkError, TimeoutError)

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential_jitter(initial=1, max=60, jitter=5),
    retry=retry_if_exception_type(TRANSIENT_ERRORS),
    reraise=True,
)
async def call_with_retry(fn, *args, **kwargs):
    return await fn(*args, **kwargs)
```

### Layer 3: Aiolimiter Rate Limiting

```python
# resilience.py
from aiolimiter import AsyncLimiter

class ProviderRateLimiters:
    def __init__(self, settings: Settings):
        self.openai = AsyncLimiter(settings.openai_rpm, 60.0)
        self.anthropic = AsyncLimiter(settings.anthropic_rpm, 60.0)
        self.google = AsyncLimiter(settings.google_rpm, 60.0)

    def get_limiter(self, model_id: str) -> AsyncLimiter:
        if "gpt" in model_id.lower() or model_id.startswith("openai:"):
            return self.openai
        elif "claude" in model_id.lower() or model_id.startswith("anthropic:"):
            return self.anthropic
        elif "gemini" in model_id.lower() or model_id.startswith("google"):
            return self.google
        raise ValueError(f"Unknown provider for model: {model_id}")
```

### Wiring in JurorScorer

```python
# juror.py
async def ascore(self, scoring_text: str) -> PHQ8Report:
    # Layer 3: Rate limiting (proactive)
    async with self._rate_limiter:
        # Layer 2: Transient retry (reactive)
        @retry(...)
        async def _call():
            # Layer 1: PydanticAI validation retry (internal)
            return await self._agent.run(scoring_text)

        result = await _call()
    ...
```

---

## Configuration Additions

Add to `Settings`:

```python
# Retry configuration (tenacity)
max_retries: int = 5
retry_initial_wait: float = 1.0
retry_max_wait: float = 60.0
retry_jitter: float = 5.0

# Validation retries (PydanticAI)
validation_retries: int = 2
```

---

## Verification

1. **Unit tests**: Mock rate limiter, verify backoff timing
2. **Integration tests**: Simulate 429 responses, verify retry behavior
3. **Smoke test**: `--live` run respects rate limits without 429 errors

---

## References

- [OpenAI Rate Limits Cookbook](https://cookbook.openai.com/examples/how_to_handle_rate_limits)
- [PydanticAI Retry Strategies](https://ai.pydantic.dev/evals/how-to/retry-strategies/)
- [Tenacity 8.3+ Documentation](https://tenacity.readthedocs.io/)
- [SPEC-vibe-check Section 4.5, 12, 16](../research/spec-vibe-check.md)

---

## Changelog

| Date | Change |
|------|--------|
| 2026-01-03 | Initial decision - adopted hybrid three-layer strategy |
