# SQPsychConv qwen-2.5 Data Quality Analysis

> First-principles analysis of data/sqpsychconv/qwen-2.5 corpus
> Date: 2026-01-04

---

## Executive Summary

The corpus is **fundamentally sound** for PHQ-8 scoring with **no critical blockers**. However, there are **P2 preprocessing gaps** that should be addressed to avoid wasting tokens and potential LLM confusion.

**Verdict**: Production run can proceed, but preprocessing improvements recommended.

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
| Total occurrences | 2,491 |
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

| Placeholder | Count |
|-------------|-------|
| `[insert preferred date]` | 57 |
| `[insert date]` | 38 |
| `[insert date and time]` | 28 |
| `[insert date here]` | 22 |
| `[Client's Name]` | 16 |
| `[next available date]` | 14 |
| `[insert time]` | 8 |
| `[Therapist's Name]` | 6 |
| Other patterns | ~83 unique |
| **Total bracket artifacts** | **2,979** |

**Example**:
```
Therapist: Hello, Mr. [Client's Name]. How are you feeling today?
```

**Impact**: Clearly synthetic, could confuse LLMs scoring for depression symptoms.

**Fix**: Strip common template placeholders or flag dialogues for review.

---

### 2.3 LLM Roleplay Meta-Actions

**Severity**: P3 (minor, but unnecessary)

| Pattern | Count |
|---------|-------|
| `[Keep silent]` | 11 |
| `[Pause and say nothing]` | 11 |
| `[No reply]` | 8 |
| `[Quiet]` | ~3 (very short turns) |

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

**Answer: No, for our specific task.**

The DAIC-WOZ paper showed that binary MDD classifiers can exploit therapist questions to predict depression labels. However:

1. **Different task**: We're scoring PHQ-8 item-by-item (0-3 scale), not binary classification
2. **Client evidence**: Jurors must cite CLIENT statements as evidence
3. **Prompt instruction**: "Therapist lines are context; evidence should quote/paraphrase CLIENT statements"
4. **Arbitration**: Judge reviews evidence quality, rejecting therapist-only claims

The `client_qa` view (therapist question + client response) is appropriate because:
- It provides context for interpreting client statements
- The client's response directly addresses the therapist's question
- PHQ-8 items require understanding *what the client is responding to*

### Question: Should we use `client_only` instead?

**Recommendation: Use `client_qa` (default)**

The `client_only` view strips therapist questions, which:
- Loses context for interpreting client responses
- Makes some statements ambiguous ("Yeah, almost every day" - of what?)
- Reduces token count by ~60% (mean 595 vs 1481)

Trade-off: `client_only` is cheaper but loses interpretive context. For accurate PHQ-8 scoring, context matters.

---

## 7. Files Created/Modified

None. This is a read-only analysis.

---

*Analysis performed: 2026-01-04*
*Corpus: data/sqpsychconv/qwen-2.5 (2,090 dialogues)*
*Analyzer: Claude Opus 4.5*
