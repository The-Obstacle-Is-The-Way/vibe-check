---
severity: P3
status: resolved
opened_date: 2026-01-03
resolved_date: 2026-01-04
---

# BUG-036: JudgeItemResolution.item Not Validated Against PHQ8_ITEMS

## Summary

The `JudgeItemResolution` schema validates that `item` is a non-empty string, but does not validate that it matches one of the 8 valid PHQ-8 item names. If the LLM hallucinates a different item name, it would be stored in the output.

## Evidence

In `src/vibe_check/judge/schema.py:17`:

```python
class JudgeItemResolution(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item: str = Field(min_length=1)  # Only validates non-empty, not membership in PHQ8_ITEMS
    final_score: Literal[0, 1, 2, 3]
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str = Field(min_length=1)
```

Compare to the prompt in `src/vibe_check/judge/prompting.py:28-38`:

```python
return f"""Contested item: {item}
...
Respond with JSON:
{{"item": "{item}", "final_score": 0, "confidence": 0.0, "rationale": "..."}}
"""
```

The prompt tells the LLM what item to return, but doesn't enforce it. An adversarial or confused LLM could return:

```json
{"item": "anxiety", "final_score": 2, "confidence": 0.8, "rationale": "..."}
```

## Impact

In `src/vibe_check/graph/single_dialogue.py:138`:

```python
"judge_resolution": {k: v.model_dump() for k, v in resolutions.items()},
```

- The dict key `k` is always valid (from our `contested` list)
- But `v.model_dump()["item"]` could be the LLM's hallucinated value
- This creates a mismatch: `judge_resolution["anhedonia"]["item"] = "anxiety"`

The `final_score` is correctly applied (using `k`), but the serialized `judge_resolution` contains misleading data.

## Root Cause

Schema validation doesn't enforce `item ∈ PHQ8_ITEMS`.

## Proposed Fix

Add a validator to `JudgeItemResolution`:

```python
from vibe_check.constants import PHQ8_ITEMS

class JudgeItemResolution(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item: str = Field(min_length=1)
    final_score: Literal[0, 1, 2, 3]
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str = Field(min_length=1)

    @field_validator("item")
    @classmethod
    def _validate_item_name(cls, v: str) -> str:
        if v not in PHQ8_ITEMS:
            raise ValueError(f"item must be one of {PHQ8_ITEMS}, got {v!r}")
        return v
```

This leverages PydanticAI's validation retry (Layer 1) to re-prompt the LLM if it returns an invalid item name.

## Verification

- [ ] Add test with mocked LLM returning invalid item name
- [ ] Verify PydanticAI retries on validation failure
- [ ] Run full test suite
