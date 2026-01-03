---
severity: P2
status: fixed
duplicate_of: BUG-006
acknowledged_date: 2026-01-02
resolution_date: 2026-01-02
---

# BUG-009: Brittle manual JSON parsing (Anti-Pattern)

## Summary
`src/vibe_check/scoring/parsing.py` implements a custom, fragile JSON extractor (`_extract_first_json_object`) and manual type checking (`_canonicalize_item`). This is a "Not Invented Here" anti-pattern that reimplements functionality provided by PydanticAI and standard libraries.

## Evidence
- `src/vibe_check/scoring/parsing.py:34`: Manual string searching for `{` and counting braces `}` to find JSON objects. This is extremely error-prone with nested objects or brace-like characters in strings.
- `src/vibe_check/scoring/parsing.py:86`: Manual type casting and validation (`int(score_raw)`, `score not in (0, 1, 2, 3)`).

## Impact
- **Silent Failures**: The parser "swallows" valid JSON if it's wrapped in unexpected text that confuses the brace counter.
- **Maintenance Burden**: We are maintaining a JSON parser.
- **Security/Stability**: Infinite loops or crashes possible with malformed inputs (though specifically guarded against here, the complexity is unwarranted).

## Fix Plan
1. Delete `_extract_first_json_object` and `parsing.py` entirely.
2. Rely on `pydantic-ai`'s built-in structured output parsing (which handles JSON extraction).
3. If "fuzzy" repair is absolutely needed, use a battle-tested library like `json_repair`, not custom string hacking.

## Resolution (2026-01-02)

**Fixed**:
- `src/vibe_check/scoring/parsing.py` has been deleted.
- Juror agents (`src/vibe_check/scoring/agent.py`) now use PydanticAI's `output_type=PHQ8Assessment` for robust, schema-driven parsing and validation.
