# SPEC-14: Clinical Inference Prompts

> **Status**: DRAFT - Pending Senior Review
> **Depends On**: SPEC-13 (NA-Aware Schema), clinical-alignment-review.md (APPROVED)
> **Blocks**: Pilot scoring run

---

## 1. Overview

This spec defines TDD requirements for rewriting juror prompts from frequency-based scoring to clinical inference mode.

**Core Change**: Prompts no longer expect explicit PHQ-8 frequency anchors ("several days", "more than half"). Instead, they guide jurors to infer severity from intensity, persistence, and functional impact.

---

## 2. Current Prompt (to be replaced)

```
Scoring scale (0-3 based on frequency):
0 = Not at all
1 = Several days
2 = More than half the days
3 = Nearly every day
```

**Problem**: Transcripts don't contain explicit frequency language.

---

## 3. New Prompt Structure

### 3.1 System Prompt Template

```markdown
You are a psychiatrist reviewing a therapy transcript to infer PHQ-8 symptom severity.

## TARGET TIMEFRAME
Infer the client's symptom burden over the recent period (~last 2 weeks), unless the
transcript clearly anchors a different timeframe. Do NOT expect explicit "in the last
two weeks" language.

## CONTEXT RULES (ConText-style)
- **Experiencer**: Score symptoms only if attributed to the CLIENT (not family/others)
- **Temporality**: Prefer current/recent symptoms; exclude purely historical mentions
- **Hypothetical/conditional**: Do not treat "what if / if it happens" as current symptoms
- **Negation**: Explicit denial counts as evidence for score 0

## SEVERITY INFERENCE (Evidence → Score)
Prefer explicit frequency cues when present ("every day", "most nights"). Otherwise,
approximate using persistence + intensity + functional impact.

| Evidence Pattern | Score | Cues |
|-----------------|-------|------|
| Mild / intermittent, minimal impact | 1 | "sometimes", "a bit", "here and there" |
| Frequent/persistent OR moderate impact | 2 | "often", "most days", clear disruption |
| Near-daily/persistent AND severe impact | 3 | "every day", "can't function", pervasive |
| Explicit denial of symptom | 0 | "I'm sleeping fine", "appetite is good" |
| No evidence for CLIENT+timeframe | null | not discussed / not scorable |

## CRITICAL: NOT DISCUSSED vs DENIED
- **DENIED (score=0)**: Patient explicitly says they DON'T have the symptom
  Example: "My sleep has been fine" → sleep: score=0, assertion="denied"

- **NOT MENTIONED (score=null)**: No evidence for the CLIENT in the target timeframe
  Example: Sleep never discussed → sleep: score=null, assertion="not_mentioned"

DO NOT score 0 for items that are simply not mentioned. Score 0 means DENIED.

## EVIDENCE REQUIREMENTS
- `present` (scores 1-3): Quote client language supporting the inference
- `denied` (score 0): Quote the denial statement
- `possible` (score 1): Quote the hedged/uncertain statement
- `not_mentioned` (score=null): Leave evidence empty, confidence=null

## OUTPUT FORMAT
Return JSON matching the PHQ8Assessment schema. No markdown, no code fences.
```

### 3.2 Key Differences from Current Prompt

| Aspect | Current | New |
|--------|---------|-----|
| Scoring basis | Frequency mapping | Intensity + persistence + impact |
| Score 0 meaning | "Not at all" (ambiguous) | Explicit denial only |
| NA handling | Force 0-3 with flag | `score=null, assertion="not_mentioned"` |
| Context rules | None | ConText: experiencer, temporality, hypothetical |
| Evidence for NA | Optional | Required empty + null confidence |

---

## 4. TDD Test Cases (Prompt Behavior)

### 4.1 Severity Inference Tests

These tests validate that the prompt + model produce expected outputs for canonical inputs.

```python
# TEST: Mild symptom → score 1
def test_prompt_mild_symptom():
    """'Sometimes I feel a bit tired' → fatigue: score=1, assertion='present'"""
    dialogue = "CLIENT: Sometimes I feel a bit tired, but it's not too bad."
    result = score_dialogue(dialogue)
    assert result.fatigue.score == 1
    assert result.fatigue.assertion == "present"

# TEST: Moderate symptom → score 2
def test_prompt_moderate_symptom():
    """'Most days I can't concentrate' → concentration: score=2, assertion='present'"""
    dialogue = "CLIENT: Most days I just can't focus on anything."
    result = score_dialogue(dialogue)
    assert result.concentration.score == 2
    assert result.concentration.assertion == "present"

# TEST: Severe symptom → score 3
def test_prompt_severe_symptom():
    """'Every single night I can't sleep' → sleep: score=3, assertion='present'"""
    dialogue = "CLIENT: Every single night I lie awake for hours. It's destroying me."
    result = score_dialogue(dialogue)
    assert result.sleep.score == 3
    assert result.sleep.assertion == "present"

# TEST: Explicit denial → score 0, assertion='denied'
def test_prompt_explicit_denial():
    """'My appetite is fine' → appetite: score=0, assertion='denied'"""
    dialogue = "THERAPIST: How's your appetite? CLIENT: Actually, it's been fine."
    result = score_dialogue(dialogue)
    assert result.appetite.score == 0
    assert result.appetite.assertion == "denied"
    assert len(result.appetite.evidence) > 0  # Must quote denial

# TEST: Not mentioned → score=None, assertion='not_mentioned'
def test_prompt_not_mentioned():
    """Sleep never discussed → sleep: score=None, assertion='not_mentioned'"""
    dialogue = "CLIENT: I've been feeling really down lately. Nothing brings me joy."
    result = score_dialogue(dialogue)
    # Sleep was never discussed
    assert result.sleep.score is None
    assert result.sleep.assertion == "not_mentioned"
    assert result.sleep.confidence is None
    assert result.sleep.evidence == []
```

### 4.2 ConText Rule Tests

```python
# TEST: Other-experiencer exclusion
def test_context_other_experiencer():
    """'My mother has insomnia' should NOT score client's sleep"""
    dialogue = "CLIENT: My mother has terrible insomnia, she's up all night."
    result = score_dialogue(dialogue)
    # Client's sleep not discussed (mother's sleep doesn't count)
    assert result.sleep.assertion == "not_mentioned"
    assert result.sleep.score is None

# TEST: Historical exclusion
def test_context_historical():
    """'I used to be depressed years ago' should NOT score current mood"""
    dialogue = "CLIENT: Years ago I was really depressed, but I'm over that now."
    result = score_dialogue(dialogue)
    # Historical mention + current denial
    assert result.depressed_mood.assertion == "denied"
    assert result.depressed_mood.score == 0

# TEST: Hypothetical exclusion
def test_context_hypothetical():
    """'If I lost my job I'd be devastated' should NOT score current mood"""
    dialogue = "CLIENT: If I ever lost my job, I'd probably be devastated."
    result = score_dialogue(dialogue)
    # Hypothetical, not current
    assert result.depressed_mood.assertion == "not_mentioned"
    assert result.depressed_mood.score is None

# TEST: Experiencer + current = valid
def test_context_valid_experiencer_current():
    """'I've been exhausted lately' should score fatigue"""
    dialogue = "CLIENT: I've been exhausted lately, even after sleeping."
    result = score_dialogue(dialogue)
    assert result.fatigue.assertion == "present"
    assert result.fatigue.score >= 1
```

### 4.3 Hedged/Possible Tests

```python
# TEST: Hedged mention → score=1, assertion='possible'
def test_prompt_hedged_possible():
    """'Maybe I've been a bit sad' → depressed_mood: score=1, assertion='possible'"""
    dialogue = "CLIENT: I don't know, maybe I've been a bit sad lately?"
    result = score_dialogue(dialogue)
    assert result.depressed_mood.score == 1
    assert result.depressed_mood.assertion == "possible"

# TEST: Too vague → not_mentioned (not possible)
def test_prompt_too_vague():
    """'Things have been weird' → too vague to score any item"""
    dialogue = "CLIENT: I don't know, things have just been weird."
    result = score_dialogue(dialogue)
    # "Weird" doesn't ground to any PHQ item
    # All items should be not_mentioned (or require more specific prompting)
    # This tests that vague language doesn't get force-scored
```

### 4.4 Evidence Quality Tests

```python
# TEST: Evidence must quote client (not therapist)
def test_evidence_quotes_client():
    """Evidence should come from CLIENT lines, not THERAPIST lines"""
    dialogue = """
    THERAPIST: It sounds like you've been feeling down.
    CLIENT: Yeah, I've been really sad lately.
    """
    result = score_dialogue(dialogue)
    # Evidence should quote "I've been really sad" not "sounds like you've been feeling down"
    assert any("sad" in e.lower() for e in result.depressed_mood.evidence)
    assert not any("sounds like" in e.lower() for e in result.depressed_mood.evidence)

# TEST: Not_mentioned has empty evidence
def test_not_mentioned_empty_evidence():
    """not_mentioned assertion must have empty evidence list"""
    dialogue = "CLIENT: Work has been stressful."  # No PHQ items
    result = score_dialogue(dialogue)
    for item in PHQ8_ITEMS:
        item_score = getattr(result, item)
        if item_score.assertion == "not_mentioned":
            assert item_score.evidence == []
            assert item_score.confidence is None
```

---

## 5. Prompt Constants Updates

### 5.1 Current Constants (to be replaced)

**File**: `src/vibe_check/constants.py`

```python
PHQ8_TIME_FRAME = "Over the last 2 weeks"
PHQ8_SCORE_SCALE = """0 = Not at all
1 = Several days
2 = More than half the days
3 = Nearly every day"""
```

### 5.2 New Constants

```python
PHQ8_TIME_FRAME = "Recent period (~last 2 weeks), unless transcript indicates otherwise"

PHQ8_SCORE_SCALE = """
| Evidence Pattern | Score | Cues |
|-----------------|-------|------|
| Mild / intermittent, minimal impact | 1 | "sometimes", "a bit" |
| Frequent/persistent OR moderate impact | 2 | "often", "most days" |
| Near-daily/persistent AND severe impact | 3 | "every day", "can't function" |
| Explicit denial of symptom | 0 | "I'm sleeping fine" |
| No evidence for CLIENT+timeframe | null | not discussed |
"""

PHQ8_ASSERTION_RULES = """
- present (1-3): Symptom clearly described by CLIENT
- denied (0): CLIENT explicitly denies symptom
- possible (1): Hedged/uncertain mention by CLIENT
- not_mentioned (null): No evidence for CLIENT+timeframe
"""

PHQ8_CONTEXT_RULES = """
- Experiencer: Score only CLIENT symptoms (not family/others)
- Temporality: Current/recent only (not historical/resolved)
- Hypothetical: Exclude "what if" / conditional statements
- Negation: Explicit denial → score 0, assertion='denied'
"""
```

---

## 6. Prompt Builder Updates

### 6.1 Function Signature

```python
def build_juror_system_prompt(
    prompt_version: str,
    view_name: str = "client_qa",
    *,
    include_context_rules: bool = True,  # NEW: ConText rules
    include_assertion_rules: bool = True,  # NEW: assertion guidance
) -> str:
    """Build clinical inference system prompt for PHQ-8 scoring."""
```

### 6.2 TDD Test Cases

```python
# TEST: Prompt includes severity inference table
def test_prompt_includes_severity_table():
    prompt = build_juror_system_prompt("v2.0.0")
    assert "Mild / intermittent" in prompt
    assert "Frequent/persistent" in prompt
    assert "Near-daily" in prompt

# TEST: Prompt includes ConText rules
def test_prompt_includes_context_rules():
    prompt = build_juror_system_prompt("v2.0.0", include_context_rules=True)
    assert "Experiencer" in prompt
    assert "Temporality" in prompt
    assert "Hypothetical" in prompt

# TEST: Prompt includes assertion rules
def test_prompt_includes_assertion_rules():
    prompt = build_juror_system_prompt("v2.0.0", include_assertion_rules=True)
    assert "not_mentioned" in prompt
    assert "denied" in prompt
    assert "possible" in prompt

# TEST: Prompt emphasizes NOT DISCUSSED vs DENIED
def test_prompt_emphasizes_na_vs_denied():
    prompt = build_juror_system_prompt("v2.0.0")
    assert "DO NOT score 0 for items that are simply not mentioned" in prompt

# TEST: No frequency anchors in new prompt
def test_prompt_no_frequency_anchors():
    prompt = build_juror_system_prompt("v2.0.0")
    assert "Several days" not in prompt
    assert "More than half the days" not in prompt
    assert "Nearly every day" not in prompt  # Except as cue, not as scale definition
```

---

## 7. Prompt Version Contract

### 7.1 Version Numbering

- **v1.x.x**: Legacy frequency-based prompts (DEPRECATED)
- **v2.0.0**: Clinical inference mode (this spec)

### 7.2 Backward Compatibility

```python
# TEST: v1.x prompts still work (for regression testing)
def test_legacy_prompt_v1():
    prompt = build_juror_system_prompt("v1.0.0")
    assert "Several days" in prompt  # Legacy behavior
    assert "More than half the days" in prompt

# TEST: v2.0 prompts use new format
def test_new_prompt_v2():
    prompt = build_juror_system_prompt("v2.0.0")
    assert "not_mentioned" in prompt
    assert "assertion" in prompt
```

---

## 8. Files Affected

| File | Change Type |
|------|-------------|
| `src/vibe_check/constants.py` | **MODERATE** - New/updated constants |
| `src/vibe_check/scoring/prompting.py` | **MAJOR** - Complete rewrite |
| `tests/unit/test_prompting.py` | **MAJOR** - New test cases |

---

## 9. Acceptance Criteria

- [ ] All test cases in Section 4 pass (behavioral)
- [ ] All test cases in Section 6.2 pass (prompt structure)
- [ ] Prompt version v2.0.0 produces NA-aware outputs
- [ ] Legacy v1.x prompts still work (for comparison)
- [ ] No frequency anchors in v2.0.0 scale definition
- [ ] ConText rules present in prompt
- [ ] Ruff + mypy pass

---

## 10. Sign-Off

| Role | Status |
|------|--------|
| Author | DRAFT |
| Senior Review | PENDING |
