# SPEC-14: Clinical Inference Prompts

> **Status**: DRAFT v2 - Revised per senior review
> **Depends On**: SPEC-13 (NA-Aware Schema), clinical-alignment-review.md §12.3 (APPROVED)
> **Blocks**: Pilot scoring run, SPEC-17 (Judge)

---

## 1. Overview

This spec defines TDD requirements for rewriting juror prompts from frequency-based scoring to clinical inference mode. Tests are **deterministic** (no live LLM calls).

**Core Change**: New v2 prompt constants + prompt builder; v1 constants preserved for comparison.

---

## 2. Versioning Strategy

### 2.1 Constant Versioning

To preserve `phq8_rubric_hash()` stability and allow regression testing:

- **v1 constants**: Keep existing constants unchanged (legacy)
- **v2 constants**: Add new `_V2` suffixed constants for clinical inference

```python
# File: src/vibe_check/constants.py

# === V1 CONSTANTS (LEGACY - DO NOT MODIFY) ===
PHQ8_TIME_FRAME: str = "Over the last 2 weeks"
PHQ8_SCORE_SCALE: str = (
    "0 = Not at all\n1 = Several days\n2 = More than half the days\n3 = Nearly every day"
)

# === V2 CONSTANTS (CLINICAL INFERENCE) ===
PHQ8_TIME_FRAME_V2: str = "Recent period (~last 2 weeks), unless transcript indicates otherwise"

PHQ8_SCORE_SCALE_V2: str = """| Evidence Pattern | Score | Cues |
|-----------------|-------|------|
| Mild / intermittent, minimal impact | 1 | "sometimes", "a bit", "here and there" |
| Frequent/persistent OR moderate impact | 2 | "often", "most days", "regularly", clear disruption |
| Near-daily/persistent AND severe impact | 3 | "every day", "nearly every day", "can't function" |
| Explicit denial of symptom | 0 | "I'm sleeping fine", "my appetite is good" |
| No evidence for CLIENT+timeframe | null | not discussed / not scorable |"""

PHQ8_ASSERTION_RULES_V2: str = """- present (score 1-3): Symptom clearly described by CLIENT for current/recent timeframe
- denied (score 0): CLIENT explicitly denies symptom
- possible (score 1): Hedged/uncertain mention by CLIENT ("maybe", "I guess")
- not_mentioned (score null): No evidence for CLIENT in target timeframe"""

PHQ8_CONTEXT_RULES_V2: str = """- Experiencer: Score ONLY symptoms attributed to the CLIENT (not family/others)
- Temporality: Score current/recent symptoms ONLY (not historical/resolved)
- Hypothetical: Exclude "what if" / conditional / future statements
- Negation: Explicit denial → score=0, assertion="denied" """

PHQ8_EVIDENCE_CONSTRAINTS_V2: str = """Evidence requirements:
- Maximum 3 snippets per item
- Each snippet: ≤50 words, ≤400 characters
- Quote CLIENT language, not therapist paraphrasing
- For not_mentioned: evidence=[], confidence=null"""
```

### 2.2 Prompt Version Contract

| Version | Constants Used | Features |
|---------|----------------|----------|
| `v1.x.x` | `PHQ8_TIME_FRAME`, `PHQ8_SCORE_SCALE` | Frequency-based, `score: 0-3` only |
| `v2.x.x` | `*_V2` constants | Clinical inference, NA-aware, assertion semantics |

---

## 3. JSON Output Skeleton

### 3.1 Explicit Schema in Prompt

The prompt MUST include an explicit JSON skeleton to reduce PydanticAI retries:

```python
PHQ8_JSON_SKELETON_V2: str = """{
  "anhedonia": {"discussed": true, "score": 2, "assertion": "present", "confidence": 0.85, "evidence": ["quote"]},
  "depressed_mood": {"discussed": true, "score": 0, "assertion": "denied", "confidence": 0.90, "evidence": ["I feel fine"]},
  "sleep": {"discussed": false, "score": null, "assertion": "not_mentioned", "confidence": null, "evidence": []},
  "fatigue": {"discussed": true, "score": 1, "assertion": "possible", "confidence": 0.55, "evidence": ["maybe tired"]},
  "appetite": {"discussed": false, "score": null, "assertion": "not_mentioned", "confidence": null, "evidence": []},
  "guilt": {"discussed": true, "score": 1, "assertion": "present", "confidence": 0.70, "evidence": ["quote"]},
  "concentration": {"discussed": false, "score": null, "assertion": "not_mentioned", "confidence": null, "evidence": []},
  "psychomotor": {"discussed": false, "score": null, "assertion": "not_mentioned", "confidence": null, "evidence": []},
  "total_score": 4,
  "discussed_count": 4,
  "mentions_self_harm": false,
  "self_harm_evidence": []
}"""
```

---

## 4. Prompt Builder

### 4.1 Updated Function Signature

```python
# File: src/vibe_check/scoring/prompting.py

def build_juror_system_prompt(
    prompt_version: str,
    view_name: str = "client_qa",
    extra_instructions: str | None = None,  # PRESERVED for backward compat
) -> str:
    """Build system prompt for PHQ-8 scoring.

    Args:
        prompt_version: "v1.x.x" for legacy, "v2.x.x" for clinical inference
        view_name: Dialogue view being scored
        extra_instructions: Additional instructions to append (optional)

    Returns:
        Complete system prompt string
    """
    if prompt_version.startswith("v2"):
        return _build_v2_prompt(prompt_version, view_name, extra_instructions)
    else:
        return _build_v1_prompt(prompt_version, view_name, extra_instructions)
```

### 4.2 V2 Prompt Template

```python
def _build_v2_prompt(
    prompt_version: str,
    view_name: str,
    extra_instructions: str | None,
) -> str:
    """Build clinical inference prompt (v2)."""
    rubric_items = "\n".join(
        f"  {i}. {item}: {PHQ8_RUBRIC[item]}"
        for i, item in enumerate(PHQ8_ITEMS, 1)
    )

    base = f"""You are a psychiatrist reviewing a therapy transcript to infer PHQ-8 symptom severity.

Input: A preprocessed dialogue view named `{view_name}` from a synthetic therapy conversation.
Prompt version: {prompt_version}.

## PHQ-8 CLINICAL RUBRIC

### Target Timeframe
{PHQ8_TIME_FRAME_V2}

### Item Definitions
{rubric_items}

### Severity Inference (Evidence → Score)
{PHQ8_SCORE_SCALE_V2}

## CONTEXT RULES (ConText-style)
{PHQ8_CONTEXT_RULES_V2}

## ASSERTION SEMANTICS
{PHQ8_ASSERTION_RULES_V2}

## CRITICAL: NOT MENTIONED vs DENIED

**DENIED (score=0, assertion="denied")**:
Patient EXPLICITLY says they DON'T have the symptom.
Example: "My sleep has been fine" → sleep: score=0, assertion="denied"

**NOT MENTIONED (score=null, assertion="not_mentioned")**:
No evidence for the CLIENT in the target timeframe.
Example: Sleep never discussed → sleep: score=null, assertion="not_mentioned"

⚠️ DO NOT score 0 for items that are simply not mentioned. Score 0 means DENIED.

## EVIDENCE REQUIREMENTS
{PHQ8_EVIDENCE_CONSTRAINTS_V2}

## OUTPUT FORMAT

Return JSON matching this exact structure:
```json
{PHQ8_JSON_SKELETON_V2}
```

- `total_score`: Sum of non-null item scores (NA items contribute 0)
- `discussed_count`: Count of items where discussed=true

Return JSON ONLY. No markdown code fences, no explanatory prose.
"""
    if extra_instructions:
        return base + "\n" + extra_instructions.strip() + "\n"
    return base
```

---

## 5. TDD Test Cases (Deterministic)

All tests use **prompt string inspection** or **TestModel** with fixed outputs. No live LLM calls.

### 5.1 Prompt Structure Tests

```python
# File: tests/unit/test_prompting.py

import pytest
from vibe_check.scoring.prompting import build_juror_system_prompt
from vibe_check.constants import (
    PHQ8_TIME_FRAME, PHQ8_SCORE_SCALE,  # v1
    PHQ8_TIME_FRAME_V2, PHQ8_SCORE_SCALE_V2,  # v2
    PHQ8_CONTEXT_RULES_V2, PHQ8_ASSERTION_RULES_V2,
    PHQ8_JSON_SKELETON_V2, PHQ8_EVIDENCE_CONSTRAINTS_V2,
)


class TestV2PromptStructure:
    """V2 prompt structure tests (deterministic)."""

    def test_v2_includes_clinical_timeframe(self):
        prompt = build_juror_system_prompt("v2.0.0")
        assert PHQ8_TIME_FRAME_V2 in prompt
        # V1 timeframe should NOT appear
        assert "Over the last 2 weeks" not in prompt or "~last 2 weeks" in prompt

    def test_v2_includes_severity_table(self):
        prompt = build_juror_system_prompt("v2.0.0")
        assert "Mild / intermittent" in prompt
        assert "Frequent/persistent" in prompt
        assert "Near-daily/persistent" in prompt

    def test_v2_includes_context_rules(self):
        prompt = build_juror_system_prompt("v2.0.0")
        assert "Experiencer" in prompt
        assert "Temporality" in prompt
        assert "Hypothetical" in prompt
        assert "Negation" in prompt

    def test_v2_includes_assertion_rules(self):
        prompt = build_juror_system_prompt("v2.0.0")
        assert "not_mentioned" in prompt
        assert "denied" in prompt
        assert "possible" in prompt
        assert "present" in prompt

    def test_v2_includes_json_skeleton(self):
        prompt = build_juror_system_prompt("v2.0.0")
        # Skeleton must be present verbatim (or key parts of it)
        assert '"discussed": true' in prompt or '"discussed":true' in prompt
        assert '"assertion": "not_mentioned"' in prompt or '"assertion":"not_mentioned"' in prompt
        assert '"score": null' in prompt or '"score":null' in prompt

    def test_v2_emphasizes_na_vs_denied(self):
        prompt = build_juror_system_prompt("v2.0.0")
        assert "DO NOT score 0 for items that are simply not mentioned" in prompt

    def test_v2_includes_evidence_constraints(self):
        prompt = build_juror_system_prompt("v2.0.0")
        assert "50 words" in prompt
        assert "400 characters" in prompt
        assert "3 snippets" in prompt or "Maximum 3" in prompt

    def test_v2_no_legacy_frequency_scale_definition(self):
        """V2 should not have legacy scale as the PRIMARY definition."""
        prompt = build_juror_system_prompt("v2.0.0")
        # "Several days" can appear as a CUE, but not as "1 = Several days"
        assert "1 = Several days" not in prompt
        assert "2 = More than half the days" not in prompt

    def test_v2_allows_frequency_cues(self):
        """V2 may mention 'every day' as a severity cue."""
        prompt = build_juror_system_prompt("v2.0.0")
        # These are cues in the severity table, which is fine
        assert "every day" in prompt.lower() or "nearly every day" in prompt.lower()


class TestV1PromptStructure:
    """V1 prompt structure tests (legacy, for comparison)."""

    def test_v1_includes_legacy_timeframe(self):
        prompt = build_juror_system_prompt("v1.0.0")
        assert "Over the last 2 weeks" in prompt

    def test_v1_includes_legacy_frequency_scale(self):
        prompt = build_juror_system_prompt("v1.0.0")
        assert "Several days" in prompt
        assert "More than half the days" in prompt
        assert "Nearly every day" in prompt

    def test_v1_does_not_include_assertion_rules(self):
        prompt = build_juror_system_prompt("v1.0.0")
        assert "not_mentioned" not in prompt
        # V1 has insufficient_evidence, not assertion


class TestPromptVersionRouting:
    """Prompt version routing tests."""

    def test_v1_routing(self):
        prompt = build_juror_system_prompt("v1.0.0")
        assert "Several days" in prompt  # V1 indicator

    def test_v1_1_routing(self):
        prompt = build_juror_system_prompt("v1.1.0")
        assert "Several days" in prompt  # Still V1

    def test_v2_routing(self):
        prompt = build_juror_system_prompt("v2.0.0")
        assert "not_mentioned" in prompt  # V2 indicator

    def test_v2_1_routing(self):
        prompt = build_juror_system_prompt("v2.1.0")
        assert "not_mentioned" in prompt  # Still V2


class TestExtraInstructions:
    """extra_instructions parameter tests."""

    def test_extra_instructions_appended_v1(self):
        prompt = build_juror_system_prompt("v1.0.0", extra_instructions="CUSTOM RULE")
        assert "CUSTOM RULE" in prompt

    def test_extra_instructions_appended_v2(self):
        prompt = build_juror_system_prompt("v2.0.0", extra_instructions="CUSTOM RULE")
        assert "CUSTOM RULE" in prompt

    def test_none_extra_instructions(self):
        prompt = build_juror_system_prompt("v2.0.0", extra_instructions=None)
        assert "CUSTOM" not in prompt

    def test_empty_extra_instructions(self):
        prompt = build_juror_system_prompt("v2.0.0", extra_instructions="  ")
        # Should handle gracefully (stripped to empty)
        # Implementation detail: may or may not add newline
```

### 5.2 Schema Parse Tests (TestModel)

```python
# File: tests/unit/test_prompting_parse.py

import pytest
from pydantic_ai.models.test import TestModel
from vibe_check.schemas.scoring import PHQ8Assessment


class TestV2SchemaParsing:
    """Test that V2 schema parses correctly with fixed outputs."""

    def test_parse_full_coverage_response(self):
        """Parse a complete V2-style response."""
        raw_json = {
            "anhedonia": {"discussed": True, "score": 2, "assertion": "present",
                         "confidence": 0.85, "evidence": ["can't enjoy anything"]},
            "depressed_mood": {"discussed": True, "score": 3, "assertion": "present",
                               "confidence": 0.90, "evidence": ["feeling hopeless"]},
            "sleep": {"discussed": True, "score": 1, "assertion": "present",
                      "confidence": 0.75, "evidence": ["sometimes trouble sleeping"]},
            "fatigue": {"discussed": True, "score": 2, "assertion": "present",
                        "confidence": 0.80, "evidence": ["exhausted"]},
            "appetite": {"discussed": True, "score": 0, "assertion": "denied",
                         "confidence": 0.88, "evidence": ["eating fine"]},
            "guilt": {"discussed": True, "score": 1, "assertion": "present",
                      "confidence": 0.70, "evidence": ["feel bad sometimes"]},
            "concentration": {"discussed": True, "score": 2, "assertion": "present",
                              "confidence": 0.78, "evidence": ["can't focus"]},
            "psychomotor": {"discussed": True, "score": 0, "assertion": "denied",
                            "confidence": 0.82, "evidence": ["moving normally"]},
            "total_score": 11,
            "discussed_count": 8,
            "mentions_self_harm": False,
            "self_harm_evidence": [],
        }
        assessment = PHQ8Assessment.model_validate(raw_json)
        assert assessment.total_score == 11
        assert assessment.discussed_count == 8

    def test_parse_partial_coverage_response(self):
        """Parse a response with NA items."""
        raw_json = {
            "anhedonia": {"discussed": True, "score": 2, "assertion": "present",
                         "confidence": 0.85, "evidence": ["no interest"]},
            "depressed_mood": {"discussed": True, "score": 3, "assertion": "present",
                               "confidence": 0.90, "evidence": ["hopeless"]},
            "sleep": {"discussed": False, "score": None, "assertion": "not_mentioned",
                      "confidence": None, "evidence": []},
            "fatigue": {"discussed": True, "score": 2, "assertion": "present",
                        "confidence": 0.80, "evidence": ["tired"]},
            "appetite": {"discussed": False, "score": None, "assertion": "not_mentioned",
                         "confidence": None, "evidence": []},
            "guilt": {"discussed": False, "score": None, "assertion": "not_mentioned",
                      "confidence": None, "evidence": []},
            "concentration": {"discussed": True, "score": 1, "assertion": "possible",
                              "confidence": 0.55, "evidence": ["maybe trouble focusing"]},
            "psychomotor": {"discussed": False, "score": None, "assertion": "not_mentioned",
                            "confidence": None, "evidence": []},
            "total_score": 8,  # 2+3+2+1
            "discussed_count": 4,
            "mentions_self_harm": False,
            "self_harm_evidence": [],
        }
        assessment = PHQ8Assessment.model_validate(raw_json)
        assert assessment.total_score == 8
        assert assessment.discussed_count == 4
        assert assessment.sleep.score is None
        assert assessment.sleep.assertion == "not_mentioned"

    def test_parse_all_na_response(self):
        """Parse a response where nothing was discussed."""
        raw_json = {
            "anhedonia": {"discussed": False, "score": None, "assertion": "not_mentioned",
                         "confidence": None, "evidence": []},
            "depressed_mood": {"discussed": False, "score": None, "assertion": "not_mentioned",
                               "confidence": None, "evidence": []},
            "sleep": {"discussed": False, "score": None, "assertion": "not_mentioned",
                      "confidence": None, "evidence": []},
            "fatigue": {"discussed": False, "score": None, "assertion": "not_mentioned",
                        "confidence": None, "evidence": []},
            "appetite": {"discussed": False, "score": None, "assertion": "not_mentioned",
                         "confidence": None, "evidence": []},
            "guilt": {"discussed": False, "score": None, "assertion": "not_mentioned",
                      "confidence": None, "evidence": []},
            "concentration": {"discussed": False, "score": None, "assertion": "not_mentioned",
                              "confidence": None, "evidence": []},
            "psychomotor": {"discussed": False, "score": None, "assertion": "not_mentioned",
                            "confidence": None, "evidence": []},
            "total_score": 0,
            "discussed_count": 0,
            "mentions_self_harm": False,
            "self_harm_evidence": [],
        }
        assessment = PHQ8Assessment.model_validate(raw_json)
        assert assessment.total_score == 0
        assert assessment.discussed_count == 0


class TestV2SchemaRejection:
    """Test that invalid V2 responses are rejected."""

    def test_reject_score_0_with_present_assertion(self):
        """present assertion cannot have score=0."""
        raw_json = {
            "anhedonia": {"discussed": True, "score": 0, "assertion": "present",
                         "confidence": 0.85, "evidence": ["quote"]},
            # ... other items omitted for brevity
        }
        with pytest.raises(Exception):  # ValidationError
            PHQ8Assessment.model_validate(raw_json)

    def test_reject_score_2_with_not_mentioned(self):
        """not_mentioned must have score=None."""
        raw_json = {
            "anhedonia": {"discussed": False, "score": 2, "assertion": "not_mentioned",
                         "confidence": None, "evidence": []},
        }
        with pytest.raises(Exception):
            PHQ8Assessment.model_validate(raw_json)

    def test_reject_discussed_true_with_not_mentioned(self):
        """not_mentioned requires discussed=False."""
        raw_json = {
            "anhedonia": {"discussed": True, "score": None, "assertion": "not_mentioned",
                         "confidence": None, "evidence": []},
        }
        with pytest.raises(Exception):
            PHQ8Assessment.model_validate(raw_json)
```

---

## 6. Files Affected

| File | Change Type | Description |
|------|-------------|-------------|
| `src/vibe_check/constants.py` | **MODERATE** | Add `*_V2` constants; keep v1 unchanged |
| `src/vibe_check/scoring/prompting.py` | **MAJOR** | Add version routing; `_build_v2_prompt()` |
| `tests/unit/test_prompting.py` | **MAJOR** | All tests in Section 5 |
| `tests/unit/test_prompting_parse.py` | **NEW** | Schema parsing tests |

---

## 7. Acceptance Criteria

- [ ] All tests in Section 5.1 (prompt structure) pass
- [ ] All tests in Section 5.2 (schema parsing) pass
- [ ] V1 constants unchanged (`phq8_rubric_hash()` stable)
- [ ] V2 prompt includes JSON skeleton verbatim
- [ ] V2 prompt includes evidence constraints (50 words, 400 chars, 3 max)
- [ ] V2 prompt includes ConText rules
- [ ] `extra_instructions` parameter preserved
- [ ] `ruff check` + `mypy --strict` pass

---

## 8. Sign-Off

| Role | Status |
|------|--------|
| Author | DRAFT v2 |
| Senior Review | PENDING |
