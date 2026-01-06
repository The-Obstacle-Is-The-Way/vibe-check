# Clinical Alignment Review: PHQ-8 Scoring from Therapy Transcripts

> **Status**: APPROVED FOR PHASE 1 IMPLEMENTATION + PILOT — Paid scoring run remains blocked pending pilot diagnostics
> **Author**: Clinical (Double-Board Psychiatrist) + Engineering collaboration
> **Date**: 2026-01-06
> **Blocks**: All paid API scoring runs

---

## Executive Summary

**Problem**: The current vibe-check implementation scores PHQ-8 items using frequency-based logic ("several days", "more than half the days") that doesn't exist in therapy transcripts. Worse, score 0 conflates "patient denied symptom" with "symptom not mentioned"—a critical clinical error.

**Solution**: Align with how psychiatrists actually infer symptoms:
1. **Infer severity from intensity** ("I'm exhausted" → high severity) instead of expecting explicit frequency anchors
2. **Allow NA for undiscussed items** using a clinical-NLP-inspired assertion/coverage scheme (present/denied/possible/not_mentioned)
3. **Report both prorated AND imputed totals** since transcript missingness is likely **informative** (not MCAR) and totals are uncertain under partial evidence

**Key Change**: Add an explicit **no-evidence** state (`not_mentioned`) so “denied” (absent) is not conflated with “unknown.”

**Impact**: These changes are required before spending money on API calls. The current implementation would generate embeddings that encode incorrect patterns (frequency expectations, 0=not_mentioned conflation).

---

## Questions for Senior Reviewer

Before approving this document, please confirm:

1. [x] **Schema**: Is the `assertion` field (present/denied/possible/not_mentioned) the right clinical abstraction?
   - **Senior Reviewer Answer**: Yes, with two clarifications: (1) `denied` should be treated as clinical **negation/absent**, and (2) the prompt must explicitly enforce **experiencer** (client vs someone else) and **temporality** (current/recent vs historical) so we do not score non-target mentions as “present.”
2. [x] **Proration**: Is 50% coverage (≥4 items discussed) a reasonable validity threshold?
   - **Senior Reviewer Answer**: Not for PHQ-8 *comparability*; acceptable only as a **minimum-coverage gate** for research embeddings. For PHQ-like totals, use a stricter gate (see Section 11.1 / 12.2).
3. [x] **Intensity mapping**: Does the intensity→severity table (Section 12.3) match clinical judgment?
   - **Senior Reviewer Answer**: Directionally yes, but it over-weights bare intensifiers (e.g., “really”) and under-specifies recency/functional impact. Use the revised table + rules in Section 12.3.
4. [x] **"Possible" handling**: Should uncertain mentions (e.g., "maybe I've been a bit tired") be:
   - Scored as 1 with `assertion="possible"`, OR
   - Scored as NA with `assertion="possible"`?
   - **Senior Reviewer Answer**: Default to **score=1** with `assertion="possible"` *when the symptom domain is clearly referenced* but hedged; use `score=null` only when the statement is too vague to ground the domain/timeframe.
5. [x] **Judge behavior**: Should the judge be able to override a juror's `not_mentioned` if evidence exists?
   - **Senior Reviewer Answer**: Yes, but only when the judge can cite **explicit textual evidence**; otherwise, keep `not_mentioned` to avoid invention.

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

> **A psychiatrist infers severity from narrative evidence (recency + persistence + intensity + functional impact), not literal day counts.**

| Patient says | Psychiatrist infers | PHQ-8 equivalent |
|--------------|---------------------|------------------|
| "I've been really tired lately" | Fatigue present; severity depends on persistence/impact | Score 1-2 (sometimes 3 if pervasive) |
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
┌──────────────────────────────────────────────────────────────────────────────┐
│                         FULL RESEARCH PIPELINE                               │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  SQPsychConv (synthetic)              DAIC-WOZ (real)                        │
│  2,090 dialogues                      189 clinical interviews                │
│         │                                    │                               │
│         ▼                                    │                               │
│  ┌──────────────────────┐                    │                               │
│  │ vibe-check           │                    │                               │
│  │ PHQ-8 scoring        │                    │                               │
│  │ (NA-aware labels)    │                    │                               │
│  └──────────┬───────────┘                    │                               │
│             │                                │                               │
│             ▼                                │                               │
│  ┌──────────────────────┐                    │                               │
│  │ ai-psychiatrist      │                    │                               │
│  │ Train embeddings on  │                    │                               │
│  │ labeled SQPsychConv  │                    │                               │
│  └──────────┬───────────┘                    │                               │
│             │                                │                               │
│             ▼                                ▼                               │
│  ┌───────────────────────────────────────────────────────────────┐           │
│  │ TRANSFER: Apply embeddings to predict PHQ-8 on DAIC-WOZ       │           │
│  │           (zero-shot or few-shot, NO training on DAIC-WOZ)    │           │
│  └───────────────────────────────────────────────────────────────┘           │
│                                                                              │
│  VALIDATION: Do synthetic-trained embeddings generalize to real interviews?  │
│                                                                              │
│  ⚠️ DOMAIN SHIFT RISK: If coverage patterns differ (e.g., SQPsychConv       │
│     discusses 6/8 items, DAIC-WOZ discusses 4/8), missingness becomes        │
│     a spurious signal. Solution: Analyze both corpora BEFORE scoring.        │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 What's NOT Cheating (Legitimate DAIC-WOZ Use During Development)

| Legitimate Use | Why It's OK |
|----------------|-------------|
| Analyzing DAIC-WOZ **coverage patterns** | Understanding structure, not leaking labels |
| Checking transcript **formatting differences** | Preprocessing alignment, not outcome tuning |
| Validating NA-aware schema **works on real data** | Schema robustness, not label fitting |
| Comparing **item discussion rates** across corpora | Domain shift detection, not training |

| What WOULD Be Cheating | Why It's Wrong |
|------------------------|----------------|
| Using DAIC-WOZ labels to tune vibe-check prompts | Leaks ground truth into labeling process |
| Training ai-psychiatrist on DAIC-WOZ | Defeats the transfer learning validation |
| Selecting SQPsychConv dialogues to match DAIC-WOZ distribution | Cherry-picking, not generalizing |

### 4.3 Why Alignment Matters

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
- `score=0, discussed=True, assertion="denied"` → Patient said "I'm sleeping fine"
- `score=None, discussed=False, assertion="not_mentioned"` → Sleep never came up (no evidence)
- `score=2, discussed=True, assertion="present"` → Patient described moderate sleep issues

### 5.2 Prompt Rewrite: Clinical Inference Mode

**Current prompt focus**: Frequency mapping
**Proposed prompt focus**: Clinical severity inference

> **Note**: This is an early sketch. The **approved** prompt language is in **Section 12.3** (includes ConText-style rules and a more defensible severity table).

```markdown
You are a psychiatrist reviewing a therapy transcript to infer PHQ-8 symptom severity.

CLINICAL INFERENCE GUIDELINES:
1. TIMEFRAME: Assume the conversation reflects the patient's recent state (last ~2 weeks).
   Do NOT expect explicit "in the last two weeks" language.

2. CONTEXT (ConText-style):
   - Experiencer: score only if attributed to the CLIENT (not family/others)
   - Temporality: score current/recent symptoms; exclude purely historical/resolved
   - Hypothetical/conditional: do not score "what if/if it happens" statements as current

3. SEVERITY INFERENCE (Evidence → Score):
   - Prefer explicit frequency cues when present ("most days", "every day")
   - Otherwise approximate using persistence + intensity + functional impact
   - Do NOT up-score to 2–3 solely on bare intensifiers (e.g., "really") without persistence/impact
   - Explicit denial → Score 0 (assertion="denied")

4. NOT MENTIONED vs DENIED:
   - If no evidence for CLIENT+timeframe → score=null, assertion="not_mentioned", confidence=null
   - If explicitly denied → score=0, assertion="denied"
   - If mentioned but hedged → score=1, assertion="possible" (unless too vague → not_mentioned)

5. EVIDENCE REQUIREMENT:
   - For scores 1-3 and "possible": quote client language that supports the inference
   - For denied: quote the denial
   - For not_mentioned: evidence=[]
```

### 5.3 Total Score Handling with NA Items

If items can be NA, how do we compute total score?

**Option A: Prorated scoring**
```python
# Only sum discussed items, scale to 0-24
discussed_items = [s for s in scores if s.discussed]
if len(discussed_items) >= 7:  # Strict gate (≤1 NA) for PHQ-like comparability
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
| Score 0 conflates "denied" and "not mentioned" | ✅ Addressed | NA-aware schema + explicit rules |
| Prompts expect frequency anchors | ✅ Addressed | Clinical inference prompt (Section 12.3) |
| Total score undefined with NA items | ✅ Decided | Hybrid totals + strict proration gate (≥7) |
| Juror disagreement on intensity→severity mapping | ⚠️ Expected | Arbitration handles |
| Appetite/psychomotor rarely discussed | ✅ Known | Will mostly be NA |
| Other-experiencer / historical / hypothetical mentions | ⚠️ High-risk | ConText-style rules + judge evidence requirement |
| Legacy int-only exports reintroduce NA confusion | ⚠️ High-risk | Treat SPEC-08 as legacy/imputed; use NA-aware exporter for research |
| Coverage shift (SQPsychConv ↔ DAIC-WOZ) | ⚠️ High-risk | Pre-scoring corpus comparison (Section 12.6) |
| Therapist text leaks condition | ✅ Mitigated | Use client_only view |
| file_id encodes condition | ✅ Mitigated | Not in prompts |
| No explicit timeframe in transcripts | ✅ Addressed | Prompt assumes recent |

---

## 8. Decision Points Before Running

### 8.1 Must Decide

- [x] **Schema change**: Add `assertion` + allow `score=None` with `confidence=None` when NA (Section 12.1)
- [x] **Total score method**: Report hybrid totals; gate proration at high coverage (Sections 12.2 / 11.1)
- [x] **Prompt rewrite**: Switch from frequency anchors to clinical inference with ConText-style rules (Section 12.3)
- [x] **Export strategy**: Keep SPEC-08 stable; add separate NA-aware exporter (Section 12.5)
- [x] **Domain shift**: Run SQPsychConv vs DAIC-WOZ coverage analysis before paid scoring (Section 12.6)

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

### 11.1 PHQ-8 Missing Items & Proration (What’s “Official,” What Transfers, What Doesn’t)

**PHQ-8 (self-report) scoring guidance is strict about missingness.** For example, an NIH PHQ-8 case report form states:

> “Score is the sum of the 8 items. **If more than 1 item missing, set the value of the scale to missing.**”
> — [NIH HEAL PHQ-8 CRF](https://heal.nih.gov/files/CDEs/2023-06/patient-health-questionnaire-8-crf.docx)

**Proration exists in closely related PHQ-9 derivatives, but only for small amounts of missingness.** The APA DSM-5TR “Severity Measure for Depression—Adult” (PHQ-9 adapted) states that when 1–2 items are unanswered, compute:

> “Multiply the partial raw score by the total number of items … and divide … by the number of items that were actually answered … If the result is a fraction, round to the nearest whole number.”
> — [APA DSM-5TR Severity Measure for Depression—Adult](https://www.psychiatry.org/getmedia/a3986be5-94af-42e7-afce-19234c2f4998/APA-DSM5TR-SeverityMeasureForDepressionAdult.pdf)

**Critical transfer note for transcripts**: Our “NA” is *not* item nonresponse; it is **no evidence in the conversation**. This is not “missing at random,” and it is not the same construct as PHQ item nonresponse. Therefore:
- Treat `prorated_total` as an **auxiliary, high-variance comparability feature**, not a gold-standard PHQ total.
- Gate proration strictly (recommend: only compute `prorated_total` when `discussed_count >= 7`).

### 11.2 Clinical NLP Assertion Annotation Standards

From [i2b2/VA Challenge (2010)](https://pmc.ncbi.nlm.nih.gov/articles/PMC3168320/), [ConText](https://pmc.ncbi.nlm.nih.gov/articles/PMC2757457/), and practitioner summaries (e.g., [John Snow Labs](https://www.johnsnowlabs.com/tips-and-tricks-on-how-to-annotate-assertion-in-clinical-texts/)):

Standard assertion labels in clinical NLP:

| Label | Meaning | Example |
|-------|---------|---------|
| **Present** | Entity is affirmed | "Patient has insomnia" |
| **Absent** | Entity is negated | "Denies insomnia" |
| **Possible** | Uncertainty expressed | "May have insomnia" |
| **Conditional / Hypothetical** | Not currently asserted | "If insomnia worsens..." |
| **Other experiencer** | Not about the patient | "Mother has insomnia" |
| **Past / Historical** | Not current | "History of insomnia" |

**Key point for this project**: i2b2-style assertion classification assumes the concept mention is already extracted (“Assertion classification was run on reports annotated with the reference standard concepts…”). In our task, we must also represent **lack of evidence** for a predefined PHQ domain.

**Our extension**: Add a **no-evidence/not-mentioned** state for each PHQ item to avoid conflating “denied” with “unknown.” This is justified for transcript-based inference, but should be described as an **annotation-coverage construct**, not a core i2b2 assertion label.

### 11.3 Mental Health Dataset Publishing Standards

There is no single “mental health dataset publishing standard.” For release and reuse hygiene, follow general dataset documentation norms (e.g., datasheets and dataset cards), plus mental-health–specific risk considerations (privacy, misuse, clinical over-interpretation).

Recommended practices for this project’s exports:

1. **Explicit missing indicators**: Use `null`/`None` rather than sentinel values like `-1`
2. **Confidence scores**: Include annotator confidence alongside labels
3. **Coverage metrics**: Report what % of items have labels
4. **Multi-annotator data**: Preserve disagreement, don't just report consensus
5. **Annotation guidelines**: Publish the exact instructions given to annotators

Even though SQPsychConv is synthetic, include a dataset card that clearly states: synthetic provenance, intended use (research), and known failure modes (coverage shift vs DAIC-WOZ, intensity→frequency approximation).

### 11.4 LLM Psychiatric Annotation Research

From [Nature npj Mental Health (2025)](https://www.nature.com/articles/s44184-025-00175-1) and [PMC LLM Psychiatric Interviews](https://pmc.ncbi.nlm.nih.gov/articles/PMC11544339/):

| Finding | Implication |
|---------|-------------|
| Fine-tuning improved symptom-extraction accuracy to **86.9%** (and recall up to **81.1%** on the test set; **86.1%** on a “high-quality EMR” subset) | LLM psychiatric labeling can be viable with calibration |
| Fine-tuned GPT-3.5 achieved **0.817 accuracy** in multiclass symptom-label classification in a pilot delineation pipeline | Multi-stage LLM pipelines can produce clinically useful intermediate labels |
| Both papers emphasize workflow integration and limitations (generalizability, labeling quality, evaluation setting) | Our pilot + diagnostics are necessary before full-scale runs |

**Key insight for our design**: Forced-choice scoring when evidence is absent increases confabulation risk. Allowing an explicit no-evidence state is both clinically defensible and operationally safer.

### 11.5 Addressing Item-Level Missing Data (PMC Research)

From [PMC Proration vs FIML Study](https://pmc.ncbi.nlm.nih.gov/articles/PMC4701045/):

> "Often when participants have missing scores on one or more items comprising a scale, researchers compute prorated scale scores by averaging the available items. Methodologists have cautioned that proration may make strict assumptions about the missing data mechanisms."

**Translation**: Proration can be biased even under MCAR (e.g., when item means/covariances differ), and it becomes more problematic as missingness increases. Our “NA” mechanism is also plausibly **informative** (people are more likely to mention severe symptoms), so treat totals derived from partial evidence as uncertain.

**Recommendation**:
- Always export `discussed_count`, `na_count`, and per-item assertions.
- Compute `prorated_total` only when coverage is high (recommend: `discussed_count >= 7`).
- Prefer downstream models that can consume **masked per-item vectors** over relying on a single total score.

---

## 12. Final Recommendations (Evidence-Based)

### 12.1 Schema Decision: **Use NA-Aware Schema** ✅ RECOMMENDED

**Current file**: `src/vibe_check/schemas/scoring.py`

```python
class PHQ8ItemScore(BaseModel):
    """Single PHQ-8 item score with clinical annotation semantics."""

    discussed: bool                      # Is there evidence about the CLIENT's recent (≈2wk) status for this item?
    score: Literal[0, 1, 2, 3] | None   # None if no evidence (not discussed / not scorable)
    assertion: Literal[                  # Clinical-NLP-inspired label (extended with "not_mentioned")
        "present",      # Symptom affirmed (score 1-3)
        "denied",       # Symptom explicitly denied (score 0)
        "possible",     # Uncertain/hedged affirmation (default score 1 unless too vague to score)
        "not_mentioned" # No evidence in transcript for CLIENT+timeframe (score=None)
    ]
    confidence: float | None             # 0.0-1.0; use null when score is null
    evidence: list[str]                  # Up to 3 supporting quotes
```

**Assertion Values Explained**:

| Assertion | Score | When to Use | Example |
|-----------|-------|-------------|---------|
| `present` | 1-3 | Patient clearly describes symptom | "I can't sleep at all" |
| `denied` | 0 | Patient explicitly denies symptom | "My appetite is fine" |
| `possible` | 1 | Uncertain or hedged mention | "Maybe I've been a bit tired" |
| `not_mentioned` | None | No evidence for CLIENT+timeframe | *(sleep never discussed as current for client)* |

**Note on `possible` (Reviewer Q4)**: Default `possible` to **score=1** (low severity) *only when* the client clearly refers to the symptom domain but hedges intensity/frequency. If the language is too vague to identify the domain (or is purely hypothetical/past/other-experiencer), use `not_mentioned` with `score=null`.

**Rationale**:
- Mirrors core clinical NLP “assertion/ConText” concepts (negation, uncertainty, experiencer, temporality)
- Prevents forced hallucination
- Preserves full information for downstream use
- `not_mentioned` is a justified coverage state for transcript-based inference (not an i2b2-native label)

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
    prorated_total: float | None         # Only if discussed_count >= 7 (<=1 NA)
    prorated_total_rounded: int | None   # Rounded to nearest int (when prorated_total is set)

    # Conservative (for downstream ML)
    imputed_total: int                   # Treat NA as 0, sum all
    na_count: int                        # How many items were NA

    # Validity flags
    is_min_coverage: bool                # discussed_count >= 4 (embedding minimum, not “PHQ comparable”)
    is_proration_valid: bool             # discussed_count >= 7 (PHQ-like total is minimally defensible)
```

**Rationale**:
- Prorated only when coverage is high (PHQ comparability gate)
- Imputed for ML (some models can't handle NA)
- Raw for full transparency
- Separate flags prevent “50% coverage” from being misread as clinically equivalent to PHQ completion

### 12.3 Prompt Decision: **Clinical Inference Mode** ✅ RECOMMENDED

**Current file**: `src/vibe_check/scoring/prompting.py`

Replace frequency-based prompting with intensity-based clinical inference:

```markdown
You are a psychiatrist reviewing a therapy transcript to infer PHQ-8 symptom severity.

## TARGET TIMEFRAME
Infer the client's symptom burden over the recent period (≈ last 2 weeks), **unless the transcript clearly anchors a different timeframe**.
- If a symptom is clearly described as *historical* or *resolved*, do not score it as current.

## CONTEXT RULES (ConText-style)
- **Experiencer**: Score symptoms only if attributed to the **CLIENT** (not family/others).
- **Temporality**: Prefer current/recent symptoms; exclude purely historical mentions.
- **Hypothetical/conditional**: Do not treat “what if / if it happens” statements as evidence of current symptoms.
- **Negation**: Explicit denial counts as evidence for score 0.

## SEVERITY INFERENCE (Evidence → Score)
Prefer **explicit frequency cues** when present (e.g., "every day", "most nights"). Otherwise, approximate using **persistence + intensity + functional impact**. Do not up-score to 2–3 solely on bare intensifiers (e.g., "really") without persistence/impact.

| Evidence pattern | Score | Practical cue |
|-----------------|-------|---------------|
| Mild / intermittent, minimal impact | 1 | "sometimes", "a bit", "here and there" |
| Frequent/persistent *or* moderate impact | 2 | "often", "most days", "regularly", clear disruption |
| Near-daily/persistent *and* severe impact | 3 | "every day/nearly every day", "can't function", pervasive impairment |
| Explicit denial of the symptom | 0 | "I'm sleeping fine", "my appetite is good" |
| No evidence for CLIENT+timeframe | null | not discussed / not scorable |

## CRITICAL: "NOT DISCUSSED" vs "DENIED"
- **DENIED (score=0)**: Patient explicitly says they DON'T have the symptom
  - Example: "My appetite is fine" → appetite: score=0, assertion="denied"

- **NOT MENTIONED / NO EVIDENCE (score=null)**: No evidence for the symptom domain for the CLIENT in the target timeframe
  - Example: Sleep never discussed as a current client issue → sleep: score=null, assertion="not_mentioned"

⚠️ DO NOT score 0 for items that are simply not mentioned. Score 0 means DENIED.

## EVIDENCE REQUIREMENTS
- For scores 1-3 (`present`) and score 1 (`possible`): Quote client language supporting the inference
- For score 0 (`denied`): Quote the denial statement
- For score=null (`not_mentioned`): Leave evidence empty, set confidence=null

## OUTPUT RULES
- Use ONLY the provided transcript. Do not invent symptoms or frequency.
- If you cannot justify a score with text, output score=null with assertion="not_mentioned".
```

**Rationale**:
- Matches how psychiatrists actually infer severity
- Explicit guidance prevents 0/NA conflation
- Intensity markers are learnable and consistent

### 12.4 HuggingFace Dataset Schema ✅ RECOMMENDED

**Current files**: `src/vibe_check/export/schemas.py`, `src/vibe_check/export/writer.py`

**Important**: The existing export is described as a stable public contract (SPEC-08). Implement this HuggingFace-style export as:
- A **separate optional exporter** (new module), or
- A **versioned** export contract (do not silently change existing field types from `int` to `int|null`).

For publishing to HuggingFace, use this schema (JSON Lines format):

```python
{
    "dialogue_id": "active436",
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
        "prorated_total": null,          # only when discussed_count >= 7
        "prorated_total_rounded": null,  # only when discussed_count >= 7
        "imputed_total": 8,  # NA treated as 0
        "na_count": 3,
        "is_min_coverage": true,
        "is_proration_valid": false
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

### 12.5 Export Strategy: **Separate NA-Aware Exporter** ✅ DECIDED

**Decision**: Create a NEW export module for NA-aware HuggingFace format. Do NOT modify SPEC-08.

**Pitfall / clarification**:
- Any **int-only** export necessarily **imputes** or **drops** the no-evidence state. Treat SPEC-08 outputs as **legacy/imputed** and do not use them as the primary artifact for embedding training or clinical interpretation.
- The NA-aware HuggingFace export (Section 12.4) is the **canonical research export** for this project.

**Rationale**:
- SPEC-08 is a stable public contract (integers only)
- Breaking changes would affect any downstream consumers
- Separate exporter allows versioned evolution

**Implementation**:
```
src/vibe_check/export/
├── schemas.py          # SPEC-08 (unchanged, int-only)
├── writer.py           # SPEC-08 writer (unchanged)
├── validator.py        # SPEC-08 validator (unchanged)
├── huggingface.py      # NEW: NA-aware HuggingFace export
└── huggingface_schema.py  # NEW: NA-aware schema (Section 12.4)
```

### 12.6 Domain Shift Mitigation: **Pre-Scoring Corpus Analysis** ✅ DECIDED

**Decision**: Before running paid scoring, analyze BOTH SQPsychConv AND DAIC-WOZ to understand coverage patterns.

**Analysis checklist** (programmatic, no label leakage):
- [ ] Transcript length distribution (tokens/words)
- [ ] Speaker turn counts
- [ ] Keyword heuristics for PHQ-8 items (sleep, appetite, energy, etc.)
- [ ] Estimated "discussability" per item
- [ ] Formatting differences (speaker labels, timestamps, etc.)

**Purpose**: Detect if coverage patterns differ significantly. If SQPsychConv covers 6/8 items on average and DAIC-WOZ covers 4/8, we need to:
1. Document this as a known limitation
2. Ensure embeddings don't over-encode missingness as signal
3. Consider masked per-item representations over totals

**Location for analysis**: `scripts/corpus_comparison.py` (to be created)

---

## 13. Implementation Checklist

### 13.0 Files Affected (Complete List)

| File | Change Type | Description |
|------|-------------|-------------|
| `src/vibe_check/schemas/scoring.py` | **Major** | Add `assertion`, allow `score=None`, add `PHQ8TotalScore` |
| `src/vibe_check/scoring/prompting.py` | **Major** | Rewrite system prompt for clinical inference |
| `src/vibe_check/aggregation/posterior.py` | **Major** | Treat NA votes as missing for score posteriors; track `not_mentioned` separately |
| `src/vibe_check/aggregation/aggregate.py` | **Moderate** | Propagate NA-aware per-item consensus + totals |
| `src/vibe_check/judge/prompting.py` | **Moderate** | Update judge to understand assertion semantics |
| `src/vibe_check/diagnostics/report.py` | **Moderate** | Add NA rate, coverage, and assertion distribution metrics |
| `src/vibe_check/export/schemas.py` | **None** | SPEC-08 unchanged (int-only contract preserved) |
| `src/vibe_check/export/writer.py` | **None** | SPEC-08 writer unchanged |
| `src/vibe_check/export/validator.py` | **None** | SPEC-08 validator unchanged |
| `src/vibe_check/export/huggingface.py` | **New** | NA-aware HuggingFace export (separate from SPEC-08) |
| `src/vibe_check/export/huggingface_schema.py` | **New** | NA-aware schema for HuggingFace format |
| `scripts/corpus_comparison.py` | **New** | Pre-scoring analysis of SQPsychConv vs DAIC-WOZ |
| `tests/unit/test_schemas_scoring.py` | **Major** | Update tests for new juror output schema |
| `tests/unit/test_posterior.py` | **Major** | Test NA handling in posterior math |
| `tests/unit/test_huggingface_export.py` | **New** | Test NA-aware HuggingFace export |

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
- [ ] Add ConText-style rules: experiencer + temporality + hypothetical/conditional exclusions
- [ ] Update evidence requirements for each assertion type

### 13.3 Aggregation Changes Required

- [ ] Treat NA votes as missing for 0–3 score posterior; separately compute `p_not_mentioned` per item
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
| Most items are NA (low coverage) | Medium | High | Export `coverage`/`na_count`; use masked features; treat prorated totals as optional and gated (≥7 items) |
| Prorated scores are biased under realistic assumptions | High | Medium | Compute proration only at high coverage; treat as auxiliary feature, not ground truth |
| Coverage distribution shifts (SQPsychConv ↔ DAIC-WOZ) | Medium | High | Pilot on both corpora; avoid over-encoding “missingness style” as signal; report per-item NA rates by corpus |
| Legacy int-only exports misused as “clinically aligned” labels | Medium | High | Mark SPEC-08 as legacy/imputed; make NA-aware export the canonical research artifact |
| Severity buckets/cutpoints misinterpreted under partial/imputed totals | Medium | Medium | Compute clinical buckets only when proration is valid; otherwise label as ML-only proxy (or omit) |
| Downstream models can't handle NA | Medium | Medium | Provide imputed_total fallback |
| HuggingFace schema too complex | Low | Low | Provide flattened CSV alternative |

---

## 15. Sources

### 15.1 PHQ Scoring & Missing Data

| # | Source | Key Finding |
|---|--------|-------------|
| 1 | [NIH HEAL: PHQ-8 CRF](https://heal.nih.gov/files/CDEs/2023-06/patient-health-questionnaire-8-crf.docx) | PHQ-8 total is sum of 8 items; if >1 item is missing, set scale to missing |
| 2 | [APA DSM-5TR: Severity Measure for Depression—Adult (PHQ-9 adapted)](https://www.psychiatry.org/getmedia/a3986be5-94af-42e7-afce-19234c2f4998/APA-DSM5TR-SeverityMeasureForDepressionAdult.pdf) | Proration formula when 1–2 items are unanswered; round fraction to nearest whole |
| 3 | [PubMed: PHQ-8 as a measure of current depression (Kroenke 2009)](https://pubmed.ncbi.nlm.nih.gov/18752852/) | Establishes PHQ-8 as a validated measure of current depression in population settings |
| 4 | [PMC: Proration vs FIML for Missing Data](https://pmc.ncbi.nlm.nih.gov/articles/PMC4701045/) | Proration can be biased even under MCAR; discusses FIML alternatives |
| 5 | [PMC: PHQ-9 Validation (Kroenke 2001)](https://pmc.ncbi.nlm.nih.gov/articles/PMC1495268/) | PHQ validation and severity conventions (PHQ-9) |

### 15.2 Clinical NLP Standards

| # | Source | Key Finding |
|---|--------|-------------|
| 6 | [i2b2/VA Challenge (2010)](https://pmc.ncbi.nlm.nih.gov/articles/PMC3168320/) | Assertion task categories include present, absent, possible, conditional, hypothetical, and other experiencer |
| 7 | [PMC: ConText (2009)](https://pmc.ncbi.nlm.nih.gov/articles/PMC2757457/) | Negation + experiencer + temporality framing for clinical concepts |
| 8 | [John Snow Labs: Clinical Assertion Annotation](https://www.johnsnowlabs.com/tips-and-tricks-on-how-to-annotate-assertion-in-clinical-texts/) | Practitioner-oriented assertion label inventories and heuristics |

### 15.3 LLM Annotation Research

| # | Source | Key Finding |
|---|--------|-------------|
| 9 | [Nature npj Mental Health: LLM symptom extraction + classification (2025)](https://www.nature.com/articles/s44184-025-00175-1) | Fine-tuning improved symptom extraction accuracy to 86.9% with large recall gains |
| 10 | [PMC: Aligning LLMs for Psychiatric Interviews (2024)](https://pmc.ncbi.nlm.nih.gov/articles/PMC11544339/) | Pilot symptom delineation/summarization pipeline; performance depends on labeling quality |

### 15.4 Dataset Publishing

| # | Source | Key Finding |
|---|--------|-------------|
| 11 | [arXiv: Datasheets for Datasets](https://arxiv.org/abs/1803.09010) | Standard dataset documentation template for provenance, intended use, and limitations |
| 12 | [HuggingFace Dataset Cards](https://huggingface.co/docs/datasets/dataset_card) | Practical conventions for dataset metadata and responsible-use documentation |

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
| Clinical alignment validated | Senior ML Reviewer (Clinical NLP) | 2026-01-06 | ✅ Approved (for implementation + pilot) |
| Schema design approved | Senior ML Reviewer (Clinical NLP) | 2026-01-06 | ✅ Approved (see Sections 12.1–12.2) |
| Prompt rewrite approved | Senior ML Reviewer (Clinical NLP) | 2026-01-06 | ✅ Approved (see Section 12.3) |
| Ready for implementation | Senior ML Reviewer (Clinical NLP) | 2026-01-06 | ✅ Approved (Phase 1 + Phase 2 pilot) |

### 16.3 Approval to Proceed

- [x] **All reviewer questions answered (Section "Questions for Senior Reviewer")**
- [x] **Schema changes approved**
- [x] **Prompt rewrite approved**
- [x] **Implementation can proceed (Phase 1 + Phase 2 pilot)**
- [ ] **Paid scoring run approved (only after pilot diagnostics meet gates)**

---

## Version History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-06 | Clinical + Engineering | Initial comprehensive draft |
| 1.1 | 2026-01-06 | Engineering | Added executive summary, reviewer questions, file references, expanded sources |
| 1.2 | 2026-01-06 | Senior ML Reviewer | Corrected citations (i2b2/proration), tightened proration gates, added ConText-style prompt rules, aligned checklist to repo |
| 1.3 | 2026-01-06 | Engineering | Added: pipeline diagram (4.1), cheating vs legitimate use table (4.2), export strategy decision (12.5), domain shift mitigation plan (12.6), updated files list |

---

*This document blocks all paid API scoring runs until senior review is complete and all checkboxes in Section 16.3 are checked.*
