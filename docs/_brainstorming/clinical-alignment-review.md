# Clinical Alignment Review: PHQ-8 Scoring from Therapy Transcripts

> **Status**: CRITICAL PRE-RUN REVIEW — Awaiting Senior Approval
> **Author**: Clinical (Double-Board Psychiatrist) + Engineering collaboration
> **Date**: 2026-01-06
> **Blocks**: All paid API scoring runs

---

## Executive Summary

**Problem**: The current vibe-check implementation scores PHQ-8 items using frequency-based logic ("several days", "more than half the days") that doesn't exist in therapy transcripts. Worse, score 0 conflates "patient denied symptom" with "symptom not mentioned"—a critical clinical error.

**Solution**: Align with how psychiatrists actually infer symptoms:
1. **Infer severity from intensity** ("I'm exhausted" → high severity) instead of expecting explicit frequency anchors
2. **Allow NA for undiscussed items** using clinical NLP assertion standards (present/denied/possible/not_mentioned)
3. **Report both prorated AND imputed totals** since missing items are not random (MNAR)

**Key Innovation**: Extending standard clinical NLP assertion frameworks with `not_mentioned`—novel but clinically correct for third-party inference from transcripts.

**Impact**: These changes are required before spending money on API calls. The current implementation would generate embeddings that encode incorrect patterns (frequency expectations, 0=not_mentioned conflation).

---

## Questions for Senior Reviewer

Before approving this document, please confirm:

1. [ ] **Schema**: Is the `assertion` field (present/denied/possible/not_mentioned) the right clinical abstraction?
2. [ ] **Proration**: Is 50% coverage (≥4 items discussed) a reasonable validity threshold?
3. [ ] **Intensity mapping**: Does the intensity→severity table (Section 12.3) match clinical judgment?
4. [ ] **"Possible" handling**: Should uncertain mentions (e.g., "maybe I've been a bit tired") be:
   - Scored as 1 with `assertion="possible"`, OR
   - Scored as NA with `assertion="possible"`?
5. [ ] **Judge behavior**: Should the judge be able to override a juror's `not_mentioned` if evidence exists?

---

## 1. The Core Question

**Does the current vibe-check implementation align with how a psychiatrist would actually infer PHQ-8 scores from a therapy transcript?**

---

## 2. How PHQ-8 Works in Real Clinical Practice

### 2.1 The Standard PHQ-8 Flow

```
Patient arrives → Fills out PHQ-8 in waiting room → Talks to psychiatrist
                         ↓
              Self-reported frequency scores (0-3)
              "In the last 2 weeks, how often..."
```

The PHQ-8 is a **self-report instrument**. The patient explicitly marks:
- 0 = Not at all
- 1 = Several days
- 2 = More than half the days
- 3 = Nearly every day

### 2.2 What Actually Happens in the Therapy Session

The psychiatrist **does NOT** typically ask:
- "In the last two weeks, how many days did you feel tired?"
- "Would you say more than half the days or nearly every day?"

Instead, the psychiatrist:
1. **Assumes a recent timeframe** (implicit "lately" = last 2 weeks)
2. **Infers severity from intensity language** ("I've been exhausted" → high severity)
3. **Notes what's NOT mentioned** (silence on appetite ≠ "no appetite problems")

### 2.3 The Key Clinical Insight

> **A psychiatrist infers severity from intensity, not frequency counts.**

| Patient says | Psychiatrist infers | PHQ-8 equivalent |
|--------------|---------------------|------------------|
| "I've been really tired lately" | Moderate-high severity | Score 2-3 |
| "Sometimes I feel a bit low" | Mild severity | Score 1 |
| "I can't sleep at all anymore" | High severity | Score 3 |
| *(doesn't mention appetite)* | **Unknown, not 0** | **NA** |

---

## 3. Current System Alignment Analysis

### 3.1 What the Current System Does

```python
# Current PHQ8ItemScore schema
class PHQ8ItemScore(BaseModel):
    score: Literal[0, 1, 2, 3]      # REQUIRED - must pick 0-3
    confidence: float               # 0.0-1.0
    evidence: list[str]             # supporting quotes
    insufficient_evidence: bool     # flag, but still requires score
```

**Problem**: If an item isn't mentioned, the juror MUST still pick a score (0-3). There's no "not discussed" option.

### 3.2 Current Prompt Language

From `src/vibe_check/scoring/prompting.py`:

```
Time frame: Over the last 2 weeks

Scoring scale (0-3 based on frequency):
0 = Not at all
1 = Several days
2 = More than half the days
3 = Nearly every day
```

**Problem**: This prompts jurors to expect explicit frequency language that doesn't exist in the transcripts.

### 3.3 Misalignment Summary

| Aspect | Clinical Reality | Current Implementation | Aligned? |
|--------|------------------|------------------------|----------|
| Timeframe | Implicit (assume recent) | Explicit ("last 2 weeks") | ⚠️ Partial |
| Scoring basis | Intensity → severity | Frequency counts | ❌ **NO** |
| Not mentioned | Unknown / NA | Must score 0-3 | ❌ **NO** |
| Score 0 meaning | Explicitly denied | Not mentioned OR denied | ❌ **NO** |

---

## 4. The Downstream Purpose (Why This Matters)

### 4.1 The Full Pipeline Vision

```
┌─────────────────────────────────────────────────────────────────────┐
│                    FULL RESEARCH PIPELINE                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  SQPsychConv (synthetic)          DAIC-WOZ (real)                   │
│  2,090 dialogues                  189 clinical interviews           │
│         │                                │                          │
│         ▼                                │                          │
│  ┌─────────────────┐                     │                          │
│  │ vibe-check      │                     │                          │
│  │ PHQ-8 scoring   │                     │                          │
│  └────────┬────────┘                     │                          │
│           │                              │                          │
│           ▼                              │                          │
│  ┌─────────────────┐                     │                          │
│  │ ai-psychiatrist │                     │                          │
│  │ embeddings      │◄────────────────────┘                          │
│  │ + few-shot      │                                                │
│  └────────┬────────┘                                                │
│           │                                                         │
│           ▼                                                         │
│  Predict PHQ-8 on unseen DAIC-WOZ transcripts                       │
│                                                                     │
│  VALIDATION: Do synthetic-trained embeddings generalize to real?    │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 4.2 Why Alignment Matters

If vibe-check scores are misaligned with clinical inference:
1. **Embeddings learn wrong patterns** (frequency language vs intensity)
2. **Few-shot examples mislead** (model expects explicit anchors)
3. **Transfer to DAIC-WOZ fails** (real transcripts don't have PHQ anchors either)

The scores need to reflect **what a psychiatrist would infer**, not what explicit PHQ-8 anchors are present.

---

## 5. Proposed Fixes

> **Note**: Sections 5-6 explore options. See **Section 12** for final evidence-based recommendations.

### 5.1 Schema Change: Add "Not Discussed" Option

**Current**:
```python
score: Literal[0, 1, 2, 3]  # Must pick one
insufficient_evidence: bool  # Flag only
```

**Proposed**:
```python
score: Literal[0, 1, 2, 3] | None  # None = not discussed
discussed: bool                    # Explicit flag
```

OR more explicit:
```python
class PHQ8ItemScore(BaseModel):
    discussed: bool                           # Was this symptom domain mentioned?
    score: Literal[0, 1, 2, 3] | None        # None if not discussed
    explicitly_denied: bool                   # Patient said "no, I'm eating fine"
    confidence: float
    evidence: list[str]
```

**Semantic distinction**:
- `score=0, discussed=True, explicitly_denied=True` → Patient said "I'm sleeping fine"
- `score=None, discussed=False` → Sleep never came up
- `score=2, discussed=True` → Patient described moderate sleep issues

### 5.2 Prompt Rewrite: Clinical Inference Mode

**Current prompt focus**: Frequency mapping
**Proposed prompt focus**: Clinical severity inference

```markdown
You are a psychiatrist reviewing a therapy transcript to infer PHQ-8 symptom severity.

CLINICAL INFERENCE GUIDELINES:
1. TIMEFRAME: Assume the conversation reflects the patient's recent state (last ~2 weeks).
   Do NOT expect explicit "in the last two weeks" language.

2. SEVERITY INFERENCE: Map patient language intensity to severity:
   - Mild indicators: "sometimes", "a bit", "occasionally" → Score 1
   - Moderate indicators: "often", "really", "a lot" → Score 2
   - Severe indicators: "always", "can't", "completely", "every day" → Score 3
   - Explicitly denied: "I'm sleeping fine", "appetite is good" → Score 0

3. NOT DISCUSSED vs DENIED:
   - If the symptom domain is NOT mentioned at all → discussed=false, score=null
   - If the patient explicitly denies the symptom → discussed=true, score=0, explicitly_denied=true
   - Score 0 means "explicitly absent", NOT "not mentioned"

4. EVIDENCE REQUIREMENT:
   - For scores 1-3: Quote the patient language that indicates severity
   - For score 0: Quote the denial ("I'm eating normally")
   - For not discussed: No evidence needed (symptom domain absent)
```

### 5.3 Total Score Handling with NA Items

If items can be NA, how do we compute total score?

**Option A: Prorated scoring**
```python
# Only sum discussed items, scale to 0-24
discussed_items = [s for s in scores if s.discussed]
if len(discussed_items) >= 4:  # Minimum coverage
    raw_sum = sum(s.score for s in discussed_items)
    total = (raw_sum / len(discussed_items)) * 8  # Scale to 8 items
else:
    total = None  # Insufficient coverage
```

**Option B: Conservative imputation**
```python
# Treat NA as 0 for total, but flag
total = sum(s.score if s.score is not None else 0 for s in scores)
na_count = sum(1 for s in scores if s.score is None)
# Report: total=12 (3 items not discussed)
```

**Option C: Separate tracking**
```python
# Report both
discussed_total = sum(s.score for s in scores if s.discussed)  # e.g., 12/5 items
coverage = len([s for s in scores if s.discussed]) / 8          # e.g., 62.5%
```

**Recommendation**: Option C - preserve full information for downstream decisions.

---

## 6. Impact on Downstream (ai-psychiatrist)

### 6.1 Embedding Implications

If we use NA-aware scores, embeddings can learn:
- Which symptom domains are typically discussed
- Severity when discussed
- Coverage patterns

This is **richer signal** than forcing 0 for not-mentioned items.

### 6.2 Few-Shot Implications

Few-shot examples should show:
```
Transcript: "I've been feeling really down lately, can't enjoy anything..."
PHQ-8 inference:
- depressed_mood: 2 (discussed, "feeling really down")
- anhedonia: 2 (discussed, "can't enjoy anything")
- sleep: NA (not discussed)
- appetite: NA (not discussed)
...
```

This teaches the model that not-mentioned ≠ absent.

---

## 7. Hidden Gotchas Checklist

| Gotcha | Status | Mitigation |
|--------|--------|------------|
| Score 0 conflates "denied" and "not mentioned" | ❌ Current issue | Schema change |
| Prompts expect frequency anchors | ❌ Current issue | Prompt rewrite |
| Total score undefined with NA items | ⚠️ Need decision | Choose Option A/B/C |
| Juror disagreement on intensity→severity mapping | ⚠️ Expected | Arbitration handles |
| Appetite/psychomotor rarely discussed | ✅ Known | Will mostly be NA |
| Therapist text leaks condition | ✅ Mitigated | Use client_only view |
| file_id encodes condition | ✅ Mitigated | Not in prompts |
| No explicit timeframe in transcripts | ✅ Addressed | Prompt assumes recent |

---

## 8. Decision Points Before Running

### 8.1 Must Decide

- [ ] **Schema change**: Add `discussed` flag and allow `score=None`?
- [ ] **Total score method**: Prorated, imputed, or separate tracking?
- [ ] **Prompt rewrite**: Switch from frequency to intensity inference?

### 8.2 Can Defer to Pilot

- [ ] Per-item NA rates (measure empirically)
- [ ] Juror agreement on intensity mapping
- [ ] Judge override patterns

---

## 9. Recommended Path Forward

### Phase 1: Schema + Prompt Update (Before Spending Money)

1. Update `PHQ8ItemScore` schema to include `discussed` and allow `score=None`
2. Rewrite juror prompts for clinical severity inference
3. Update aggregation to handle NA items
4. Update diagnostics to report per-item NA rates

### Phase 2: Validation Pilot (~$20)

1. Run 50 dialogues with updated system
2. Review: Are NA rates sensible? Is severity inference reasonable?
3. Check: Does MDD vs control separation hold?

### Phase 3: Full Run (if Phase 2 passes)

1. Score all 2,090 dialogues
2. Export with full NA information
3. Use in ai-psychiatrist with NA-aware embeddings

---

## 10. Summary: Is the System Aligned?

**Current state**: NO - critical misalignments exist.

| Aspect | Aligned? | Fix Required |
|--------|----------|--------------|
| Score 0 semantics | ❌ | Schema change |
| Frequency vs intensity | ❌ | Prompt rewrite |
| NA handling | ❌ | Schema + aggregation |
| Timeframe assumption | ⚠️ | Prompt clarification |
| Evidence extraction | ✅ | None |
| Multi-juror consensus | ✅ | None |
| Arbitration | ✅ | None |

**Recommendation**: Implement Phase 1 fixes before any paid API calls. The scoring will be fundamentally more aligned with clinical practice and more useful for downstream embedding training.

---

## 11. Research-Backed Recommendations (Web Search Findings)

### 11.1 Official PHQ Proration Formula

From [APA DSM-5 Severity Measures](https://www.psychiatry.org/File%20Library/Psychiatrists/Practice/DSM/APA_DSM5_Severity-Measure-For-Depression-Child-Age-11-to-17.pdf):

> **Prorated Score = (Partial Raw Score × Total Items) ÷ Items Answered**
> If the result is a fraction, round to the nearest whole number.

**Example**: If 5 of 8 items are scored with raw sum = 10:
```
Prorated = (10 × 8) ÷ 5 = 16
```

**Caveat**: This assumes items are missing at random. In our case, items are systematically not discussed (appetite, psychomotor), so proration may overestimate if those items would typically be low.

### 11.2 Clinical NLP Assertion Annotation Standards

From [John Snow Labs Clinical NLP Best Practices](https://www.johnsnowlabs.com/tips-and-tricks-on-how-to-annotate-assertion-in-clinical-texts/) and [i2b2/VA Challenge](https://pmc.ncbi.nlm.nih.gov/articles/PMC3900128/):

Standard assertion labels in clinical NLP:

| Label | Meaning | Example |
|-------|---------|---------|
| **Present** | Entity is affirmed | "Patient has insomnia" |
| **Absent** | Entity is negated | "Denies insomnia" |
| **Possible** | Uncertainty expressed | "May have insomnia" |
| **Hypothetical** | Conditional | "If insomnia worsens..." |
| **Past** | Historical | "History of insomnia" |

**Critical gap**: Standard clinical NLP frameworks assume you're annotating entities that WERE mentioned. There's no standard "not mentioned" category because typical NER only extracts what's in the text.

**Our innovation**: We need a **"not discussed"** category that's distinct from "absent/negated". This is novel but clinically correct.

### 11.3 Mental Health Dataset Publishing Standards

From [GitHub mental-health-datasets](https://github.com/kharrigian/mental-health-datasets) and [HuggingFace mental health collections](https://huggingface.co/datasets/Amod/mental_health_counseling_conversations):

Best practices for mental health NLP datasets:

1. **Explicit missing indicators**: Use `null`/`None` rather than sentinel values like `-1`
2. **Confidence scores**: Include annotator confidence alongside labels
3. **Coverage metrics**: Report what % of items have labels
4. **Multi-annotator data**: Preserve disagreement, don't just report consensus
5. **Annotation guidelines**: Publish the exact instructions given to annotators

**Notable**: The [Primate2022 dataset](https://arxiv.org/html/2412.03796v1) labels Reddit posts using PHQ-9, demonstrating precedent for LLM-based PHQ annotation.

### 11.4 LLM Psychiatric Annotation Research

From [Nature npj Mental Health (2025)](https://www.nature.com/articles/s44184-025-00175-1) and [PMC LLM Psychiatric Interviews](https://pmc.ncbi.nlm.nih.gov/articles/PMC11544339/):

| Finding | Implication |
|---------|-------------|
| LLMs achieve 86.9% accuracy identifying clinical annotations | LLM annotation is viable |
| Recall increases from 77.3% → 86.1% with fine-tuning | Our multi-juror approach compensates |
| "Hallucinations" occur when LLMs face queries they can't handle | NA option prevents forced hallucination |
| Lack of clinical validation is the primary limitation | MDD vs control separation validates |

**Key insight**: Forcing LLMs to score items without evidence leads to hallucination. Allowing NA is both clinically correct AND reduces hallucination risk.

### 11.5 Addressing Item-Level Missing Data (PMC Research)

From [PMC Proration vs FIML Study](https://pmc.ncbi.nlm.nih.gov/articles/PMC4701045/):

> "Often when participants have missing scores on one or more items comprising a scale, researchers compute prorated scale scores by averaging the available items. Methodologists have cautioned that proration may make strict assumptions about the missing data mechanisms."

**Translation**: Proration assumes Missing Completely At Random (MCAR). Our case is Missing Not At Random (MNAR) - appetite/psychomotor are systematically not discussed. Proration will be biased.

**Recommendation**: Report both raw discussed scores AND prorated total, letting downstream users choose.

---

## 12. Final Recommendations (Evidence-Based)

### 12.1 Schema Decision: **Use NA-Aware Schema** ✅ RECOMMENDED

**Current file**: `src/vibe_check/schemas/scoring.py`

```python
class PHQ8ItemScore(BaseModel):
    """Single PHQ-8 item score with clinical annotation semantics."""

    discussed: bool                      # Was this symptom domain mentioned at all?
    score: Literal[0, 1, 2, 3] | None   # None if not discussed
    assertion: Literal[                  # Clinical NLP standard (extended)
        "present",      # Symptom affirmed (score 1-3)
        "denied",       # Symptom explicitly denied (score 0)
        "possible",     # Uncertain mention (score 1, flagged for review)
        "not_mentioned" # Symptom domain absent from transcript (score=None)
    ]
    confidence: float                    # 0.0-1.0
    evidence: list[str]                  # Up to 3 supporting quotes
```

**Assertion Values Explained**:

| Assertion | Score | When to Use | Example |
|-----------|-------|-------------|---------|
| `present` | 1-3 | Patient clearly describes symptom | "I can't sleep at all" |
| `denied` | 0 | Patient explicitly denies symptom | "My appetite is fine" |
| `possible` | 1 | Uncertain or hedged mention | "Maybe I've been a bit tired" |
| `not_mentioned` | None | Symptom domain never discussed | *(no sleep discussion)* |

**Note on `possible`**: Per reviewer question #4, we score `possible` as 1 (conservative non-zero) rather than NA because the symptom WAS mentioned, just with uncertainty. The `assertion="possible"` flag allows downstream filtering if desired.

**Rationale**:
- Aligns with clinical NLP assertion standards
- Prevents forced hallucination
- Preserves full information for downstream use
- Novel but clinically correct extension of standard frameworks

### 12.2 Total Score Decision: **Report Both (Hybrid)** ✅ RECOMMENDED

**Current file**: `src/vibe_check/schemas/scoring.py` (add new class)

```python
class PHQ8TotalScore(BaseModel):
    """Total score with full provenance."""

    # Raw discussed items
    discussed_count: int                 # How many of 8 items were discussed
    discussed_sum: int                   # Sum of scores for discussed items
    coverage: float                      # discussed_count / 8

    # Prorated (for comparability with standard PHQ-8)
    prorated_total: float | None         # (discussed_sum × 8) / discussed_count
    prorated_total_rounded: int | None   # Rounded to nearest int

    # Conservative (for downstream ML)
    imputed_total: int                   # Treat NA as 0, sum all
    na_count: int                        # How many items were NA

    # Validity flag
    is_valid: bool                       # discussed_count >= 4 (50% coverage minimum)
```

**Rationale**:
- Prorated for clinical comparability
- Imputed for ML (some models can't handle NA)
- Raw for full transparency
- Validity threshold prevents meaningless scores

### 12.3 Prompt Decision: **Clinical Inference Mode** ✅ RECOMMENDED

**Current file**: `src/vibe_check/scoring/prompting.py`

Replace frequency-based prompting with intensity-based clinical inference:

```markdown
You are a psychiatrist reviewing a therapy transcript to infer PHQ-8 symptom severity.

## CLINICAL CONTEXT
This is a synthetic therapy conversation. Assume the discussion reflects the patient's
recent state (approximately the last 2 weeks). Do NOT expect explicit PHQ-8 phrasing
like "more than half the days" or "in the last two weeks."

## SEVERITY INFERENCE (Intensity → Score)
Map the patient's language intensity to PHQ-8 severity:

| Intensity Markers | Score | Clinical Meaning |
|-------------------|-------|------------------|
| "a bit", "sometimes", "occasionally" | 1 | Several days |
| "often", "really", "a lot", "most days" | 2 | More than half the days |
| "always", "can't", "every day", "completely" | 3 | Nearly every day |
| "I'm fine", "no problems", explicit denial | 0 | Not at all (DENIED) |
| *(symptom domain not mentioned)* | null | Not discussed |

## CRITICAL: "NOT DISCUSSED" vs "DENIED"
- **DENIED (score=0)**: Patient explicitly says they DON'T have the symptom
  - Example: "My appetite is fine" → appetite: score=0, assertion="denied"

- **NOT DISCUSSED (score=null)**: Symptom domain never comes up
  - Example: Appetite never mentioned → appetite: score=null, assertion="not_mentioned"

⚠️ DO NOT score 0 for items that are simply not mentioned. Score 0 means DENIED.

## EVIDENCE REQUIREMENTS
- For scores 1-3: Quote patient language showing severity
- For score 0 (denied): Quote the denial statement
- For not discussed: Leave evidence empty, set assertion="not_mentioned"
```

**Rationale**:
- Matches how psychiatrists actually infer severity
- Explicit guidance prevents 0/NA conflation
- Intensity markers are learnable and consistent

### 12.4 HuggingFace Dataset Schema ✅ RECOMMENDED

**Current file**: `src/vibe_check/export/huggingface.py` (to be created)

For publishing to HuggingFace, use this schema (JSON Lines format):

```python
{
    "file_id": "active436",
    "condition": "mdd",  # Ground truth from corpus
    "split": "train",

    # Per-item scores (the primary value)
    "items": {
        "anhedonia": {"score": 2, "assertion": "present", "confidence": 0.85, "evidence": ["..."]},
        "depressed_mood": {"score": 3, "assertion": "present", "confidence": 0.92, "evidence": ["..."]},
        "sleep": {"score": 1, "assertion": "present", "confidence": 0.78, "evidence": ["..."]},
        "fatigue": {"score": null, "assertion": "not_mentioned", "confidence": null, "evidence": []},
        "appetite": {"score": null, "assertion": "not_mentioned", "confidence": null, "evidence": []},
        "guilt": {"score": 0, "assertion": "denied", "confidence": 0.88, "evidence": ["I don't blame myself"]},
        "concentration": {"score": 2, "assertion": "present", "confidence": 0.75, "evidence": ["..."]},
        "psychomotor": {"score": null, "assertion": "not_mentioned", "confidence": null, "evidence": []}
    },

    # Aggregated totals (secondary, derived)
    "totals": {
        "discussed_count": 5,
        "discussed_sum": 8,
        "coverage": 0.625,
        "prorated_total": 12.8,
        "prorated_total_rounded": 13,
        "imputed_total": 8,  # NA treated as 0
        "is_valid": true
    },

    # Provenance
    "scoring_metadata": {
        "prompt_version": "v2.0.0-clinical",
        "juror_models": ["gpt-5.2", "claude-sonnet-4.5", "gemini-3-pro"],
        "runs_per_model": 2,
        "arbitration_triggered": true,
        "judge_model": "claude-opus-4.5"
    }
}
```

---

## 13. Implementation Checklist

### 13.0 Files Affected (Complete List)

| File | Change Type | Description |
|------|-------------|-------------|
| `src/vibe_check/schemas/scoring.py` | **Major** | Add `assertion`, allow `score=None`, add `PHQ8TotalScore` |
| `src/vibe_check/scoring/prompting.py` | **Major** | Rewrite system prompt for clinical inference |
| `src/vibe_check/aggregation/posterior.py` | **Major** | Handle NA votes in Bayesian aggregation |
| `src/vibe_check/judge/prompting.py` | **Moderate** | Update judge to understand assertion semantics |
| `src/vibe_check/diagnostics/quality_gates.py` | **Moderate** | Add NA rate and coverage metrics |
| `src/vibe_check/export/labels.py` | **Moderate** | Export assertion field, handle NA |
| `src/vibe_check/export/huggingface.py` | **New** | Create HuggingFace export format |
| `tests/unit/test_scoring.py` | **Major** | Update tests for new schema |
| `tests/unit/test_aggregation.py` | **Major** | Test NA handling |

### 13.1 Schema Changes Required

- [ ] Update `PHQ8ItemScore` to allow `score: int | None`
- [ ] Add `assertion` field with clinical NLP values
- [ ] Update `PHQ8Report` to handle NA items in total
- [ ] Add `PHQ8TotalScore` with both prorated and imputed
- [ ] Update Pydantic validators for new schema

### 13.2 Prompt Changes Required

- [ ] Rewrite juror system prompt for clinical inference
- [ ] Add intensity → severity mapping table
- [ ] Add explicit NOT DISCUSSED vs DENIED guidance
- [ ] Update evidence requirements for each assertion type

### 13.3 Aggregation Changes Required

- [ ] Update posterior calculation to handle NA votes
- [ ] Update entropy calculation to exclude NA
- [ ] Add per-item `assertion` consensus
- [ ] Compute both prorated and imputed totals

### 13.4 Diagnostics Changes Required

- [ ] Add per-item NA rate reporting
- [ ] Add coverage distribution reporting
- [ ] Update separation test to handle NA
- [ ] Add assertion distribution reporting

---

## 14. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Jurors disagree on intensity→severity | High | Medium | Arbitration handles; report uncertainty |
| Most items are NA (low coverage) | Medium | High | Validity threshold; require ≥4 items |
| Prorated scores are biased (MNAR) | High | Medium | Report both prorated AND imputed |
| Downstream models can't handle NA | Medium | Medium | Provide imputed_total fallback |
| HuggingFace schema too complex | Low | Low | Provide flattened CSV alternative |

---

## 15. Sources

### 15.1 PHQ Scoring & Missing Data

| # | Source | Key Finding |
|---|--------|-------------|
| 1 | [APA DSM-5 Severity Measures - PHQ-A Instructions](https://www.psychiatry.org/File%20Library/Psychiatrists/Practice/DSM/APA_DSM5_Severity-Measure-For-Depression-Child-Age-11-to-17.pdf) | Official proration formula: `(Partial Sum × 8) ÷ Items Answered` |
| 2 | [PMC: Proration vs FIML for Missing Data](https://pmc.ncbi.nlm.nih.gov/articles/PMC4701045/) | Proration assumes MCAR; our case is MNAR → report both prorated AND imputed |
| 3 | [PMC: PHQ-9 Validation (Kroenke 2001)](https://pmc.ncbi.nlm.nih.gov/articles/PMC1495268/) | Original PHQ validation; severity cut-points |

### 15.2 Clinical NLP Standards

| # | Source | Key Finding |
|---|--------|-------------|
| 4 | [i2b2/VA Challenge (2010)](https://pmc.ncbi.nlm.nih.gov/articles/PMC3900128/) | Established assertion labels: present, absent, possible, hypothetical, past |
| 5 | [John Snow Labs: Clinical Assertion Annotation](https://www.johnsnowlabs.com/tips-and-tricks-on-how-to-annotate-assertion-in-clinical-texts/) | Practical annotation guidelines; no `not_mentioned` category (gap we fill) |

### 15.3 LLM Annotation Research

| # | Source | Key Finding |
|---|--------|-------------|
| 6 | [Nature npj Mental Health: LLM Psychiatric Detection (2025)](https://www.nature.com/articles/s44184-025-00175-1) | LLMs achieve 86.9% accuracy; forcing scores without evidence → hallucination |
| 7 | [PMC: LLM Psychiatric Interviews (2024)](https://pmc.ncbi.nlm.nih.gov/articles/PMC11544339/) | Symptom delineation research; validation methodology |
| 8 | [arXiv: Multi-Label Mental Health Annotation (Primate2022)](https://arxiv.org/html/2412.03796v1) | Precedent for LLM-based PHQ annotation from social media |

### 15.4 Dataset Publishing

| # | Source | Key Finding |
|---|--------|-------------|
| 9 | [GitHub: Mental Health Datasets Repository](https://github.com/kharrigian/mental-health-datasets) | Best practices: use `null` not sentinels, include confidence, report coverage |

---

## 16. Sign-Off

### 16.1 Author Attestation

| Role | Name | Date | Status |
|------|------|------|--------|
| Clinical Lead | [Double-Board Psychiatrist] | 2026-01-06 | ✅ Initial draft approved |
| Engineering Lead | Claude (Opus 4.5) | 2026-01-06 | ✅ Research & schema complete |

### 16.2 Senior Reviewer Sign-Off

| Checkpoint | Reviewer | Date | Status |
|------------|----------|------|--------|
| Clinical alignment validated | | | ⏳ Pending |
| Schema design approved | | | ⏳ Pending |
| Prompt rewrite approved | | | ⏳ Pending |
| Ready for implementation | | | ⏳ Pending |

### 16.3 Approval to Proceed

- [ ] **All reviewer questions answered (Section "Questions for Senior Reviewer")**
- [ ] **Schema changes approved**
- [ ] **Prompt rewrite approved**
- [ ] **Implementation can proceed**

---

## Version History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-06 | Clinical + Engineering | Initial comprehensive draft |
| 1.1 | 2026-01-06 | Engineering | Added executive summary, reviewer questions, file references, expanded sources |

---

*This document blocks all paid API scoring runs until senior review is complete and all checkboxes in Section 16.3 are checked.*
