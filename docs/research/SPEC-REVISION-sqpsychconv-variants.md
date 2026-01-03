# SPEC REVISION: SQPsychConv Model Variant Selection

**Date**: 2026-01-02
**Status**: CRITICAL - Requires Master Spec Update
**Affects**: SPEC-vibe-check.md, SPEC-02-data-pipeline.md
**Priority**: HIGH - Discovered during dataset analysis

---

## 1. Executive Summary

**Problem Discovered**: The SQPsychConv dataset exists in 7 model variants, each with different conversation quality. Our original download (`qwq`) has a HuggingFace upload bug AND is not the highest-quality variant.

**Recommendation**: Use `SQPsychConv_qwen-2.5` instead of `SQPsychConv_qwq`.

---

## 2. Dataset Variant Analysis

### 2.1 Available Variants

The SQPsychConv paper generates conversations using 7 different LLMs from the same 2,090 questionnaires:

| Variant | HuggingFace Dataset | Train | Test | Split Status |
|---------|---------------------|-------|------|--------------|
| qwq | `AIMH/SQPsychConv_qwq` | 2090 | 2090 | **BUGGED** (train=test) |
| qwen-2.5 | `AIMH/SQPsychConv_qwen-2.5` | 1837 | 253 | OK (88/12) |
| gemma | `AIMH/SQPsychConv_gemma` | 1837 | 253 | OK (88/12) |
| llama3 | `AIMH/SQPsychConv_llama3` | 1837 | 253 | OK (88/12) |
| mistral | `AIMH/SQPsychConv_mistral` | 1837 | 253 | OK (88/12) |
| nemotron | `AIMH/SQPsychConv_nemotron` | 1837 | 253 | OK (88/12) |
| command | `AIMH/SQPsychConv_command` | 1837 | 253 | OK (88/12) |

### 2.2 Expert Quality Scores (Paper Table 5)

Human experts evaluated therapist skills (max 18 points):

| Variant | Expert Score | Rank |
|---------|--------------|------|
| **qwen-2.5** | **16.29** | 1st (BEST) |
| gemma | 16.14 | 2nd |
| qwq | 15.71 | 3rd |
| llama3 | 14.86 | 4th |
| mistral | 14.71 | 5th |
| deepseek | 13.71 | 6th (not on HF) |
| command | 12.57 | 7th (WORST) |

### 2.3 File ID Consistency

All 7 variants share **identical file_ids** (same 2,090 questionnaires):

```
All non-bugged variants have identical file_ids: True
qwq file_ids match qwen-2.5: True
```

This means switching variants preserves corpus integrity - same questionnaires, different model interpretations.

---

## 3. The qwq Duplication Bug

### Evidence

```
qwq Arrow MD5 (train): e3ff92d039b8ee12fa2023fc4d3abfb3
qwq Arrow MD5 (test):  e3ff92d039b8ee12fa2023fc4d3abfb3  # IDENTICAL

file_id overlap: 2090/2090 (100%)
```

### Impact

- HuggingFace displays 4.18k rows (incorrectly)
- Actually only 2,090 unique dialogues
- Train and test are literally the same data
- Our deterministic resplit mitigated this, but switching to qwen-2.5 avoids it entirely

### Root Cause

Likely a dataset upload error by AIMH. All other variants have proper splits.

---

## 4. Recommendations

### 4.1 Primary Recommendation: Use qwen-2.5

| Factor | qwq (current) | qwen-2.5 (recommended) |
|--------|---------------|------------------------|
| Expert quality score | 15.71 (3rd) | **16.29 (1st)** |
| Train/test split | BUGGED | Proper (88/12) |
| Unique dialogues | 2,090 | 2,090 |
| file_ids | Same | Same |

**Action**: Update `SPEC-02-data-pipeline.md` to specify `qwen-2.5` as the primary corpus.

### 4.2 Alternative: Multi-Variant Corpus

For more robust scoring, consider using multiple variants:

```
Tier 1 (highest quality):
  - qwen-2.5 (16.29)
  - gemma (16.14)

Total: 2 variants × 2,090 = 4,180 unique conversations
```

**Pros**:
- More data
- Cross-model validation (same questionnaire, different interpretations)
- Reduces single-model bias

**Cons**:
- 2× API costs
- More complex analysis
- Model-style variance in outputs

### 4.3 NOT Recommended

- **qwq alone**: Bugged splits, not highest quality
- **command**: Lowest expert score (12.57)
- **All 7 variants**: Overkill, diminishing returns

---

## 5. Spec Updates Required

### 5.1 SPEC-vibe-check.md (Master Spec)

**Section 3.4 (Corpus Integrity)**: Add model variant selection guidance.

```markdown
### 3.5 Model Variant Selection

SQPsychConv exists in 7 model variants. Use `SQPsychConv_qwen-2.5`:
- Highest expert quality score (16.29/18)
- Proper train/test split (1837/253)
- No known upload bugs

Avoid `SQPsychConv_qwq` despite similar naming:
- Train/test duplication bug on HuggingFace
- Lower quality score (15.71)
```

### 5.2 SPEC-02-data-pipeline.md

**Update HuggingFace source**:

```python
# BEFORE (incorrect)
DATASET_NAME = "AIMH/SQPsychConv_qwq"

# AFTER (correct)
DATASET_NAME = "AIMH/SQPsychConv_qwen-2.5"
```

### 5.3 Data Directory Structure

**Current**:
```
data/sqpsychconv/
├── qwq/           # BUGGED
├── qwen-2.5/      # RECOMMENDED
├── gemma/
├── llama3/
├── mistral/
├── nemotron/
└── command/
```

**Recommended default**: `data/sqpsychconv/qwen-2.5/`

---

## 6. Impact Assessment

### 6.1 Code Changes Required

| File | Change |
|------|--------|
| `src/vibe_check/data/loader.py` | Update default dataset path |
| `src/vibe_check/settings.py` | Add `corpus_variant` setting |
| `tests/integration/*` | Update fixture paths |

### 6.2 Existing Work Preserved

- Deterministic resplit logic: **Still valid** (can be simplified for non-bugged variants)
- Scoring schemas: **No change**
- Aggregation logic: **No change**
- Export format: **No change**

### 6.3 Good News

We caught this before production scoring. The fix is a path change, not an architectural change.

---

## 7. Author Notification

**Action Item**: Contact AIMH authors about the qwq duplication bug.

Draft email included in `docs/data/DATASET-sqpsychconv-qwq.md`.

---

## 8. Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-01-02 | Use qwen-2.5 as primary | Highest quality + proper splits |
| 2026-01-02 | Keep all variants downloaded | Future multi-model analysis |
| 2026-01-02 | Preserve deterministic resplit | Still useful for cross-validation |

---

## Appendix: Verification Commands

```bash
# Verify all variants downloaded
ls -la data/sqpsychconv/

# Check split sizes
uv run python -c "
from datasets import load_from_disk
for v in ['qwq', 'qwen-2.5', 'gemma', 'llama3', 'mistral', 'nemotron', 'command']:
    ds = load_from_disk(f'data/sqpsychconv/{v}')
    print(f'{v}: train={len(ds[\"train\"])}, test={len(ds[\"test\"])}')"
```
