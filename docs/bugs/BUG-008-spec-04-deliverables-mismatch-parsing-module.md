# BUG-008: SPEC-04 deliverables mention `scoring/parsing.py`, but implementation uses PydanticAI schemas

**Severity**: P3 (documentation mismatch)
**Status**: RESOLVED
**Date**: 2026-01-03

---

## Summary

`docs/specs/SPEC-04-juror-scoring-agent.md` lists `src/vibe_check/scoring/parsing.py` as a required deliverable for robust parsing + canonicalization.

Current implementation uses PydanticAI structured outputs (`output_type=PHQ8Assessment`) and does not include a dedicated parsing module.

---

## Fix Plan

Choose one SSOT-aligned approach:

1. **Update SPEC-04** to reflect the real architecture:
   - Parsing is handled by PydanticAI + Pydantic validators (canonicalization in schema).
   - No separate `parsing.py` module required.

OR

2. Implement `scoring/parsing.py` as a thin, tested adapter around the schema for cases where provider output is not already structured.

---

## Verification

- Specs and code agree on the interface surface area for juror scoring.
- Canonicalization behavior (e.g., total score) is covered by tests.
