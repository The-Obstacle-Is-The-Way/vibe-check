# Dataset Card: SQPsychConv (All Variants)

**Source**: HuggingFace `AIMH/SQPsychConv_*`
**Local Path**: `data/sqpsychconv/`
**Verified**: 2026-01-02
**Recommended Variant**: `qwen-2.5`

---

## Summary

SQPsychConv is a synthetic psychotherapy conversation dataset. The same 2,090 questionnaires (from Kircher et al. 2019) are used to generate conversations with 7 different LLMs, producing 7 dataset variants.

---

## Variant Overview

| Variant | Expert Score | Train | Test | Status | Recommendation |
|---------|--------------|-------|------|--------|----------------|
| **qwen-2.5** | **16.29** | 1837 | 253 | OK | **USE THIS** |
| gemma | 16.14 | 1837 | 253 | OK | Good alternative |
| qwq | 15.71 | 2090 | 2090 | **BUGGED** | Avoid |
| llama3 | 14.86 | 1837 | 253 | OK | - |
| mistral | 14.71 | 1837 | 253 | OK | - |
| nemotron | N/A | 1837 | 253 | OK | - |
| command | 12.57 | 1837 | 253 | OK | Lowest quality |

**Expert scores from paper Table 5** (max 18 points, human evaluation of therapist skills)

---

## The qwq Bug

`SQPsychConv_qwq` has a HuggingFace upload bug where train and test splits are identical:

```
Arrow MD5 (both splits): e3ff92d039b8ee12fa2023fc4d3abfb3
file_id overlap: 100%
Claimed total: 4,180 (incorrect)
Actual unique: 2,090
```

All other variants have proper 88/12 train/test splits with 0% overlap.

---

## Schema (All Variants)

| Field | Type | Description |
|-------|------|-------------|
| `file_id` | string | Unique questionnaire ID (e.g., `active436`) |
| `condition` | string | `mdd` or `control` |
| `client_model` | string | Model used for client (variant name) |
| `therapist_model` | string | Model used for therapist (variant name) |
| `dialogue` | string | Full conversation transcript |

---

## Condition Distribution

Consistent across all variants:

| Condition | Count | Percentage |
|-----------|-------|------------|
| control | 1,178 | 56.4% |
| mdd | 912 | 43.6% |

---

## File ID Consistency

All 7 variants share **identical file_ids**. They are different model interpretations of the same 2,090 questionnaires:

```python
# Verified: All variants have same file_ids
all_same = True  # Confirmed via SHA256 comparison
```

This enables:
- Switching variants without breaking corpus integrity
- Cross-model analysis on same questionnaires
- Multi-variant ensemble scoring

---

## Local File Structure

```
data/sqpsychconv/
├── qwen-2.5/          # RECOMMENDED (highest quality)
│   ├── train/
│   │   └── data-00000-of-00001.arrow  (1,837 rows)
│   ├── test/
│   │   └── data-00000-of-00001.arrow  (253 rows)
│   └── dataset_dict.json
├── gemma/             # Second best
├── qwq/               # BUGGED - train=test
├── llama3/
├── mistral/
├── nemotron/
└── command/           # Lowest quality
```

---

## Usage

### Load Recommended Variant

```python
from datasets import load_from_disk

# Recommended: qwen-2.5
ds = load_from_disk("data/sqpsychconv/qwen-2.5")
print(f"Train: {len(ds['train'])}, Test: {len(ds['test'])}")
# Train: 1837, Test: 253
```

### Load All Variants

```python
variants = ["qwen-2.5", "gemma", "llama3", "mistral", "nemotron", "command"]
# Note: Excluding qwq due to bug

for variant in variants:
    ds = load_from_disk(f"data/sqpsychconv/{variant}")
    print(f"{variant}: {len(ds['train']) + len(ds['test'])} total")
```

---

## Licensing

**Status**: UNKNOWN - Same as parent dataset

See `DATASET-sqpsychconv-qwq.md` for licensing concerns.

---

## References

- Paper: [SQPsychConv: Synthetic Question-based Psychological Conversation Dataset](https://arxiv.org/abs/2510.25384)
- HuggingFace Collection: [AIMH/SQPsychConv](https://huggingface.co/collections/AIMH/sqpsychconv)
