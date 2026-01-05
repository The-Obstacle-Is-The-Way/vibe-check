# SQPsychConv qwen-2.5 Data Quality Analysis

> First-principles analysis of data/sqpsychconv/qwen-2.5 corpus
> Date: 2026-01-04

---

## Executive Summary

The corpus is **structurally clean and parseable** for PHQ-8 scoring, but PHQ-8 **labeling feasibility is conditional** once you account for (a) sparse direct evidence for some items (notably appetite/psychomotor) and (b) **therapist prompt leakage risk** if therapist turns are included in the scoring text.

There are also **P2 preprocessing gaps** that should be addressed to avoid wasting tokens and potential LLM confusion.

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

| Stat | Tokens |
|------|--------|
| Min | ~682 |
| Max | ~3,609 |
| Mean | ~1,481 |
| Median | ~1,400 |

11 dialogues exceed 3,000 tokens (all well within GPT-4/Claude limits).

---

## 2. P2 Issues - Generation Artifacts (Should Fix)

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

**Fix**: Strip `[/END]` during preprocessing.

---

### 2.2 Template Placeholders Not Filled

**Severity**: P2 (data quality, potential LLM confusion)

Counts below are **occurrences** of bracketed placeholders (case-insensitive; capitalization variants aggregated).

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
| Other patterns | 83 unique (non-`[/END]`) |
| **Total bracket artifacts** | **2,984** |

Notes:
- “Total bracket artifacts” counts **all** bracketed segments, including `[/END]` (2,492 occurrences) + 492 other bracketed segments.

**Example**:
```
Therapist: Hello, Mr. [Client's Name]. How are you feeling today?
```

**Impact**: Clearly synthetic, could confuse LLMs scoring for depression symptoms.

**Fix**: Strip common template placeholders or flag dialogues for review.

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

**Impact**: These are not clinical content. Could be stripped or left (low impact).

---

## 3. P3 Issues - Minor/Cosmetic (No Action Needed)

### 3.1 Curly Quotes (Unicode)

**Severity**: P3 (no action needed)

- 2,089/2,090 dialogues use U+2019 (right single quotation mark) as apostrophe
- 175 curly double quotes (U+201C, U+201D)
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

**Option A: Fix Preprocessing** (Recommended)
1. Strip `[/END]` markers in `_sanitize_utterance_text()`
2. Strip common template placeholders (`[insert ...]`, `[Client's Name]`, etc.)

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

Empirical check (simple bag-of-words Naive Bayes on held-out split):
- **Therapist-only text** predicts `condition` with ~0.91 accuracy (AUC ~0.95).

### Question: Should we use `client_only` instead?

**Recommendation: Use `client_only` (default), and run `client_qa` only as an explicit ablation.**

The `client_only` view strips therapist questions, which:
- Reduces token count by ~60% (mean ~595 vs ~1481 from the earlier estimate)
- Reduces leakage surface from therapist conditioning

In this specific corpus, the classic downside of `client_only` (ambiguous short answers without question context) appears limited: client utterances are long and well-formed, and short/numeric-only answers are rare.

Trade-off: `client_only` is cheaper and less leaky but loses interpretive context; use `client_qa` only if a pilot shows material ambiguity.

---

## 7. Addendum (2026-01-05): PHQ-8 Labelability Feasibility

This section evaluates whether SQPsychConv conversations contain enough signal to support **item-level PHQ-8 scores** (0–3 each), before spending API budget.

### 7.1 Corpus-Level Red Flags for Item-Level PHQ-8

Some PHQ-8 items are likely to be **dominated by “insufficient evidence”** across the corpus:

- **Appetite change**: 16/2,090 dialogues (~0.8%) contain any client-side appetite/eating-change language.
- **Psychomotor**:
  - strict (pacing/fidget/can’t sit still/slowed): 17/2,090 (~0.8%)
  - including “restless”: 86/2,090 (~4.1%)
- **PHQ frequency anchors** (“last 2 weeks”, “most days”, “nearly every day”, etc.) in client text: 79/2,090 (~3.8%)

Practical implication: if you force 8-item scoring, expect large amounts of imputation/guessing for appetite + psychomotor and noisy mapping from vague language to the 0–3 frequency scale.

### 7.2 Sample-Based Labelability (Adversarial Slice)

A 15-dialogue slice across `mdd` and `control` shows many dialogues support only ~2–4 items with direct evidence, with appetite/psychomotor usually absent. Example “high labelability” cases include:
- `active2610` (mdd): explicit depressed mood + sleep + fatigue + appetite
- `active3314` (mdd): depressed mood + fatigue + guilt + concentration + psychomotor (“can’t sit still / fidgeting”)
- `active2878` (mdd): depressed mood + anhedonia (“used to enjoy… don’t bring satisfaction”) + guilt

### 7.3 Recommendation (Run Gating)

Before running all 2,090 dialogues:
1. Run a **pilot** (e.g., 50–100 dialogues) and measure per-item `insufficient_evidence` rates and inter-juror disagreement.
2. If appetite/psychomotor are mostly “insufficient evidence”, decide explicitly whether to:
   - drop those items,
   - treat them as missing (not 0), or
   - regenerate/augment dialogues to actually express those symptoms.

---

## 8. Addendum (2026-01-05): Cost Estimates & Judge Architecture

### 8.1 Production Run Cost Breakdown (Current 3-Juror Setup)

| Component | Calls | Input Tokens | Output Tokens | Est. Cost |
|-----------|-------|--------------|---------------|-----------|
| GPT-5.2 Juror (×2 runs) | 4,180 | ~8.3M | ~1.7M | ~$225 |
| Sonnet-4.5 Juror (×2 runs) | 4,180 | ~8.3M | ~1.7M | ~$50 |
| Gemini-3-Pro Juror (×2 runs) | 4,180 | ~8.3M | ~1.7M | ~$19 |
| **Juror Subtotal** | 12,540 | ~24.9M | ~5.0M | **~$293** |
| Opus-4.5 Judge (~30% arb, ~3 items) | ~1,881 | ~4.7M | ~0.6M | ~$113 |
| **TOTAL** | | | | **~$406** |

With 50% buffer: **~$609**

Note: `client_only` view reduces juror input tokens by ~60%, lowering juror costs to ~$175 (total ~$288).

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

## 9. Files Created/Modified

Modified: `DATA-QUALITY-ANALYSIS.md` (counts corrected; labelability + leakage addendum; cost estimates + 2-judge architecture)

---

*Analysis performed: 2026-01-04*
*Corpus: data/sqpsychconv/qwen-2.5 (2,090 dialogues)*
*Analyzer: Claude Opus 4.5*

*Addendum performed: 2026-01-05*
*Analyzer: GPT-5.2 (Codex CLI)*
