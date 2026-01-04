# BUG-040: Missing PHQ-8 Clinical Rubric in System Prompts

| Field | Value |
|-------|-------|
| **Severity** | P0 (Critical) |
| **Status** | resolved |
| **Date** | 2026-01-04 |
| **Component** | `scoring/prompting.py`, `judge/prompting.py`, `constants.py` |
| **Impact** | Reproducibility, cross-model consistency, clinical validity |

---

## Summary

The vibe-check system prompts for jurors and judge agents rely entirely on LLM pre-trained knowledge of PHQ-8. Neither the juror nor judge prompts include:

1. **PHQ-8 item definitions** (official question text)
2. **Scoring scale** (0=Not at all, 1=Several days, 2=More than half the days, 3=Nearly every day)
3. **Time frame** ("Over the last 2 weeks")
4. **Arbitration criteria** (for judge)

This is a **fundamental reproducibility and clinical validity issue**.

---

## Current State

### Juror System Prompt (`scoring/prompting.py:36-44`)

```text
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

**Problem**: Only item names, no definitions. LLM must "remember" what each item means.

### Judge System Prompt (`judge/prompting.py:8-13`)

```text
You are an expert judge resolving contested PHQ-8 item scores.
Prompt version: {prompt_version}.

Return JSON ONLY. No markdown, no code fences, no prose.
```

**Problem**: Only 3 lines. Judge has no guidance on what items mean or how to arbitrate.

### Judge Item Prompt (`judge/prompting.py:16-39`)

```text
Contested item: {item}
Juror votes: {juror_votes}
...
```

**Problem**: Item name only (e.g., "anhedonia"), no definition provided.

---

## Why This Is Critical

### 1. Cross-Model Inconsistency

Different LLMs may have different "memories" of PHQ-8:

| Model | Potential Issue |
|-------|-----------------|
| GPT-5.2 | May conflate PHQ-8 with PHQ-9 (includes self-harm item) |
| Claude | May use different clinical phrasing |
| Gemini | May have different training cutoff with older versions |

Without explicit rubric, same dialogue → different scores depending on model.

### 2. Training Data Drift

If a model updates its training data:
- Same prompt → different interpretation
- No way to detect this drift
- Historical scores become non-comparable

### 3. Audit Trail Missing

Current state:
- `prompt_version=v1` is recorded
- But what does `v1` mean? The rubric isn't defined anywhere

Cannot prove what clinical criteria were used for a given run.

### 4. Research Best Practices Violated

| Paper | Recommendation | Our Compliance |
|-------|----------------|----------------|
| [LMIQ (arxiv:2406.06636)](https://arxiv.org/abs/2406.06636) | Embed full question text | **NO** |
| [Chain-of-Thought (arxiv:2408.14053)](https://arxiv.org/abs/2408.14053) | "Fed the PHQ-8 rubric" first | **NO** |
| [HopeBot 2025 (arxiv:2507.05984)](https://arxiv.org/abs/2507.05984) | RAG with item-specific clarifications | **NO** |

---

## Risk Diagram

```text
┌─────────────────────────────────────────────────────────────┐
│                CURRENT IMPLICIT DEPENDENCY                  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  System Prompt: "Score PHQ-8 items: anhedonia, ..."         │
│         │                                                   │
│         ▼                                                   │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ LLM Pre-training Knowledge (UNCONTROLLED)           │    │
│  │                                                     │    │
│  │  "I think I remember PHQ-8..."                      │    │
│  │                                                     │    │
│  │  RISKS:                                             │    │
│  │  • May confuse PHQ-8 with PHQ-9 (self-harm item)    │    │
│  │  • May use different clinical version               │    │
│  │  • May vary between model updates                   │    │
│  │  • Different interpretation per provider            │    │
│  │  • No reproducibility guarantee                     │    │
│  └─────────────────────────────────────────────────────┘    │
│         │                                                   │
│         ▼                                                   │
│  PHQ8Report (potentially inconsistent/invalid)              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## What Should Be Embedded

### PHQ-8 Item Definitions (Official Text)

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

### Scoring Scale

```text
Score each item 0-3 based on frequency OVER THE LAST 2 WEEKS:
  0 = Not at all
  1 = Several days
  2 = More than half the days
  3 = Nearly every day
```

### Judge Arbitration Criteria

```text
When resolving contested items:
1. Review juror evidence against the item definition
2. Apply the 0-3 frequency scale strictly
3. If evidence supports multiple interpretations, choose the score best supported by direct quotes
4. Higher confidence when multiple jurors cite consistent evidence
```

---

## Fix Required

See **SPEC-11: PHQ-8 Rubric Embedding** for implementation details.

---

## Resolution (Implemented)

- Added `PHQ8_RUBRIC`, `PHQ8_SCORE_SCALE`, `PHQ8_TIME_FRAME`, and `phq8_rubric_hash()` in `src/vibe_check/constants.py`.
- Embedded the rubric + scale + time frame into juror and judge prompts in `src/vibe_check/scoring/prompting.py` and `src/vibe_check/judge/prompting.py`.
- Recorded `phq8_rubric_hash` into `run_manifest.json` via `src/vibe_check/run/runner.py`.

### High-Level Changes

1. **`constants.py`**: Add `PHQ8_RUBRIC`, `PHQ8_SCORE_SCALE`, `PHQ8_TIME_FRAME`
2. **`scoring/prompting.py`**: Embed rubric in juror system prompt
3. **`judge/prompting.py`**: Embed rubric + arbitration criteria in judge prompts
4. **`run_manifest.json`**: Record rubric hash for audit trail

---

## Test Plan

1. Verify new prompts include all 8 item definitions
2. Verify scoring scale appears in prompts
3. Verify time frame ("last 2 weeks") appears
4. Verify judge prompts include item definitions
5. Verify rubric hash recorded in manifest
6. Integration test: same dialogue → consistent scores across models (improved)

---

## Terminology Note

**"Embedding" in this bug refers to prompt embedding** (including text directly in the prompt), NOT vector embeddings (numerical ML representations for RAG).

Vector embeddings are unnecessary for the PHQ-8 rubric because:
- Only 8 fixed items (~200 tokens)
- Static content that never changes
- Direct inclusion guarantees 100% accuracy (no retrieval errors)

See SPEC-11 for full design decision rationale and future vector embedding recommendations.

---

## Related

- [SPEC-11: PHQ-8 Rubric Embedding](../_specs/SPEC-11-phq8-rubric-embedding.md)
- [Prompts Reference](../prompts/index.md)
- [Agents: Juror](../agents/juror.md)
- [Agents: Judge](../agents/judge.md)
