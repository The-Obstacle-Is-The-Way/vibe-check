# SPEC-17: Judge NA Semantics

> **Status**: DRAFT - Pending Senior Review
> **Depends On**: SPEC-13 (Schema), SPEC-14 (Prompts)
> **Blocks**: End-to-end NA-aware scoring pipeline
> **Created By**: Senior review identified this as missing spec

---

## 1. Overview

The Judge agent arbitrates contested items when jurors disagree. With NA-aware scoring (SPEC-13/14), jurors can now vote `None` with assertion `not_mentioned`. The judge must handle these cases.

**Core Change**: Judge schema and prompts updated to support NA semantics.

### 1.1 Current State (v1)

```python
# Current: int-only final_score
class JudgeItemResolution(BaseModel):
    item: str
    final_score: Literal[0, 1, 2, 3]  # No None
    confidence: float
    rationale: str
```

### 1.2 Target State (v2)

```python
# New: NA-aware with assertion
class JudgeItemResolutionNA(BaseModel):
    item: str
    discussed: bool
    final_score: Literal[0, 1, 2, 3] | None
    assertion: Assertion
    confidence: float | None
    rationale: str
```

---

## 2. Design Decisions

### 2.1 When Does Judge See NA Votes?

The Judge is invoked when jurors **disagree** on an item. With NA votes, disagreement scenarios include:

| Scenario | Juror Votes | Action |
|----------|-------------|--------|
| **All numeric, spread > threshold** | `[0, 2, 1, 3, 1, 2]` | Judge arbitrates (existing) |
| **Mixed NA + numeric** | `[None, 2, None, 1, None, 2]` | Judge arbitrates (new) |
| **All NA** | `[None, None, None, None, None, None]` | **No arbitration** - unanimous NA |

### 2.2 Judge NA Decision Tree

When jurors have mixed NA + numeric votes:

1. **Majority NA (> 50%)**: Judge should **confirm NA** unless numeric evidence is compelling
2. **Minority NA (≤ 50%)**: Judge should **resolve to numeric** using clinical inference
3. **Tie (exactly 50%)**: Judge uses clinical judgment, defaults to numeric if evidence exists

### 2.3 Backward Compatibility

- **v1 schema preserved**: `JudgeItemResolution` unchanged for existing runs
- **v2 schema added**: `JudgeItemResolutionNA` for Phase 1+ runs
- **v1 prompts preserved**: Existing constants unchanged
- **v2 prompts added**: New constants with clinical inference

---

## 3. NA-Aware Judge Schema

### 3.1 Schema Definition

```python
# src/vibe_check/judge/schema.py (additions)
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from vibe_check.constants import PHQ8_ITEMS
from vibe_check.constants import MAX_EVIDENCE_SNIPPET_CHARS, MAX_EVIDENCE_SNIPPET_WORDS
from vibe_check.schemas.scoring import TokenUsage

Assertion = Literal["present", "denied", "possible", "not_mentioned"]


class JudgeItemResolutionNA(BaseModel):
    """NA-aware judge decision for a single contested PHQ-8 item.

    Follows SPEC-13 assertion/score invariants.
    """

    model_config = ConfigDict(extra="forbid")

    item: str = Field(min_length=1, description="PHQ-8 item name")
    discussed: bool = Field(description="Whether symptom was discussed in transcript")
    final_score: Literal[0, 1, 2, 3] | None = Field(
        description="Severity score (None if not_mentioned)"
    )
    assertion: Assertion = Field(description="Clinical assertion type")
    confidence: float | None = Field(
        ge=0.0, le=1.0, description="Confidence (None if not_mentioned)"
    )
    evidence: list[str] = Field(
        default_factory=list,
        max_length=3,
        description="Up to 3 supporting quotes (empty for not_mentioned)",
    )
    rationale: str = Field(min_length=1, description="Reasoning for decision")

    @model_validator(mode="after")
    def _validate_item_name(self) -> "JudgeItemResolutionNA":
        """Validate item is a valid PHQ-8 item."""
        if self.item not in PHQ8_ITEMS:
            raise ValueError(f"item must be one of {PHQ8_ITEMS}, got {self.item!r}")
        return self

    @model_validator(mode="after")
    def _validate_assertion_consistency(self) -> "JudgeItemResolutionNA":
        """Enforce SPEC-13 assertion/score/discussed invariants."""
        if self.assertion == "not_mentioned":
            if self.discussed is not False:
                raise ValueError("not_mentioned requires discussed=False")
            if self.final_score is not None:
                raise ValueError("not_mentioned requires final_score=None")
            if self.confidence is not None:
                raise ValueError("not_mentioned requires confidence=None")
            if self.evidence:
                raise ValueError("not_mentioned requires evidence=[]")
        else:
            # present, denied, possible all require discussed=True
            if self.discussed is not True:
                raise ValueError(f"{self.assertion} requires discussed=True")
            if self.final_score is None:
                raise ValueError(f"{self.assertion} requires final_score != None")
            if self.confidence is None:
                raise ValueError(f"{self.assertion} requires confidence != None")
            if not self.evidence:
                raise ValueError(f"{self.assertion} requires at least one evidence snippet")

            # Assertion-specific score constraints
            if self.assertion == "denied" and self.final_score != 0:
                raise ValueError("denied requires final_score=0")
            if self.assertion == "present" and self.final_score not in (1, 2, 3):
                raise ValueError("present requires final_score in {1, 2, 3}")
            if self.assertion == "possible" and self.final_score != 1:
                raise ValueError("possible requires final_score=1 (SSOT Q4 answer)")

        return self


class JudgeItemReportNA(JudgeItemResolutionNA):
    """NA-aware judge decision plus token usage metadata."""

    usage: TokenUsage | None = None
```

---

## 4. NA-Aware Judge Prompts

### 4.1 Constants (v2)

```python
# src/vibe_check/constants.py (additions)

JUDGE_ASSERTION_GUIDANCE_V2: str = """
ASSERTION TYPES
===============

When resolving contested items, you must determine the appropriate assertion:

- **present**: Client clearly indicates experiencing the symptom with severity > 0
  → Score must be 1, 2, or 3

- **denied**: Client explicitly denies or negates the symptom
  → Score must be 0

- **possible**: Symptom domain is clearly referenced, but severity/intensity is hedged/uncertain
  → Default to score=1 (low severity)

- **not_mentioned**: Symptom was never discussed in the transcript
  → Score must be null (no score assigned)
  → ONLY use if the symptom domain is not referenced at all for the CLIENT+timeframe
"""

JUDGE_NA_HANDLING_V2: str = """
HANDLING NA VOTES
=================

When jurors have voted "not_mentioned" (None) for some votes:

1. If ALL jurors voted not_mentioned → confirm not_mentioned
2. If MAJORITY (> 50%) voted not_mentioned but some provided numeric scores:
   - Review the evidence from numeric jurors carefully
   - If evidence is compelling and clearly references the symptom → override to numeric
   - If evidence is weak or tangential → confirm not_mentioned
3. If MINORITY (≤ 50%) voted not_mentioned:
   - Default to numeric resolution using evidence from other jurors
   - Only confirm not_mentioned if numeric evidence is clearly mistaken

CRITICAL: "Not mentioned" means the symptom was NEVER discussed. If there's ANY
evidence of the symptom being mentioned (even to deny it), it was discussed.
"""

JUDGE_JSON_SKELETON_V2: str = """{
  "item": "anhedonia",
  "discussed": true,
  "final_score": 2,
  "assertion": "present",
  "confidence": 0.85,
  "evidence": ["Client: I can't enjoy anything anymore."],
  "rationale": "Client explicitly describes loss of interest and impairment."
}"""
```

### 4.2 Prompt Builder (v2)

```python
# src/vibe_check/judge/prompting.py (additions)

from vibe_check.constants import (
    JUDGE_ASSERTION_GUIDANCE_V2,
    JUDGE_JSON_SKELETON_V2,
    JUDGE_NA_HANDLING_V2,
    PHQ8_ITEMS,
    PHQ8_RUBRIC,
    PHQ8_TIME_FRAME_V2,
    MAX_EVIDENCE_SNIPPET_CHARS,
    MAX_EVIDENCE_SNIPPET_WORDS,
)


def build_judge_system_prompt_v2(prompt_version: str) -> str:
    """Build NA-aware judge system prompt.

    Uses v2 constants with clinical inference (no frequency anchors).
    """
    rubric_items = "\n".join(f'  - {item}: "{PHQ8_RUBRIC[item]}"' for item in PHQ8_ITEMS)

    return f"""You are an expert judge resolving contested PHQ-8 item scores.
Prompt version: {prompt_version}.

PHQ-8 CLINICAL RUBRIC
=====================

Time frame: {PHQ8_TIME_FRAME_V2}

Scoring: Infer severity (0-3) from clinical context, not literal frequency words.

Item definitions:
{rubric_items}

{JUDGE_ASSERTION_GUIDANCE_V2}

{JUDGE_NA_HANDLING_V2}

ARBITRATION CRITERIA
====================

When jurors disagree on a score:
1. Review ALL juror evidence against the EXACT item definition
2. Determine the appropriate assertion type first
3. If assertion is present/denied/possible: assign severity score
4. If assertion is not_mentioned: set score to null
5. Higher confidence when evidence is consistent; lower when contradictory

EVIDENCE CONSTRAINTS
====================
- Provide up to 3 evidence snippets.
- Each snippet must be <= {MAX_EVIDENCE_SNIPPET_WORDS} words and <= {MAX_EVIDENCE_SNIPPET_CHARS} characters.
- Evidence must quote CLIENT language (not therapist paraphrasing).
- For not_mentioned: evidence must be [] and confidence must be null.

Return JSON ONLY. No markdown, no code fences, no prose.

JSON SKELETON:
{JUDGE_JSON_SKELETON_V2}
"""


def build_judge_item_prompt_v2(
    *,
    scoring_text: str,
    item: str,
    juror_votes: list[int | None],
    juror_assertions: list[Assertion],
    juror_evidence: list[str],
) -> str:
    """Build NA-aware judge item prompt.

    Args:
        scoring_text: The dialogue transcript being scored.
        item: PHQ-8 item name.
        juror_votes: Juror scores (int 0-3 or None).
        juror_assertions: Juror assertion types.
        juror_evidence: Evidence snippets from jurors (may be empty for NA).
    """
    if item not in PHQ8_ITEMS:
        raise ValueError(f"Unknown PHQ-8 item: {item!r}")

    item_definition = PHQ8_RUBRIC[item]

    # Format votes showing NA explicitly
    formatted_votes = [str(v) if v is not None else "not_mentioned" for v in juror_votes]

    # Count NA vs numeric
    na_count = sum(1 for v in juror_votes if v is None)
    numeric_count = len(juror_votes) - na_count
    na_pct = na_count / len(juror_votes) * 100 if juror_votes else 0

    # Evidence block (may be empty if all NA)
    if juror_evidence:
        evidence_block = "\n".join(f"- {e}" for e in juror_evidence[:5])
    else:
        evidence_block = "(No evidence provided - all jurors voted not_mentioned)"

    return f"""Contested item: {item}
Item definition: "{item_definition}"

Juror votes: {formatted_votes}
Juror assertions: {juror_assertions}
Vote breakdown: {numeric_count} numeric, {na_count} not_mentioned ({na_pct:.0f}% NA)

Juror evidence snippets:
{evidence_block}

Dialogue (view text):
{scoring_text}

Based on the transcript and juror evidence:
1. Determine if this symptom was discussed (discussed=true/false)
2. If discussed: assign assertion (present/denied/possible) and score (0-3)
3. If NOT discussed: assertion=not_mentioned, score=null

Respond with JSON only:
{{"item": "{item}", "discussed": true/false, "final_score": 0-3 or null, "assertion": "...", "confidence": 0.0-1.0 or null, "evidence": ["..."], "rationale": "..."}}
"""
```

---

## 5. TDD Test Cases

### 5.1 Schema Validation Tests

```python
# tests/unit/test_judge_schema_na.py
import pytest
from pydantic import ValidationError

from vibe_check.constants import PHQ8_ITEMS
from vibe_check.judge.schema import JudgeItemResolutionNA


class TestJudgeItemResolutionNA:
    """Test NA-aware judge schema validation."""

    def test_valid_present_resolution(self):
        """present assertion with score 1-3 is valid."""
        resolution = JudgeItemResolutionNA(
            item="anhedonia",
            discussed=True,
            final_score=2,
            assertion="present",
            confidence=0.85,
            evidence=["Client: I can't enjoy anything."],
            rationale="Client clearly states loss of interest in activities.",
        )
        assert resolution.final_score == 2
        assert resolution.assertion == "present"

    def test_valid_denied_resolution(self):
        """denied assertion with score 0 is valid."""
        resolution = JudgeItemResolutionNA(
            item="guilt",
            discussed=True,
            final_score=0,
            assertion="denied",
            confidence=0.9,
            evidence=["Client: I don't blame myself."],
            rationale="Client explicitly denies feeling guilty.",
        )
        assert resolution.final_score == 0
        assert resolution.assertion == "denied"

    def test_valid_possible_resolution(self):
        """possible assertion defaults to score=1 (SSOT Q4)."""
        resolution = JudgeItemResolutionNA(
            item="sleep",
            discussed=True,
            final_score=1,
            assertion="possible",
            confidence=0.6,
            evidence=["Client: Maybe I've been sleeping a bit worse."],
            rationale="Evidence is ambiguous but suggests mild sleep issues.",
        )
        assert resolution.final_score == 1
        assert resolution.assertion == "possible"

    def test_valid_not_mentioned_resolution(self):
        """not_mentioned assertion with null score is valid."""
        resolution = JudgeItemResolutionNA(
            item="psychomotor",
            discussed=False,
            final_score=None,
            assertion="not_mentioned",
            confidence=None,
            evidence=[],
            rationale="Symptom never discussed in transcript.",
        )
        assert resolution.final_score is None
        assert resolution.discussed is False

    def test_present_requires_score_1_to_3(self):
        """present with score=0 raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            JudgeItemResolutionNA(
                item="anhedonia",
                discussed=True,
                final_score=0,  # WRONG: present needs 1-3
                assertion="present",
                confidence=0.8,
                evidence=["Client: ..."],
                rationale="...",
            )
        assert "present requires final_score in {1, 2, 3}" in str(exc_info.value)

    def test_denied_requires_score_0(self):
        """denied with score!=0 raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            JudgeItemResolutionNA(
                item="guilt",
                discussed=True,
                final_score=2,  # WRONG: denied needs 0
                assertion="denied",
                confidence=0.8,
                evidence=["Client: ..."],
                rationale="...",
            )
        assert "denied requires final_score=0" in str(exc_info.value)

    def test_possible_requires_score_1(self):
        """possible with score!=1 raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            JudgeItemResolutionNA(
                item="sleep",
                discussed=True,
                final_score=2,  # WRONG: possible must be 1
                assertion="possible",
                confidence=0.8,
                evidence=["Client: ..."],
                rationale="...",
            )
        assert "possible requires final_score=1" in str(exc_info.value)

    def test_not_mentioned_requires_discussed_false(self):
        """not_mentioned with discussed=True raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            JudgeItemResolutionNA(
                item="psychomotor",
                discussed=True,  # WRONG: not_mentioned needs False
                final_score=None,
                assertion="not_mentioned",
                confidence=None,
                evidence=[],
                rationale="...",
            )
        assert "not_mentioned requires discussed=False" in str(exc_info.value)

    def test_not_mentioned_requires_score_none(self):
        """not_mentioned with numeric score raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            JudgeItemResolutionNA(
                item="psychomotor",
                discussed=False,
                final_score=0,  # WRONG: not_mentioned needs None
                assertion="not_mentioned",
                confidence=None,
                evidence=[],
                rationale="...",
            )
        assert "not_mentioned requires final_score=None" in str(exc_info.value)

    def test_not_mentioned_requires_confidence_none(self):
        """not_mentioned with numeric confidence raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            JudgeItemResolutionNA(
                item="psychomotor",
                discussed=False,
                final_score=None,
                assertion="not_mentioned",
                confidence=0.5,  # WRONG: not_mentioned needs None
                evidence=[],
                rationale="...",
            )
        assert "not_mentioned requires confidence=None" in str(exc_info.value)

    def test_not_mentioned_requires_empty_evidence(self):
        """not_mentioned must not include evidence."""
        with pytest.raises(ValidationError) as exc_info:
            JudgeItemResolutionNA(
                item="psychomotor",
                discussed=False,
                final_score=None,
                assertion="not_mentioned",
                confidence=None,
                evidence=["Client: ..."],  # WRONG
                rationale="...",
            )
        assert "not_mentioned requires evidence=[]" in str(exc_info.value)

    def test_invalid_item_name(self):
        """Invalid item name raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            JudgeItemResolutionNA(
                item="invalid_symptom",
                discussed=True,
                final_score=1,
                assertion="present",
                confidence=0.8,
                rationale="...",
            )
        assert "must be one of" in str(exc_info.value)

    def test_all_valid_items_accepted(self):
        """All PHQ8_ITEMS are accepted as valid item names."""
        for item in PHQ8_ITEMS:
            resolution = JudgeItemResolutionNA(
                item=item,
                discussed=True,
                final_score=1,
                assertion="present",
                confidence=0.8,
                evidence=["Client: test"],
                rationale=f"Test for {item}",
            )
            assert resolution.item == item
```

### 5.2 Prompt Tests

```python
# tests/unit/test_judge_prompts_na.py
import pytest

from vibe_check.constants import (
    JUDGE_ASSERTION_GUIDANCE_V2,
    JUDGE_JSON_SKELETON_V2,
    JUDGE_NA_HANDLING_V2,
    PHQ8_ITEMS,
    PHQ8_RUBRIC,
)
from vibe_check.judge.prompting import (
    build_judge_item_prompt_v2,
    build_judge_system_prompt_v2,
)


class TestBuildJudgeSystemPromptV2:
    """Test NA-aware judge system prompt builder."""

    def test_contains_version_string(self):
        """System prompt includes version string."""
        prompt = build_judge_system_prompt_v2("v2.0.0-clinical")
        assert "v2.0.0-clinical" in prompt

    def test_contains_all_phq8_items(self):
        """System prompt includes all PHQ-8 item definitions."""
        prompt = build_judge_system_prompt_v2("v2.0.0")
        for item in PHQ8_ITEMS:
            assert item in prompt
            assert PHQ8_RUBRIC[item] in prompt

    def test_contains_assertion_guidance(self):
        """System prompt includes assertion type guidance."""
        prompt = build_judge_system_prompt_v2("v2.0.0")
        assert "present" in prompt
        assert "denied" in prompt
        assert "possible" in prompt
        assert "not_mentioned" in prompt

    def test_contains_na_handling_guidance(self):
        """System prompt includes NA vote handling guidance."""
        prompt = build_judge_system_prompt_v2("v2.0.0")
        assert "MAJORITY" in prompt or "majority" in prompt
        assert "MINORITY" in prompt or "minority" in prompt

    def test_contains_json_skeleton(self):
        """System prompt includes JSON response skeleton."""
        prompt = build_judge_system_prompt_v2("v2.0.0")
        assert '"discussed"' in prompt
        assert '"assertion"' in prompt
        assert '"evidence"' in prompt

    def test_no_frequency_anchors(self):
        """v2 prompt avoids frequency-based scoring language."""
        prompt = build_judge_system_prompt_v2("v2.0.0")
        # Should NOT contain v1 frequency anchors
        assert "Several days" not in prompt
        assert "More than half the days" not in prompt
        assert "Nearly every day" not in prompt


class TestBuildJudgeItemPromptV2:
    """Test NA-aware judge item prompt builder."""

    def test_valid_item_accepted(self):
        """Valid PHQ-8 item generates prompt."""
        prompt = build_judge_item_prompt_v2(
            scoring_text="Test transcript",
            item="anhedonia",
            juror_votes=[2, 2, 1, None, 2, 1],
            juror_assertions=["present", "present", "present", "not_mentioned", "present", "present"],
            juror_evidence=["Evidence 1", "Evidence 2"],
        )
        assert "anhedonia" in prompt
        assert "Test transcript" in prompt

    def test_invalid_item_raises_error(self):
        """Invalid item name raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            build_judge_item_prompt_v2(
                scoring_text="Test",
                item="invalid_item",
                juror_votes=[1, 2],
                juror_assertions=["present", "present"],
                juror_evidence=[],
            )
        assert "Unknown PHQ-8 item" in str(exc_info.value)

    def test_na_votes_displayed_as_not_mentioned(self):
        """None votes display as 'not_mentioned' in prompt."""
        prompt = build_judge_item_prompt_v2(
            scoring_text="Test",
            item="fatigue",
            juror_votes=[None, 2, None, 1],
            juror_assertions=["not_mentioned", "present", "not_mentioned", "present"],
            juror_evidence=["Some evidence"],
        )
        assert "not_mentioned" in prompt

    def test_vote_breakdown_calculated(self):
        """Prompt includes NA vs numeric vote breakdown."""
        prompt = build_judge_item_prompt_v2(
            scoring_text="Test",
            item="sleep",
            juror_votes=[None, None, None, 1, 2, None],  # 4 NA, 2 numeric
            juror_assertions=["not_mentioned"] * 4 + ["present", "present"],
            juror_evidence=["Evidence from numeric jurors"],
        )
        assert "2 numeric" in prompt
        assert "4 not_mentioned" in prompt

    def test_empty_evidence_handled(self):
        """All-NA votes with no evidence handled gracefully."""
        prompt = build_judge_item_prompt_v2(
            scoring_text="Test",
            item="psychomotor",
            juror_votes=[None, None, None, None, None, None],
            juror_assertions=["not_mentioned"] * 6,
            juror_evidence=[],  # No evidence when all NA
        )
        assert "No evidence provided" in prompt

    def test_includes_item_definition(self):
        """Prompt includes v2 item definition."""
        prompt = build_judge_item_prompt_v2(
            scoring_text="Test",
            item="concentration",
            juror_votes=[1, 2, 1],
            juror_assertions=["present", "present", "present"],
            juror_evidence=["Hard to focus"],
        )
        assert PHQ8_RUBRIC["concentration"] in prompt
```

### 5.3 Integration Tests

```python
# tests/unit/test_judge_na_integration.py
"""Test judge agent with NA-aware schema."""

import pytest
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel

from vibe_check.judge.prompting import build_judge_system_prompt_v2
from vibe_check.judge.schema import JudgeItemResolutionNA


class TestJudgeAgentNA:
    """Test judge agent produces valid NA-aware output."""

    @pytest.fixture
    def judge_agent(self) -> Agent[None, JudgeItemResolutionNA]:
        """Create judge agent with TestModel for deterministic testing."""
        output = {
            "item": "anhedonia",
            "discussed": True,
            "final_score": 2,
            "assertion": "present",
            "confidence": 0.85,
            "evidence": ["Client: I can't enjoy anything."],
            "rationale": "Deterministic test output.",
        }
        return Agent(
            model=TestModel(custom_output_args=output),
            output_type=JudgeItemResolutionNA,
            system_prompt=build_judge_system_prompt_v2("v2.0.0-test"),
        )

    def test_agent_parses_present_resolution(self, judge_agent):
        """Agent can parse present resolution from TestModel."""
        # TestModel returns structured output matching result_type
        result = judge_agent.run_sync(
            "Resolve this item: anhedonia with votes [2, 2, 1]"
        )
        # TestModel produces valid schema output
        assert isinstance(result.data, JudgeItemResolutionNA)

    def test_schema_validates_test_model_output(self):
        """JudgeItemResolutionNA validates correctly structured data."""
        # Simulate what TestModel would produce
        valid_data = {
            "item": "anhedonia",
            "discussed": True,
            "final_score": 2,
            "assertion": "present",
            "confidence": 0.85,
            "evidence": ["Client: ..."],
            "rationale": "TestModel rationale",
        }
        resolution = JudgeItemResolutionNA.model_validate(valid_data)
        assert resolution.item == "anhedonia"
        assert resolution.final_score == 2
```

---

## 6. Integration with Aggregation (SPEC-15)

The Judge is invoked only for items that the aggregation layer flags as `needs_arbitration=True` (see SPEC-15). The Judge prompt/schema must be able to handle:

- unanimous NA (should not be arbitrated by default)
- mixed NA + numeric (when arbitration is triggered)
- numeric disagreement (existing)

---

## 7. Files Affected

| File | Change Type |
|------|-------------|
| `src/vibe_check/judge/schema.py` | **EXTEND** - Add `JudgeItemResolutionNA` |
| `src/vibe_check/judge/prompting.py` | **EXTEND** - Add v2 prompt builders |
| `src/vibe_check/constants.py` | **EXTEND** - Add judge v2 constants |
| `tests/unit/test_judge_schema_na.py` | **NEW** |
| `tests/unit/test_judge_prompts_na.py` | **NEW** |
| `tests/unit/test_judge_na_integration.py` | **NEW** |

---

## 8. Acceptance Criteria

- [ ] All test cases in Section 5 pass
- [ ] v1 `JudgeItemResolution` schema unchanged
- [ ] v2 `JudgeItemResolutionNA` enforces SPEC-13 invariants
- [ ] v2 prompts include assertion guidance
- [ ] v2 prompts include NA vote handling guidance
- [ ] Mixed NA + numeric votes trigger arbitration
- [ ] Unanimous NA votes do NOT trigger arbitration
- [ ] Ruff + mypy pass

---

## 9. Sign-Off

| Role | Status |
|------|--------|
| Author | DRAFT |
| Senior Review | PENDING |
