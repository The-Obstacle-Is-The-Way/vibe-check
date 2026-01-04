# System Prompts Reference

This document catalogs all LLM prompts used in vibe-check and their current state.

---

## Prompt Inventory

| Prompt | Location | Agent | Purpose |
|--------|----------|-------|---------|
| [Juror System Prompt](#juror-system-prompt) | `scoring/prompting.py` | Juror | Score PHQ-8 items from dialogue |
| [Judge System Prompt](#judge-system-prompt) | `judge/prompting.py` | Judge | Resolve contested items |
| [Judge Item Prompt](#judge-item-prompt) | `judge/prompting.py` | Judge | Per-item arbitration context |

---

## Juror System Prompt

**File**: `src/vibe_check/scoring/prompting.py`
**Function**: `build_juror_system_prompt(prompt_version, view_name, extra_instructions)`
**Used by**: `JurorScorer` via `build_juror_agent()`

### Current Prompt

```text
You are a clinical scoring juror. Score PHQ-8.

Input: a preprocessed dialogue view named `{view_name}` from a synthetic therapy conversation.
Prompt version: {prompt_version}.

PHQ-8 CLINICAL RUBRIC
=====================

Time frame: Over the last 2 weeks

Scoring scale (0-3 based on frequency):
0 = Not at all
1 = Several days
2 = More than half the days
3 = Nearly every day

Item definitions:
  1. anhedonia: Little interest or pleasure in doing things
  2. depressed_mood: Feeling down, depressed, or hopeless
  3. sleep: Trouble falling or staying asleep, or sleeping too much
  4. fatigue: Feeling tired or having little energy
  5. appetite: Poor appetite or overeating
  6. guilt: Feeling bad about yourself—or that you are a failure or have let yourself or your family down
  7. concentration: Trouble concentrating on things, such as reading the newspaper or watching television
  8. psychomotor: Moving or speaking so slowly that other people could have noticed—or the opposite, being so fidgety or restless that you have been moving around a lot more than usual

IMPORTANT: Match evidence to the EXACT item definition above. Do not infer beyond the text.

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
```

### Notes

- The rubric (definitions, time frame, scale) is embedded directly in the prompt for reproducibility (BUG-040 / SPEC-11).
- Few-shot examples are intentionally omitted to keep prompts stable/minimal.

---

## Judge System Prompt

**File**: `src/vibe_check/judge/prompting.py`
**Function**: `build_judge_system_prompt(prompt_version)`
**Used by**: `JudgeArbitrator` via `build_judge_agent()`

### Current Prompt

```text
You are an expert judge resolving contested PHQ-8 item scores.
Prompt version: {prompt_version}.

PHQ-8 CLINICAL RUBRIC
=====================

Time frame: Over the last 2 weeks

Scoring scale (0-3 based on frequency):
0 = Not at all
1 = Several days
2 = More than half the days
3 = Nearly every day

Item definitions:
  - anhedonia: "Little interest or pleasure in doing things"
  - depressed_mood: "Feeling down, depressed, or hopeless"
  - sleep: "Trouble falling or staying asleep, or sleeping too much"
  - fatigue: "Feeling tired or having little energy"
  - appetite: "Poor appetite or overeating"
  - guilt: "Feeling bad about yourself—or that you are a failure or have let yourself or your family down"
  - concentration: "Trouble concentrating on things, such as reading the newspaper or watching television"
  - psychomotor: "Moving or speaking so slowly that other people could have noticed—or the opposite, being so fidgety or restless that you have been moving around a lot more than usual"

ARBITRATION CRITERIA
====================

When jurors disagree on a score:
1. Review the juror evidence against the EXACT item definition
2. Apply the 0-3 frequency scale strictly (0=Not at all, 3=Nearly every day)
3. If evidence supports multiple interpretations, choose the score best supported by direct CLIENT quotes
4. If evidence is sparse, favor the majority juror vote
5. Higher confidence when multiple jurors cite consistent evidence; lower when evidence is contradictory

Return JSON ONLY. No markdown, no code fences, no prose.
```

### Notes

- The judge prompt embeds the same rubric used by jurors for consistent arbitration (BUG-040 / SPEC-11).

---

## Judge Item Prompt

**File**: `src/vibe_check/judge/prompting.py`
**Function**: `build_judge_item_prompt(scoring_text, item, juror_votes, juror_evidence)`
**Used by**: `JudgeArbitrator.arbitrate_item()`

### Current Prompt

```text
Contested item: {item}
Item definition: "{definition}"

Juror votes: {juror_votes}
Juror evidence snippets:
- {evidence_1}
- {evidence_2}
...

Dialogue (view text):
{scoring_text}

Apply the scoring scale strictly: 0=Not at all, 1=Several days, 2=More than half the days, 3=Nearly every day.

Respond with JSON:
{"item": "{item}", "final_score": 0, "confidence": 0.0, "rationale": "..."}
```

### Notes

- The judge item prompt includes the contested item definition and scale guidance (BUG-040 / SPEC-11).

---

## Constants Not Embedded

**File**: `src/vibe_check/constants.py`

These constants exist and are embedded in prompts:

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

PHQ8_TIME_FRAME: str = "Over the last 2 weeks"

PHQ8_SCORE_SCALE: str = (
    "0 = Not at all\\n"
    "1 = Several days\\n"
    "2 = More than half the days\\n"
    "3 = Nearly every day"
)

PHQ8_RUBRIC: dict[str, str] = {...}
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
│  │ INCLUDES:                                               │    │
│  │ ✓ PHQ-8 item definitions                                │    │
│  │ ✓ Score scale (0=Not at all, 3=Nearly every day)        │    │
│  │ ✓ Time frame (Over the last 2 weeks)                    │    │
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
│  │ JUDGE SYSTEM PROMPT                                     │    │
│  │ + JUDGE ITEM PROMPT (per contested item)                │    │
│  │                                                         │    │
│  │ INCLUDES:                                               │    │
│  │ ✓ Item definition for contested item                    │    │
│  │ ✓ Arbitration criteria                                  │    │
│  │ ✓ Score scale                                           │    │
│  └─────────────────────────────────────────────────────────┘    │
│       │                                                         │
│       ▼                                                         │
│  JudgeItemResolution                                            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Related Documentation

- [BUG-040: Missing PHQ-8 Rubric in Prompts](../_archive/bugs/bug-040-missing-phq8-rubric-in-prompts.md)
- [SPEC-11: PHQ-8 Rubric Embedding](../_specs/SPEC-11-phq8-rubric-embedding.md)
- [Agents: Juror](../agents/juror.md)
- [Agents: Judge](../agents/judge.md)
- [Constants Reference](../reference/settings.md)
