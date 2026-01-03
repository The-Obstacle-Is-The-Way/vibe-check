# BUG-011: `datetime.utcnow()` is deprecated in Python 3.12+

**Severity**: P4 (code hygiene / future-proofing)
**Status**: RESOLVED
**Date**: 2026-01-03

---

## Summary

The codebase uses `datetime.utcnow()` which is deprecated in Python 3.12+ (PEP 587). Should use `datetime.now(UTC)` for timezone-aware datetimes.

---

## Affected Areas

- `src/vibe_check/schemas/scoring.py:145` - `scored_at` default factory
- `src/vibe_check/schemas/output.py:77` - `scored_at` default factory
- `src/vibe_check/scoring/juror.py:74` - `scored_at` assignment
- `src/vibe_check/aggregation/aggregate.py:174` - `scored_at` assignment

---

## Fix Plan

Replace all `datetime.utcnow()` with `datetime.now(UTC)`:

```python
from datetime import UTC, datetime

# Before
scored_at: datetime = Field(default_factory=datetime.utcnow)

# After
scored_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

---

## Verification

- `uv run mypy src tests` passes
- No deprecation warnings when running with Python 3.12+
