# Dataset Card: SQPsychConv

**Source**: HuggingFace `AIMH/SQPsychConv_*`
**Local Path**: `data/sqpsychconv/`
**Primary Variant**: `qwen-2.5` (highest quality, 16.29/18 expert score)
**Verified**: 2026-01-02

---

## Summary

SQPsychConv is a synthetic psychotherapy conversation dataset. The same 2,090 questionnaires (from Kircher et al. 2019) are used to generate conversations with 7 different LLMs, producing 7 dataset variants on HuggingFace.

**Our selection**: We use only `qwen-2.5` (primary) and `gemma` (backup). Lower-quality variants were deleted per research best practices: "model capability matters more than model diversity."

---

## Local Variants (Kept)

| Variant | Expert Score | Train | Test | Status |
|---------|--------------|-------|------|--------|
| **qwen-2.5** | **16.29** | 1837 | 253 | **PRIMARY** |
| gemma | 16.14 | 1837 | 253 | Backup |

**Expert scores from paper Table 5** (max 18 points, human evaluation of therapist skills)

---

## Deleted Variants (Not Local)

| Variant | Expert Score | Reason Deleted |
|---------|--------------|----------------|
| qwq | 15.71 | **BUGGED** (train=test duplication) |
| llama3 | 14.86 | Lower quality |
| mistral | 14.71 | Lower quality |
| nemotron | N/A | Lower quality |
| command | 12.57 | Lowest quality |

See `docs/_archive/dataset-sqpsychconv-qwq.md` for qwq bug documentation.

---

## Schema

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
├── qwen-2.5/              # PRIMARY (highest quality)
│   ├── train/
│   │   └── data-00000-of-00001.arrow  (1,837 rows)
│   ├── test/
│   │   └── data-00000-of-00001.arrow  (253 rows)
│   └── dataset_dict.json
├── gemma/                 # BACKUP (second best)
│   ├── train/
│   ├── test/
│   └── dataset_dict.json
└── exports/               # CSV exports for analysis
    ├── qwen25_train.csv   (1,837 rows)
    └── qwen25_test.csv    (253 rows)
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

### Load CSV Exports

```python
import pandas as pd

train = pd.read_csv("data/sqpsychconv/exports/qwen25_train.csv")
test = pd.read_csv("data/sqpsychconv/exports/qwen25_test.csv")

print(f"Train: {len(train)} dialogues")
print(f"Test: {len(test)} dialogues")
print(train.head())
```

---

## Licensing

**Status**: UNKNOWN - Requires author confirmation before redistribution

| Artifact | Known License |
|----------|---------------|
| arXiv paper | CC BY 4.0 |
| Project website | CC BY-SA 4.0 |
| HuggingFace dataset card | **No license displayed** |
| Dataset itself | **UNCONFIRMED** |

---

## References

- Paper: [SQPsychConv: Synthetic Question-based Psychological Conversation Dataset](https://arxiv.org/abs/2510.25384)
- HuggingFace Collection: [AIMH/SQPsychConv](https://huggingface.co/collections/AIMH/sqpsychconv)
