# BUG-013: Rate limiting and retries not implemented (tenacity/aiolimiter unused)

**Severity**: P2 (production readiness for live API calls)
**Status**: OPEN
**Date**: 2026-01-03

---

## Summary

SPEC-05 and SPEC-06 require:
- "bounded retries with exponential backoff" (tenacity)
- "respect provider rate limits" (aiolimiter)

Both packages are in `pyproject.toml` but neither is imported or used in the codebase. This could cause issues with real API calls:
- Rate limit errors when hitting provider limits
- Unhandled transient failures without retry logic

---

## Affected Areas

- `src/vibe_check/scoring/agent.py` - Should configure PydanticAI retries
- `src/vibe_check/run/runner.py` - Should implement rate limiting
- `src/vibe_check/run/factory.py` - Should wire up rate limiters

---

## Spec References

- **SPEC-05 Section 2.3**: "tenacity (bounded retries; no infinite loops)" + "aiolimiter (rate limiting)"
- **SPEC-06 Section 4.1**: "Must respect provider rate limits (global and per-provider)"
- **SPEC-06 Section 4.2**: "Use bounded retries with exponential backoff"

---

## Fix Plan

### Option A: Minimal (PydanticAI-native)

Check if PydanticAI has built-in retry/rate-limit config and use it:

```python
agent = Agent(
    model=model,
    retries=3,  # If supported
    ...
)
```

### Option B: Full Implementation

1. Add `aiolimiter` rate limiters per provider:
   ```python
   from aiolimiter import AsyncLimiter

   openai_limiter = AsyncLimiter(settings.openai_rpm, 60)
   ```

2. Add `tenacity` retry decorator:
   ```python
   from tenacity import retry, stop_after_attempt, wait_exponential

   @retry(stop=stop_after_attempt(3), wait=wait_exponential())
   def score(...): ...
   ```

---

## Verification

- `--live` runs respect rate limits and don't get 429 errors
- Transient failures are retried with backoff
- Tests mock the rate limiters (no network dependency)
