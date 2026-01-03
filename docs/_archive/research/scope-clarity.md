# SCOPE-CLARITY: vibe-check's Sole Purpose

**Date**: 2026-01-03
**Status**: ACTIVE - Read before implementing any new specs

---

## The Problem We're Solving

**ai-psychiatrist** uses few-shot retrieval to improve PHQ-8 scoring accuracy. The paper reports 22% lower item-level MAE with few-shot vs zero-shot (0.796 → 0.619).

Few-shot retrieval requires **labeled reference examples**. But:

| Dataset | Has Transcripts | Has PHQ-8 Labels | Can Redistribute |
|---------|-----------------|------------------|------------------|
| DAIC-WOZ | ✓ | ✓ | ❌ (restricted) |
| SQPsychConv | ✓ | ❌ | ✓ (synthetic) |

**SQPsychConv has no PHQ-8 labels.** We need to create them.

---

## vibe-check's ONLY Job

```
┌─────────────────────────────────────────────────────────────────┐
│                        vibe-check                               │
│                                                                 │
│   INPUT: SQPsychConv (2,090 dialogues, no labels)              │
│                          ↓                                      │
│   PROCESS: Frontier LLM consensus scoring                       │
│                          ↓                                      │
│   OUTPUT: vibe_check_labels.jsonl (2,090 PHQ-8 labels)         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                           ↓
                           ↓  (consumed by)
                           ↓
┌─────────────────────────────────────────────────────────────────┐
│                      ai-psychiatrist                            │
│                                                                 │
│   Uses vibe-check labels as few-shot reference examples         │
│   for embedding-based retrieval during PHQ-8 scoring            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Definition of Done

vibe-check is **COMPLETE** when:

1. ✅ All 2,090 SQPsychConv (qwen-2.5) dialogues are scored
2. ✅ Labels are exported to `vibe_check_labels.jsonl` and `.csv`
3. ✅ Internal diagnostics pass quality gates (Krippendorff α ≥ 0.70, arbitration rate < 30%)
4. ✅ ai-psychiatrist can consume the labels for few-shot retrieval

**That's it.** Once we have the labeled dataset, vibe-check has served its purpose.

---

## What's Already Implemented (SPEC-01 to SPEC-08)

| Spec | Purpose | Status |
|------|---------|--------|
| SPEC-01 | DevEx Foundation (CI, tooling) | ✅ IMPLEMENTED |
| SPEC-02 | Data Pipeline (corpus loading) | ✅ IMPLEMENTED |
| SPEC-03 | Aggregation Engine (posterior math) | ✅ IMPLEMENTED |
| SPEC-04 | Juror Scoring Agent (PydanticAI) | ✅ IMPLEMENTED |
| SPEC-05 | Consensus Orchestration (LangGraph) | ✅ IMPLEMENTED |
| SPEC-06 | Batch Runner & Export | ✅ IMPLEMENTED |
| SPEC-07 | Run Diagnostics (quality gates) | ✅ IMPLEMENTED |
| SPEC-08 | Export Contract (public label format) | ✅ IMPLEMENTED |

**The core engine is done.** We can run `vibe-check score-corpus --live` today.

---

## Optional Spec

| Spec | Purpose | Verdict | Rationale |
|------|---------|---------|-----------|
| **SPEC-09** | Human-in-the-Loop Calibration | ⚠️ CONDITIONAL | Only needed if internal diagnostics fail. If Krippendorff α ≥ 0.70, we don't need human calibration for a one-shot labeling job. |

SPEC-10 (Chaos Testing) and SPEC-11 (TUI) were deleted as unnecessary scope creep.

---

## The Real Remaining Work

### 1. Run the Production Scoring (~$95-185)

```bash
vibe-check score-corpus \
  --input data/sqpsychconv/qwen-2.5 \
  --checkpoint sqlite:///data/checkpoints/production.db \
  --output data/outputs \
  --live \
  --prompt-version v1.0.0
```

### 2. Validate Internal Diagnostics

```bash
vibe-check diagnostics \
  --scored data/outputs/scored.jsonl \
  --output data/outputs/diagnostics.json \
  --strict
```

**If this passes** (Krippendorff α ≥ 0.70, arbitration < 30%):
- Export labels
- Ship to ai-psychiatrist
- Done

**If this fails**:
- Investigate specific failures
- Consider SPEC-09 (human calibration) IF needed

### 3. Export Public Labels

```bash
vibe-check export \
  --input data/outputs/scored.jsonl \
  --output-dir data/outputs/public \
  --format jsonl,csv
```

### 4. Integrate with ai-psychiatrist

Create embeddings from labeled SQPsychConv for few-shot retrieval.
This happens in ai-psychiatrist, NOT vibe-check. See [Issue #38](https://github.com/The-Obstacle-Is-The-Way/ai-psychiatrist/issues/38).

---

## What We're NOT Building

| Feature | Why Not |
|---------|---------|
| Continuous deployment | There's nothing to deploy continuously |
| Multi-tenant support | One user, one run |
| Real-time scoring API | Batch job only |

---

## Decision Framework

Before implementing anything new, ask:

1. **Does this help us label SQPsychConv?**
   - If no → Don't implement

2. **Can we ship labels without this?**
   - If yes → Defer

3. **Is this fixing a bug that blocks the run?**
   - If no → Defer

---

## Recommended Action

1. **Run the production batch** with existing SPEC-01-08 implementation
2. **Check diagnostics** - if they pass, ship labels
3. **If diagnostics fail** - consider SPEC-09 (human calibration)
4. **Ship labels to ai-psychiatrist**
5. **Close the vibe-check project**

---

## Success Metric

```
ai-psychiatrist can load vibe_check_labels.jsonl
and use it for few-shot retrieval.
```

That's the only metric that matters.
