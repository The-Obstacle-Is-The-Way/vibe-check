# System Prompts Reference

This document catalogs all LLM prompts used in vibe-check, their current state, and identified issues.

---

## Prompt Inventory

| Prompt | Location | Agent | Purpose |
|--------|----------|-------|---------|
| [Juror System Prompt](#juror-system-prompt) | `scoring/prompting.py:6-48` | Juror | Score PHQ-8 items from dialogue |
| [Judge System Prompt](#judge-system-prompt) | `judge/prompting.py:8-13` | Judge | Resolve contested items |
| [Judge Item Prompt](#judge-item-prompt) | `judge/prompting.py:16-39` | Judge | Per-item arbitration context |

---

## Juror System Prompt

**File**: `src/vibe_check/scoring/prompting.py`
**Function**: `build_juror_system_prompt(prompt_version, view_name, extra_instructions)`
**Used by**: `JurorScorer` via `build_juror_agent()`

### Current Prompt (v1)

```text
You are a clinical scoring juror. Score PHQ-8.

Input: a preprocessed dialogue view named `{view_name}` from a synthetic therapy conversation.
Prompt version: {prompt_version}.

Rules:
- Use ONLY the provided text. Do not assume facts not stated.
- Score PHQ-8 items only (8 items). Self-harm is a separate boolean tag, not an extra item.
- Therapist lines are context; evidence should quote/paraphrase CLIENT statements.
- If evidence is insufficient for an item, set `insufficient_evidence=true` and still choose the best score (0-3).

For each item, return:
- score: integer 0-3
- confidence: float 0.0-1.0
- evidence: list of up to 3 short snippets (each <= 50 words)
- insufficient_evidence: boolean

Also return:
- mentions_self_harm: boolean (true if the client expresses self-harm/suicidal ideation)
- self_harm_evidence: list of up to 3 short snippets
- total_score: sum of the 8 item scores (0-24)

Return JSON ONLY. No markdown, no code fences, no prose.

Items (PHQ-8):
- anhedonia
- depressed_mood
- sleep
- fatigue
- appetite
- guilt
- concentration
- psychomotor
```

### Issues Identified

| Issue | Severity | Description |
|-------|----------|-------------|
| **Missing PHQ-8 rubric** | CRITICAL | Only item names listed; no clinical definitions |
| **Missing score scale** | HIGH | No "0=Not at all, 1=Several days..." guidance |
| **Missing time frame** | HIGH | PHQ-8 asks about "last 2 weeks" - not specified |
| **Implicit LLM knowledge** | HIGH | Relies on model pre-training for PHQ-8 semantics |
| **No scoring examples** | MEDIUM | Few-shot examples could improve consistency |

### What's Missing (Official PHQ-8)

The official PHQ-8 questionnaire text (public domain, derived from PHQ-9):

| Item | Official Question Text |
|------|------------------------|
| anhedonia | "Little interest or pleasure in doing things" |
| depressed_mood | "Feeling down, depressed, or hopeless" |
| sleep | "Trouble falling or staying asleep, or sleeping too much" |
| fatigue | "Feeling tired or having little energy" |
| appetite | "Poor appetite or overeating" |
| guilt | "Feeling bad about yourself—or that you are a failure or have let yourself or your family down" |
| concentration | "Trouble concentrating on things, such as reading the newspaper or watching television" |
| psychomotor | "Moving or speaking so slowly that other people could have noticed? Or the opposite—being so fidgety or restless that you have been moving around a lot more than usual" |

**Scoring Scale** (not in current prompt):
- 0 = Not at all
- 1 = Several days
- 2 = More than half the days
- 3 = Nearly every day

**Time Frame** (not in current prompt):
- "Over the last 2 weeks, how often have you been bothered by..."

---

## Judge System Prompt

**File**: `src/vibe_check/judge/prompting.py`
**Function**: `build_judge_system_prompt(prompt_version)`
**Used by**: `JudgeArbitrator` via `build_judge_agent()`

### Current Prompt

```text
You are an expert judge resolving contested PHQ-8 item scores.
Prompt version: {prompt_version}.

Return JSON ONLY. No markdown, no code fences, no prose.
```

### Issues Identified

| Issue | Severity | Description |
|-------|----------|-------------|
| **Extremely minimal** | CRITICAL | Only 3 lines; no guidance on arbitration logic |
| **No PHQ-8 rubric** | CRITICAL | Judge doesn't know what items mean |
| **No arbitration criteria** | HIGH | How should judge weigh juror votes vs evidence? |
| **No confidence calibration** | MEDIUM | What does confidence 0.8 vs 0.5 mean? |

---

## Judge Item Prompt

**File**: `src/vibe_check/judge/prompting.py`
**Function**: `build_judge_item_prompt(scoring_text, item, juror_votes, juror_evidence)`
**Used by**: `JudgeArbitrator.arbitrate_item()`

### Current Prompt

```text
Contested item: {item}

Juror votes: {juror_votes}
Juror evidence snippets:
- {evidence_1}
- {evidence_2}
...

Dialogue (view text):
{scoring_text}

Respond with JSON:
{"item": "{item}", "final_score": 0, "confidence": 0.0, "rationale": "..."}
```

### Issues Identified

| Issue | Severity | Description |
|-------|----------|-------------|
| **No item definition** | CRITICAL | Judge sees "anhedonia" but not what it means |
| **No scoring guidance** | HIGH | What makes a score 2 vs 3? |
| **No arbitration rules** | HIGH | Majority vote? Best evidence? Weighted average? |
| **Placeholder in example** | LOW | Shows `"final_score": 0` which may bias toward 0 |

---

## Constants Not Embedded

**File**: `src/vibe_check/constants.py`

These constants exist but are NOT included in prompts:

```python
PHQ8_ITEMS: tuple[str, ...] = (
    "anhedonia",
    "depressed_mood",
    "sleep",
    "fatigue",
    "appetite",
    "guilt",
    "concentration",
    "psychomotor",
)

# These exist but are not in prompts:
# - No PHQ8_RUBRIC with full question text
# - No PHQ8_SCORE_SCALE with frequency descriptions
# - No PHQ8_TIME_FRAME ("last 2 weeks")
```

---

## Prompt Flow Diagram

```text
┌─────────────────────────────────────────────────────────────────┐
│                     PROMPT CHAIN                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Dialogue Text                                                  │
│       │                                                         │
│       ▼                                                         │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ JUROR SYSTEM PROMPT                                     │    │
│  │ + scoring_text (user message)                           │    │
│  │                                                         │    │
│  │ MISSING:                                                │    │
│  │ ✗ PHQ-8 item definitions                                │    │
│  │ ✗ Score scale (0=Not at all, 3=Nearly every day)        │    │
│  │ ✗ Time frame (last 2 weeks)                             │    │
│  │ ✗ Scoring examples                                      │    │
│  └─────────────────────────────────────────────────────────┘    │
│       │                                                         │
│       ▼                                                         │
│  6× PHQ8Report                                                  │
│       │                                                         │
│       ▼                                                         │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ AGGREGATION (no LLM, pure math)                         │    │
│  │ → Detects contested items                               │    │
│  └─────────────────────────────────────────────────────────┘    │
│       │                                                         │
│       ▼ (if contested)                                          │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ JUDGE SYSTEM PROMPT (minimal)                           │    │
│  │ + JUDGE ITEM PROMPT (per contested item)                │    │
│  │                                                         │    │
│  │ MISSING:                                                │    │
│  │ ✗ PHQ-8 item definition for contested item              │    │
│  │ ✗ Arbitration criteria                                  │    │
│  │ ✗ Score scale                                           │    │
│  │ ✗ How to weigh evidence vs votes                        │    │
│  └─────────────────────────────────────────────────────────┘    │
│       │                                                         │
│       ▼                                                         │
│  JudgeItemResolution                                            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Related Documentation

- [BUG-037: Missing PHQ-8 Rubric in Prompts](../_bugs/BUG-037-missing-phq8-rubric.md)
- [Agents: Juror](../agents/juror.md)
- [Agents: Judge](../agents/judge.md)
- [Constants Reference](../reference/settings.md)
