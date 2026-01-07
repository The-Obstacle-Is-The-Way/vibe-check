# BUG-055: LLM Output Schemas Allow Boolean Coercion in Numeric Fields

| Field | Value |
|-------|-------|
| **Severity** | P1 (High) |
| **Status** | resolved |
| **Date** | 2026-01-07 |
| **Component** | `src/vibe_check/schemas/scoring.py`, `src/vibe_check/judge/schema.py` |
| **Impact** | Silent data corruption (and confusing validation errors) when LLM returns booleans for numeric fields |

---

## Summary

Several NA-aware LLM-output schemas unintentionally accepted booleans for numeric fields due to Python/Pydantic coercion rules:

- `PHQ8ItemScore.score=True` was accepted and coerced to `1` (because `bool` is a subclass of `int`, and `Literal[0,1,2,3]` matches `True == 1`).
- `PHQ8ItemScore.confidence=True/False` was accepted and coerced to `1.0/0.0`.
- `JudgeItemResolutionNA.final_score=True` was accepted and coerced to `1`.
- `JudgeItemResolutionNA.confidence=True/False` was accepted and coerced to `1.0/0.0`.

Additionally, `PHQ8ItemScore.discussed="true"` was coerced to `True` at the item level, but `PHQ8Assessment` computed `discussed_count` from the raw input using `disc is True`, producing a misleading error: `discussed_count != computed`.

---

## Root Cause

- Python numeric tower: `bool` is a subclass of `int` (`True == 1`, `False == 0`).
- Pydantic v2 accepts/coerces booleans for `int`/`float` fields unless strictness is enforced.
- Literal constraints (`Literal[0, 1, 2, 3]`) do not inherently exclude booleans because `True` can satisfy the literal `1`.
- `PHQ8Assessment` computed-field canonicalization relied on identity checks (`is True`) against raw (pre-coercion) input.

---

## Fix

- `src/vibe_check/schemas/scoring.py`: added `mode="before"` validators on:
  - `PHQ8ItemScore.discussed` → require actual boolean type
  - `PHQ8ItemScore.score` → reject booleans explicitly
  - `PHQ8ItemScore.confidence` → reject booleans explicitly
- `src/vibe_check/judge/schema.py`: added `mode="before"` validators on:
  - `JudgeItemResolutionNA.discussed` → require actual boolean type
  - `JudgeItemResolutionNA.final_score` → reject booleans explicitly
  - `JudgeItemResolutionNA.confidence` → reject booleans explicitly

This prevents silent corruption and yields clearer schema validation errors for PydanticAI retry loops.

---

## Tests Added

- `tests/unit/test_schemas_scoring.py`: rejects `discussed="true"`, `score=True`, `confidence=True`
- `tests/unit/test_judge_schema_na.py`: rejects `discussed="true"`, `final_score=True`, `confidence=True`
