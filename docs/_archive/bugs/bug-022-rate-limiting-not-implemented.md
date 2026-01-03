# BUG-013: Rate limiting and retries not implemented (tenacity/aiolimiter unused)

**Severity**: P2 (production readiness for live API calls)
**Status**: RESOLVED
**Date**: 2026-01-03
**Resolution**: ADR-001 - Three-layer resilience strategy

---

## Summary

SPEC-05 and SPEC-06 require:
- "bounded retries with exponential backoff" (tenacity)
- "respect provider rate limits" (aiolimiter)

Both packages were in `pyproject.toml` but neither was imported or used in the codebase.

---

## Root Cause

Dependencies were declared but implementation was deferred.

---

## Resolution

Implemented ADR-001's three-layer resilience strategy:

| Layer | Tool | Handles |
|-------|------|---------|
| 1. Validation | PydanticAI `retries=2` | Schema validation failures (malformed JSON) |
| 2. Transient | Tenacity decorator | 429 rate limits, 5xx errors, network timeouts |
| 3. Proactive | Aiolimiter | Prevent 429s by throttling requests per provider |

---

## Files Changed

- **NEW**: `src/vibe_check/resilience.py` - Rate limiters + retry decorators
- **NEW**: `docs/architecture/adr-001-rate-limiting-retries.md` - Architectural decision
- `src/vibe_check/settings.py` - Added retry configuration
- `src/vibe_check/scoring/agent.py` - Added `retries` parameter
- `src/vibe_check/scoring/juror.py` - Integrated rate limiting + retry in `ascore()`
- `src/vibe_check/graph/single_dialogue.py` - Runs jurors via async `ascore()` so Layers 2/3 are actually applied
- `src/vibe_check/sqlite.py` - Async checkpoint helper for LangGraph (`open_async_sqlite_saver`)
- `src/vibe_check/run/runner.py` - Async batch runner invokes the async graph + supports bounded concurrency
- `src/vibe_check/run/factory.py` - Wires rate limiters to jurors

---

## Configuration Added to Settings

```python
# Retry Configuration (ADR-001)
max_retries: int = 5
retry_initial_wait: float = 1.0
retry_max_wait: float = 60.0
retry_jitter: float = 5.0
validation_retries: int = 2
```

---

## Verification

- [x] `make ci` passes (ruff + mypy + pytest)
- [x] mypy strict: 0 issues
- [x] ruff: all checks passed
- [ ] Production verification pending: `--live` run with real API calls
