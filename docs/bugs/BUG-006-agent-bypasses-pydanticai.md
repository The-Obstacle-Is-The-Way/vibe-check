---
severity: P2
status: fixed
acknowledged_date: 2026-01-02
resolution_date: 2026-01-02
---

# BUG-006: Juror agents bypass PydanticAI schema validation

## Summary
`src/vibe_check/scoring/agent.py` configures PydanticAI agents with `output_type=dict[str, Any]` and relies on manual parsing in `parsing.py`. This disables PydanticAI's built-in capability to catch schema errors (e.g., missing fields, wrong types) and automatically reprompt the LLM.

## Evidence
- `src/vibe_check/scoring/agent.py:27`: `output_type=dict[str, Any]`
- `src/vibe_check/scoring/parsing.py`: Extensive manual JSON extraction and validation logic (`_extract_first_json_object`, `_canonicalize_item`) that effectively re-implements PydanticAI's internal logic but without the retry loop.

## Impact
- **Brittle to hallucinations**: If an LLM returns `{ "items": { "anhedonia": { "score": 4 } } }`, the manual parser will raise a `ParseError` and the run will fail.
- **Lost functionality**: PydanticAI would have caught `score=4` (validation error), sent it back to the LLM with the error message, and likely received a corrected `score=3`. We lose this resilience.
- **Maintenance burden**: We own the parsing code (`_extract_first_json_object`) instead of the library.

## Fix Plan
1. Define a Pydantic model for the "Raw" output (unbounded totals) if necessary, or use `PHQ8Report` directly with a looser validator.
2. Update `build_juror_agent` to use `output_type=YourPydanticModel`.
3. Let PydanticAI handle the JSON parsing and retries.
4. Keep `_truncate_snippet` (Operational Hygiene) but implement it as a Pydantic validator on the model.

## Resolution (2026-01-02)

**Fixed**:
- Removed `src/vibe_check/scoring/parsing.py` and its manual JSON extraction logic.
- Updated `build_juror_agent` in `src/vibe_check/scoring/agent.py` to use `output_type=PHQ8Assessment`.
- `PHQ8Assessment` (in `src/vibe_check/schemas/scoring.py`) now enforces strict schema validation (Literal scores, matching totals).
- PydanticAI now handles the parsing and retries automatically.
