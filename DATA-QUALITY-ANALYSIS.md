# SQPsychConv qwen-2.5 Data Quality Analysis

> First-principles analysis of data/sqpsychconv/qwen-2.5 corpus
> Date: 2026-01-04

---

## Executive Summary

The corpus is **structurally clean and parseable** for PHQ-8 scoring, but PHQ-8 **labeling feasibility is conditional** once you account for (a) sparse direct evidence for some items (notably appetite/psychomotor) and (b) **therapist prompt leakage risk** if therapist turns are included in the scoring text.

The raw corpus also contains minor bracketed generation artifacts, but these are now stripped deterministically during preprocessing (SPEC-12) to avoid token waste and potential LLM confusion.

**Verdict**: Run a small pilot first; default to `client_only` for labeling; treat `client_qa` as an ablation (costlier + higher leakage surface).

---

## 1. Corpus Statistics

| Metric | Value |
|--------|-------|
| Total dialogues | 2,090 |
| MDD condition | 912 (43.6%) |
| Control condition | 1,178 (56.4%) |
| Client model | qwen-2.5 (100%) |
| Train/Dev/Test split | 1,685 / 206 / 199 |

### Token Estimates (client_qa view)

Approximate token counts (tiktoken `cl100k_base`):

| Stat | View Text Only | + Juror System Prompt |
|------|----------------|------------------------|
| Min | ~616 | ~1,109 |
| Max | ~3,032 | ~3,525 |
| Mean | ~1,306 | ~1,799 |
| Median | ~1,240 | ~1,733 |

Notes:
- 1 dialogue exceeds 3,000 tokens for view text alone; 16 exceed 3,000 when including the juror system prompt.
- Providers tokenize differently; these are for order-of-magnitude budgeting.

---

## 2. P2 Issues - Generation Artifacts (Fixed in Preprocessing)

Note: counts below refer to the **raw corpus**; preprocessing now strips these artifacts (SPEC-12).

### 2.1 `[/END]` Termination Marker

**Severity**: P2 (wastes tokens, potential confusion)

| Finding | Count |
|---------|-------|
| Dialogues with `[/END]` | 2,090 (100%) |
| Total occurrences | 2,492 |
| Mid-dialogue occurrences | 400 dialogues |

**Example (mid-dialogue)**:
```
Therapist: Looking forward to our next session. [/END]
Client: Thanks, I appreciate it.
```

**Impact**: ~5 wasted tokens per dialogue × 2,090 = ~10,450 tokens. More importantly, `[/END]` in therapist turns gets included in `client_qa` view and sent to jurors.

**Status**: Stripped during preprocessing (SPEC-12).

---

### 2.2 Template Placeholders Not Filled

**Severity**: P2 (data quality, potential LLM confusion)

Counts below are **occurrences** of common bracketed placeholders (case-insensitive; capitalization variants aggregated).

| Placeholder | Count (occurrences) |
|-------------|-------|
| `[insert preferred date]` | 57 |
| `[insert date]` | 43 |
| `[insert date and time]` | 28 |
| `[insert date here]` | 27 |
| `[Client's Name]` | 16 |
| `[next available date]` | 16 |
| `[next available date and time]` | 1 |
| `[insert time]` | 8 |
| `[insert preferred time]` | 9 |
| `[Therapist's Name]` | 6 |
| Other patterns | 83 unique raw strings (73 case-folded) (non-`[/END]`) |
| **Total bracket artifacts** | **2,984** |

Notes:
- “Total bracket artifacts” counts **all** bracketed segments, including `[/END]` (2,492 occurrences) + 492 other bracketed segments.

**Example**:
```
Therapist: Hello, Mr. [Client's Name]. How are you feeling today?
```

**Impact**: Clearly synthetic, could confuse LLMs scoring for depression symptoms.

**Status**: Stripped during preprocessing (SPEC-12).

---

### 2.3 LLM Roleplay Meta-Actions

**Severity**: P3 (minor, but unnecessary)

Counts below are **occurrences** (not dialogues).

| Pattern | Count (occurrences) |
|---------|-------|
| `[Keep silent]` | 11 |
| `[Pause and say nothing]` | 11 |
| `[No reply]` | 8 |
| `[Quiet]` | 2 |

**Example**:
```
Client: [Quiet]
```

**Impact**: These are not clinical content. Now stripped during preprocessing (SPEC-12).

---

## 3. P3 Issues - Minor/Cosmetic (No Action Needed)

### 3.1 Curly Quotes (Unicode)

**Severity**: P3 (no action needed)

- 2,089/2,090 dialogues use U+2019 (right single quotation mark) as apostrophe
- 350 curly double-quote characters (U+201C/U+201D) (≈175 paired quotes)
- 374 em-dashes (U+2014)

**Impact**: NONE. Modern LLMs handle Unicode fine. JSON round-trips 100% successfully.

---

### 3.2 Asterisk Actions

**Severity**: P3 (semantically meaningful, keep)

- 36 dialogues have asterisk roleplay markers in client text

**Examples**:
```
Client: Okay, I'll try. *takes a deep breath* It does feel a bit better already.
Client: *pauses* It's hard to focus, but I'm trying to breathe deeply.
Client: *exhales deeply* It's a bit easier now.
```

**Impact**: These are **semantically meaningful** for PHQ-8 scoring:
- `*pauses*` could indicate psychomotor slowing
- `*takes a deep breath*` could indicate fatigue/anxiety management
- They reflect client emotional state

**Recommendation**: KEEP as-is. These are valid evidence snippets.

---

### 3.3 Chinese Characters

**Severity**: P2 (rare but notable)

- 4 dialogues contain Chinese characters
- 3 in therapist turns only ("沉重" = "heavy/weighed down")
- **1 in client turn** (control891)

**Example (control891 - client turn)**:
```
When I think, "I'll never get this done in time," I feel really anxious
and overwhelmed. My heart starts racing, and I feel a knot in my stomach.
It's like everything gets放大了，变得不可逾越。但我知道这些想法并不真实，
我需要找到一种方法来平衡它们。
```

Translation: "It's like everything gets magnified, becoming insurmountable. But I know these thoughts aren't real, I need to find a way to balance them."

**Impact**:
- Only 1 dialogue (0.05%) has Chinese in client text
- The Chinese is coherent and clinically relevant (describes anxiety)
- LLMs (especially Qwen-based jurors if used) will understand it
- This is a control condition dialogue, not MDD

**Recommendation**: Flag for awareness. No immediate fix needed.

---

## 4. No Issues Found (Validated Clean)

| Check | Result |
|-------|--------|
| JSON round-trip | 0 failures (2,090/2,090 clean) |
| Speaker format | 100% correct ("Therapist:", "Client:") |
| Empty dialogues | 0 |
| Missing client text | 0 |
| Malformed lines | 0 |
| Unknown speakers | 0 |
| Orphan lines | 0 |
| Truncated utterances | 0 |
| Meta text removed | 0 |
| Control characters | 0 |
| NULL bytes | 0 |

The preprocessing pipeline (`src/vibe_check/preprocessing/extractor.py`) handles all edge cases correctly - the data is well-structured at the parse level.

---

## 5. Recommendations

### 5.1 Before Production (P2 Fixes)

**Option A: Fix Preprocessing** (Implemented)
1. Strip `[/END]` markers during preprocessing (SPEC-12)
2. Strip common template placeholders (`[insert ...]`, `[Client's Name]`, etc.) (SPEC-12)

**Option B: Document and Proceed**
- Accept the ~3,000 extra bracket artifacts
- Token waste: ~15,000-20,000 tokens (cost ~$0.30)
- Risk: Very low - LLMs will likely ignore these as boilerplate

### 5.2 After Production (P3 Improvements)

1. Consider flagging dialogues with Chinese for manual review
2. Log preprocessing diagnostics for quality monitoring

---

## 6. Impact on Scoring Task

### Question: Does DAIC-WOZ therapist bias apply here?

**Answer: Yes, as a shortcut risk.**

The DAIC-WOZ paper showed that binary MDD classifiers can exploit therapist questions to predict depression labels. However:

1. **Different task**: We're scoring PHQ-8 item-by-item (0-3 scale), not binary classification
2. **Client evidence**: Jurors must cite CLIENT statements as evidence
3. **Prompt instruction**: "Therapist lines are context; evidence should quote/paraphrase CLIENT statements"
4. **Arbitration**: Judge reviews evidence quality, rejecting therapist-only claims

Even with those safeguards, therapist text can still function as a **label leak** (models may internalize therapist framing before selecting “client evidence” snippets).

Empirical check (simple bag-of-words Naive Bayes on stratified 80/20 splits; 10 random seeds):
- **Therapist-only text** predicts `condition` with ~0.92 accuracy (AUC ~0.96).

### Question: Should we use `client_only` instead?

> ⚠️ **Note**: The codebase default is `client_qa` (see `settings.py:52`). The recommendation below suggests `client_only` for reduced leakage, which requires explicitly setting `--dialogue-view client_only`.

**Recommendation: Use `client_only` for production, and run `client_qa` only as an explicit ablation.**

The `client_only` view strips therapist questions, which:

- Reduces **view text** token count by ~58% (mean ~550 vs ~1,306)
- Reduces **total juror input** tokens by ~42% once you include the fixed juror system prompt (mean ~1,043 vs ~1,799)
- Reduces leakage surface from therapist conditioning

In this specific corpus, the classic downside of `client_only` (ambiguous short answers without question context) appears limited: client utterances are long and well-formed, and short/numeric-only answers are rare.

**Trade-off**: `client_only` is cheaper and less leaky but loses interpretive context; use `client_qa` only if a pilot shows material ambiguity.

**Action Required**: If choosing `client_only`, run with: `--dialogue-view client_only`

---

## 7. THE CORE LABELING PROBLEM: Deep Analysis

> **This is the most critical section for understanding what we're attempting and its limitations.**

### 7.1 What We're Trying To Do

We want to generate **PHQ-8 item-level labels** (0-3 per item, 8 items, 0-24 total) from synthetic therapy dialogues. These labels will be used downstream to train/evaluate the `ai-psychiatrist` system.

### 7.2 The Fundamental Problem

**PHQ-8 was designed for patient self-report, not third-party inference from conversation.**

The PHQ-8 asks patients directly:
> "Over the **last 2 weeks**, how often have you been bothered by... [symptom]?"

Possible responses are:
- 0 = Not at all
- 1 = Several days
- 2 = More than half the days
- 3 = Nearly every day

**The problem**: In a therapy conversation, patients rarely say things like "I've felt tired **more than half the days** in the last two weeks." Instead, they say things like:
- "I've been so exhausted lately"
- "I can't seem to get out of bed"
- "Everything feels like a chore"

We're asking LLMs to **infer a frequency score from qualitative language** - a task that even human clinicians find challenging without direct questioning.

### 7.3 Evidence of the Problem in This Corpus

| PHQ-8 Item | Direct Evidence in Corpus | Implication |
|------------|--------------------------|-------------|
| **Anhedonia** | Common ("don't enjoy things anymore") | Labelable |
| **Depressed mood** | Very common ("feeling down", "hopeless") | Labelable |
| **Sleep** | Common ("can't sleep", "sleeping too much") | Labelable |
| **Fatigue** | Common ("tired", "no energy") | Labelable |
| **Appetite** | **Rare** (~11–18/2,090 = ~0.5–0.9% by keyword heuristic) | **Mostly missing** |
| **Guilt** | Moderate ("feel like a failure") | Sometimes labelable |
| **Concentration** | Moderate ("can't focus") | Sometimes labelable |
| **Psychomotor** | **Very rare** (~10/2,090 = ~0.5% strict; ~90/2,090 = ~4.3% if including “restless”) | **Mostly missing** |

**Key insight**: For appetite and psychomotor, we're asking LLMs to score something that simply isn't discussed in most conversations. The jurors will either:
1. Mark `insufficient_evidence=true` (correct but uninformative)
2. Hallucinate a score based on general depression indicators (incorrect but common)
3. Default to 0 (underestimates true severity)

### 7.4 The Frequency Anchor Problem

PHQ-8 maps symptoms to **frequency buckets**:
- 0 = Not at all (0 days)
- 1 = Several days (1-6 days)
- 2 = More than half the days (7-10 days)
- 3 = Nearly every day (11-14 days)

**The corpus contains essentially no PHQ-calibrated frequency anchors.** Explicit "last/past two weeks" language appears in **0/2,090 dialogues (0%)** in client text. Broader "past few weeks" variants appear in only **2/2,090 (~0.10%)** in client text (3/2,090 if including therapist utterances). Literal PHQ response-category phrasing ("more than half the days", "nearly every day", etc.) appears **0 times**.

*Verification method: `grep -E "(last|past)\s+(two|2|couple\s+of|few)\s+weeks?" client_only_text` (case-insensitive)*

This means for ~100% of dialogues, jurors must infer frequency from intensity language:
- "I've been feeling really down" → Score 2? 3? Unclear.
- "Sometimes I can't concentrate" → Score 1? 2? Unclear.

**The result**: High inter-juror disagreement on severity, even when symptom presence is clear.

### 7.5 What This Means for Our Labels

Our labels will be:

| Characteristic | Reality |
|---------------|---------|
| **Symptom presence** | Reliable (anhedonia, mood, sleep, fatigue, guilt, concentration) |
| **Symptom severity** | Less reliable (no frequency anchors → juror disagreement) |
| **Appetite/psychomotor** | Mostly `insufficient_evidence` or guessed |
| **Total score** | Moderately reliable (errors average out across items) |
| **MDD vs Control separation** | Should be robust (aggregate effect) |

### 7.6 Strategic Options

**Option A: Accept and Document (Recommended for v1)**

- Run full 8-item scoring
- Track `insufficient_evidence` rates per item
- Report per-item Krippendorff's α (will be lower for appetite/psychomotor)
- Use total score for downstream tasks (more robust than item scores)
- Document limitations explicitly

**Option B: Reduce to 6 Items (PHQ-6)**

- Drop appetite and psychomotor
- Reduces noise from under-evidenced items
- Loses clinical completeness
- Non-standard instrument

**Option C: Binary Symptom Presence (Not PHQ)**

- Score each item as 0 (absent) or 1 (present)
- Ignores severity/frequency
- Much higher reliability
- Not compatible with PHQ severity buckets

**Recommendation**: Start with Option A. The pilot will reveal if Option B is necessary.

### 7.7 Addendum: Labelability Feasibility Data

This section evaluates whether SQPsychConv conversations contain enough signal to support **item-level PHQ-8 scores** (0–3 each), before spending API budget.

#### 7.7.1 Corpus-Level Red Flags for Item-Level PHQ-8

Some PHQ-8 items are likely to be **dominated by "insufficient evidence"** across the corpus:

- **Appetite change**: rare and definition-sensitive; ~11 dialogues explicitly mention “appetite” (~0.5%), and ~18 dialogues match a more inclusive appetite/eating-change heuristic (~0.9%).
- **Psychomotor**:
  - strict (pacing/fidget/can't sit still/slowed): ~10/2,090 (~0.5%)
  - including "restless": ~90/2,090 (~4.3%)
- **PHQ-calibrated timeframe anchors** ("last/past two weeks"): 0/2,090 (0%); "past few weeks" variants: 2/2,090 (~0.10%) in client text

Practical implication: if you force 8-item scoring, expect large amounts of imputation/guessing for appetite + psychomotor and noisy mapping from vague language to the 0–3 frequency scale.

#### 7.7.2 Sample-Based Labelability (Adversarial Slice)

A 15-dialogue slice across `mdd` and `control` shows many dialogues support only ~2–4 items with direct evidence, with appetite/psychomotor usually absent. Example "high labelability" cases include:

- `active2610` (mdd): explicit depressed mood + sleep + fatigue + appetite
- `active3314` (mdd): depressed mood + fatigue + guilt + concentration + psychomotor ("can't sit still / fidgeting")
- `active2878` (mdd): depressed mood + anhedonia ("used to enjoy… don't bring satisfaction") + guilt

#### 7.7.3 Recommendation (Run Gating)

Before running all 2,090 dialogues:

1. Run a **pilot** (e.g., 50–100 dialogues) and measure per-item `insufficient_evidence` rates and inter-juror disagreement.
2. If appetite/psychomotor are mostly "insufficient evidence", decide explicitly whether to:
   - drop those items,
   - treat them as missing (not 0), or
   - regenerate/augment dialogues to actually express those symptoms.

---

## 8. Addendum (2026-01-05): Cost Estimates & Judge Architecture

### 8.1 Production Run Cost Breakdown (Current 3-Juror Setup)

> ⚠️ **Cost Discrepancy Note**: The preflight checklist (`docs/preflight-checklist/index.md`) shows different estimates (~$640 total). The difference is mostly driven by **judge call volume assumptions** and **API pricing/model IDs**.
>
> SSOT note: In the current implementation, the judge is invoked **per contested item** (see `src/vibe_check/graph/single_dialogue.py`). So judge cost scales roughly linearly with the number of contested items, which you can only learn from a pilot.
>
> **Recommendation**: Budget for the higher estimate until you measure arbitration rates on a pilot run.

| Component | Calls | Input Tokens | Output Tokens | Est. Cost |
|-----------|-------|--------------|---------------|-----------|
| GPT-5.2 Juror (×2 runs) | 4,180 | ~8.3M | ~1.7M | ~$225 |
| Sonnet-4.5 Juror (×2 runs) | 4,180 | ~8.3M | ~1.7M | ~$50 |
| Gemini-3-Pro Juror (×2 runs) | 4,180 | ~8.3M | ~1.7M | ~$19 |
| **Juror Subtotal** | 12,540 | ~24.9M | ~5.0M | **~$293** |
| Opus-4.5 Judge (per item; pilot-dependent call volume) | ~1,881 | ~4.7M | ~0.6M | ~$113* |
| **TOTAL** | | | | **~$406** |

With 50% buffer: **~$609** (highly sensitive to judge calls and pricing)

*Notes:
- `~1,881` judge calls assumes ~30% of dialogues arbitrated × ~3 contested items per arbitrated dialogue.
- If arbitration often triggers `__total__` (8 items), judge calls can be closer to ~5,000 (and costs scale accordingly).

Note: `client_only` reduces view-text tokens by ~58% (and total input tokens by ~42% once you include the fixed system prompt), so juror costs should drop materially but by less than 60% after fixed overhead + output tokens.

### 8.2 Two-Judge Architecture Consideration

**Current design**: Single judge (Opus-4.5) arbitrates contested items.

**Alternative**: Two judges (Opus-4.5 + GPT-5-Pro) for cross-validation.

| Factor | 1 Judge (Opus) | 2 Judges (Opus + GPT-5-Pro) |
|--------|----------------|------------------------------|
| Judge cost | ~$113 | ~$217 |
| Total cost | ~$406 | ~$510 |
| Complexity | Simple | Needs disagreement policy |
| Scientific value | Good | Better (inter-judge reliability) |
| Publication strength | Solid | Stronger |

**When 2 judges adds value**:
- You can report "judges agreed on X% of arbitrated items"
- Judge disagreement flags genuinely ambiguous cases
- Stronger methodology for peer review

**When 1 judge suffices**:
- v1 validation run (prove pipeline works)
- Budget-constrained
- Pilot phase before full production

**Code impact**: Current architecture (`JudgeItemFn`) is single-judge. 2-judge requires:
1. New `JudgeItemFn` signature or wrapper
2. Disagreement resolution policy (majority vote, flag-and-skip, etc.)
3. Schema updates for dual-judge reporting

**Recommendation**:
- **v1**: Run with Opus only, validate pipeline end-to-end
- **v2**: Add 2nd judge if results look promising and publication requires stronger methodology claims

---

## 9. Addendum (2026-01-04): Why This Architecture? A First-Principles Analysis

This section answers: **Why did we design vibe-check with one judge? Should it have two? What does the 2025-2026 literature say?**

### 9.1 The Design Decision Chain

**Question 1: Why multi-model jurors at all?**

The original SPEC-vibe-check (Section 7) explains:
> "Simple mean of `[0, 2, 2, 2, 3, 3]` = 2.0. But `[1, 1, 1, 2, 2, 3]` also = 1.67 ≈ 2. The distributions are different! The first has clear consensus on 2-3, the second is dispersed. Entropy captures this."

Multi-model jurors (3 models × 2 runs = 6 opinions) provide:
1. **Diversity of reasoning** - GPT, Claude, and Gemini have different training data, architectures, and biases
2. **Uncertainty quantification** - Disagreement signals ambiguity, not error
3. **Bayesian aggregation** - Full posterior distribution, not just point estimates

**Question 2: Why a separate judge role?**

The judge exists specifically for *contested items* - when juror opinions diverge beyond threshold. From `docs/scoring/arbitration.md`:
- Low max probability (< 0.60)
- High entropy (> 1.2)
- Clinical ambiguity (P(score ≥ 2) ∈ [0.4, 0.6])
- Wide vote range (≥ 2 points)

The judge is *not* scoring from scratch - it's **reviewing the evidence and reasoning from 6 jurors**. This is fundamentally different from a second independent opinion.

**Question 3: Why was a single judge chosen?**

From SPEC-vibe-check Section 2:
> "Claude Opus 4.5 (Judge): Most capable Anthropic model for complex arbitration. Different family from majority jurors (avoids correlated errors). Used sparingly - only for disagreements (~20% of items)."

The design rationale was:
1. **Different model family** - Opus is a different architecture than the jurors (Sonnet, GPT, Gemini)
2. **Highest capability** - Opus 4.5 is the most capable model available for "careful deliberation"
3. **Cost efficiency** - Judge calls are ~10× more expensive per item than juror calls
4. **Sparing use** - Only ~30% of items trigger arbitration

### 9.2 What Does 2025-2026 Literature Say?

**Multi-Judge/Ensemble Research:**

| Finding | Source | Implication |
|---------|--------|-------------|
| "Multi-Agent Judges achieve higher reliability and closer alignment to human consensus than a lone model" | [LLM-as-a-Judge Survey](https://arxiv.org/abs/2411.15594) | Supports ensemble approach |
| "Consensus-based judges offered no accuracy advantage over single judges. Both topped out around 96% agreement with human labels" | [DataRobot Study](https://www.datarobot.com/blog/llm-judges/) | Single judge may be sufficient |
| "Committees bring stability. For critical evaluations, polling 3–5 diverse, powerful models reduces bias and noise" | [EmergentMind](https://www.emergentmind.com/topics/llm-as-a-judge-evaluations) | Multi-judge adds stability, not accuracy |
| "Ensembles do not inherently mitigate shared systematic biases. If most models exhibit the same bias, the ensemble reinforces it" | [Collective Intelligence Project](https://www.cip.org/blog/llm-judges-are-unreliable) | Diversity matters more than quantity |

**Amazon CollabEval Framework (2025):**

Amazon's [CollabEval](https://www.amazon.science/publications/enhancing-llm-as-a-judge-via-multi-agent-collaboration) implements a three-phase multi-agent evaluation:
1. **Initial evaluation** - Multiple independent judges score with confidence
2. **Multi-round discussion** - Judges share reasoning and update
3. **Final judgment** - Consensus decision

Key insight: CollabEval's value is in the *discussion phase*, not just vote aggregation. Vibe-check's current architecture has discussion implicitly via the judge seeing juror evidence.

**Clinical NLP Specific:**

| Finding | Source | Implication |
|---------|--------|-------------|
| "Qwen 2.5–72b achieves near-human level agreement on MADRS items (ICC 0.89-0.94)" | [LlaMADRS](https://arxiv.org/html/2501.03624v1) | Single LLM can match human raters |
| "LLMs consistently overestimated urgency compared to human raters, with moderate-to-strong correlations" | [Nature Mental Health](https://www.nature.com/articles/s44184-024-00112-8) | Calibration matters more than judge count |
| "GPT-4 performs exceptionally well... accuracy of 0.902" | [JMIR Study](https://www.jmir.org/2024/1/e54617) | Strong single-model performance is achievable |

### 9.3 Key Insight: Vibe-Check Already Has Multi-Rater Architecture

The critical realization: **vibe-check already has a 6-rater ensemble at the juror level**.

```
                  ┌─────────────────────────────────────────────────┐
                  │              JUROR ENSEMBLE (6 raters)          │
                  │                                                 │
                  │    ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐
                  │    │GPT-1│ │GPT-2│ │CLD-1│ │CLD-2│ │GEM-1│ │GEM-2│
                  │    └──┬──┘ └──┬──┘ └──┬──┘ └──┬──┘ └──┬──┘ └──┬──┘
                  │       └───────┴───────┴───┬───┴───────┴───────┘
                  │                           │
                  │           Bayesian Aggregation (Dirichlet posterior)
                  │                           │
                  │              ┌────────────┴────────────┐
                  │              ▼                         ▼
                  │         Consensus                 Contested
                  │         (70% items)              (30% items)
                  │              │                         │
                  └──────────────┼─────────────────────────┼────────┘
                                 │                         ▼
                                 │                  ┌─────────────┐
                                 │                  │   JUDGE     │
                                 │                  │  (Opus 4.5) │
                                 │                  │             │
                                 │                  │ Sees ALL 6  │
                                 │                  │ juror votes │
                                 │                  │ + evidence  │
                                 │                  └──────┬──────┘
                                 │                         │
                                 ▼                         ▼
                              FINAL SCORE
```

The question "should we have 2 judges?" is really asking:
- Should we add a **7th or 8th opinion** on contested items?
- Is Opus alone a sufficient tiebreaker?

### 9.4 Arguments For vs Against Two Judges

**Arguments FOR two judges (Opus + GPT-5-Pro):**

| Argument | Weight | Counter |
|----------|--------|---------|
| "Inter-judge reliability is publishable" | High (academic) | True, but juror κ is already reportable |
| "Catches Opus-specific biases" | Medium | GPT-5-Pro may share biases with GPT-5.2 jurors |
| "Stronger methodology claims" | High (publication) | v1 can still demonstrate validity |
| "Flags genuinely ambiguous cases" | Medium | Juror entropy already does this |

**Arguments AGAINST two judges:**

| Argument | Weight | Counter |
|----------|--------|---------|
| "Opus already sees 6 diverse opinions" | High | This is the key insight |
| "Adding GPT-5-Pro is same family as GPT-5.2 jurors" | High | Reduces diversity benefit |
| "~$104 additional cost for ~30% of items" | Medium | May be acceptable for publication |
| "Adds complexity (disagreement policy)" | Medium | Solvable engineering problem |
| "Judge role is synthesis, not independent scoring" | High | Two judges synthesizing the same evidence may converge anyway |

### 9.5 Recommendation

**For v1 (Pipeline Validation):** Single judge (Opus) is **architecturally sound**.

The 6-juror ensemble provides:
- Model diversity (3 families: OpenAI, Anthropic, Google)
- Run-to-run variance capture (2 runs per model)
- Bayesian uncertainty quantification (posteriors, entropy)
- Evidence extraction for audit

The judge role is **synthesis of existing evidence**, not independent scoring. Opus seeing 6 opinions and their evidence is analogous to a senior clinician reviewing junior assessments.

**For v2 (Publication-Grade):** Consider second judge **only if**:

1. Pilot shows Opus disagreeing with juror consensus > 15% of arbitrated items
2. Reviewers specifically request inter-judge reliability metrics
3. You want to claim "multi-model arbitration" as a methodological contribution

If adding a second judge, choose a **different model family** than the jurors:
- ❌ GPT-5-Pro (same family as GPT-5.2 jurors)
- ✓ Gemini 3 Ultra (different family, if available)
- ✓ DeepSeek-R1-70B (open-source diversity)

### 9.6 Literature Sources

1. [LLM-as-Judge Best Practices](https://www.montecarlodata.com/blog-llm-as-judge/) - 7 best practices and templates
2. [SE-Jury: LLM-as-Ensemble-Judge (ASE 2025)](https://conf.researchr.org/details/ase-2025/ase-2025-papers/222/SE-Jury-An-LLM-as-Ensemble-Judge-Metric-for-Narrowing-the-Gap-with-Human-Evaluation-) - Dynamic team selection
3. [Amazon CollabEval](https://www.amazon.science/publications/enhancing-llm-as-a-judge-via-multi-agent-collaboration) - Multi-agent collaborative evaluation
4. [Can You Trust LLM Judgments?](https://arxiv.org/abs/2412.12509) - Reliability of LLM-as-a-Judge
5. [Survey on LLM-as-a-Judge](https://arxiv.org/abs/2411.15594) - Comprehensive survey (Nov 2024)
6. [LlaMADRS](https://arxiv.org/html/2501.03624v1) - LLM-based MADRS scoring (Jan 2025)
7. [PHQ-9 ML Estimation](https://www.sciencedirect.com/science/article/pii/S016503272500182X) - ML model for PHQ-9 from clinical notes
8. [LLM-Based PHQ-9 Labeling](https://arxiv.org/abs/2505.17119) - Systematic evaluation (May 2025)

---

## 10. Summary: What We're Building and Why

### 10.1 The System

**vibe-check** is a multi-agent PHQ-8 scoring pipeline that:

1. Takes 2,090 synthetic therapy dialogues (SQPsychConv qwen-2.5)
2. Scores each with 6 LLM jurors (3 models × 2 runs)
3. Aggregates via Bayesian posteriors (Dirichlet smoothing)
4. Arbitrates contested items with a senior judge (Opus 4.5)
5. Exports PHQ-8 labels for downstream use in `ai-psychiatrist`

### 10.2 The Architecture Rationale

| Design Choice | Rationale | Alternative Considered |
|--------------|-----------|------------------------|
| 3 juror models | Cross-vendor diversity | 1 model × 6 runs (lower diversity) |
| 2 runs per model | Capture intra-model variance | 1 run (cheaper but less stable) |
| Dirichlet aggregation | Principled uncertainty | Simple majority vote (loses info) |
| Single judge | Synthesis role, not independent | 2 judges (higher cost, unclear benefit) |
| Opus as judge | Highest capability available | Sonnet (cheaper but less capable) |
| Arbitration at ~30% | Balance quality vs cost | Always judge (10× cost) |

### 10.3 What's NOT Needed for v1

Based on this analysis:

- ❌ **Two judges** - Single judge with 6-juror input is sufficient
- ✓ **Preprocessing fixes** - Implemented (SPEC-12)
- ❌ **Chinese character removal** - 1 dialogue (0.05%), LLMs handle it
- ❌ **Different dialogue view** - `client_qa` vs `client_only` is an ablation choice

### 10.4 What IS Needed for v1

- ✓ **Pilot run** (50-100 dialogues) to validate pipeline
- ✓ **Measure per-item insufficient_evidence rates**
- ✓ **Report inter-juror agreement** (Krippendorff's α)
- ✓ **Apply quality gates** (see `docs/reference/thresholds.md`): Krippendorff α ≥ 0.67, Cronbach α ≥ 0.70, separation p < 0.01 & d ≥ 0.5, arbitration rate < 30%
- ✓ **Decision rule for under-evidenced items**: if appetite/psychomotor are mostly insufficient evidence or fail per-item reliability, treat as missing or drop (PHQ-6) and document explicitly
- ✓ **Verify MDD > Control separation**
- ✓ **Document arbitration rate** (target: < 30%)

---

## 11. Files Created/Modified

Modified: `DATA-QUALITY-ANALYSIS.md`
- Original analysis (2026-01-04): corpus stats, P2/P3 issues, preprocessing
- Addendum 1 (2026-01-05): labelability feasibility, cost estimates, 2-judge consideration
- Addendum 2 (2026-01-04): architecture rationale, literature review, final recommendation

---

*Analysis performed: 2026-01-04*
*Corpus: data/sqpsychconv/qwen-2.5 (2,090 dialogues)*
*Analyzer: Claude Opus 4.5*

*Addendum 1: 2026-01-05*
*Analyzer: GPT-5.2 (Codex CLI)*

*Addendum 2: 2026-01-04*
*Analyzer: Claude Opus 4.5 (deep research on judge architecture)*
