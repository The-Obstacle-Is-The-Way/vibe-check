# BUG-014: Judge lacks ADR-001 resilience (rate limiting, retries)

**Severity**: P2 (production readiness for live API calls)
**Status**: RESOLVED
**Date**: 2026-01-03
**Resolution**: Added Layer 1 (PydanticAI retries) and Layer 2 (Tenacity transient retry) to judge. Layer 3 (rate limiting) omitted due to sync call context and low call frequency.

---

## Summary

The juror scoring path implements ADR-001's three-layer resilience strategy:
- Layer 1: PydanticAI `retries` parameter for validation failures
- Layer 2: Tenacity `@with_retry` for transient errors (429, 5xx, network)
- Layer 3: Aiolimiter rate limiting (proactive throttling)

The judge (arbitration) path has NONE of these layers.

---

## Root Cause

In `factory.py:build_real_judge_item()`:

```python
def build_real_judge_item(settings: Settings) -> JudgeItemFn:
    full_model_name = f"anthropic:{settings.judge_model}"
    agent = build_judge_agent(model=full_model_name, prompt_version=settings.prompt_version)
    # ...
    result = agent.run_sync(prompt)  # No retries, no rate limiting
```

And in `judge/agent.py:build_judge_agent()`:

```python
return Agent(
    model=model,
    output_type=JudgeItemResolution,
    system_prompt=build_judge_system_prompt(prompt_version),
    # Missing: retries=settings.validation_retries
)
```

---

## Impact

1. **Layer 1 Missing**: Validation errors crash immediately (no retries)
2. **Layer 2 Missing**: Transient errors (429, 5xx) crash the dialogue
3. **Layer 3 Missing**: No rate limiting - can hit provider limits

If a dialogue triggers arbitration and the judge call fails, the entire scoring run fails for that dialogue with no retry opportunity.

---

## Evidence

Compare juror wiring (`factory.py:build_real_jury()`):

```python
# Layer 1: validation retries via agent
agent = build_juror_agent(..., retries=settings.validation_retries)

# Layer 2+3: transient retry + rate limiting via JurorScorer
scorer = JurorScorer(
    agent=agent,
    rate_limiter=limiter,  # Layer 3
    max_retries=settings.max_retries,  # Layer 2
    retry_initial_wait=settings.retry_initial_wait,
    # ... etc
)
```

Judge has none of this.

---

## Fix

Option A (Minimal): Add `retries` to `build_judge_agent()` and use existing retry decorator inline.

Option B (Consistent): Create a `JudgeItemScorer` class parallel to `JurorScorer` that wraps the judge agent with all three resilience layers.

Recommended: Option A (minimal) since judge calls are less frequent (only on arbitration).

---

## Acceptance Criteria

- [ ] `build_judge_agent()` accepts and uses `retries` parameter (Layer 1)
- [ ] Judge calls in `build_real_judge_item()` use `@with_retry` (Layer 2)
- [ ] Judge calls acquire rate limiter before calling (Layer 3)
- [ ] Test: judge call with mock transient error retries and succeeds
