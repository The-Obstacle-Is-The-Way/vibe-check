# Paper Split Registry (DAIC-WOZ)

This document describes the **paper reproduction splits** shipped in `data/daic-woz/paper_splits/`.

## What These Splits Are

These CSVs provide an alternative partitioning of the **142 labeled DAIC-WOZ participants** (AVEC train+dev) into:
- Train: 58
- Val: 43
- Test: 41

The split membership is recorded in:
- `data/daic-woz/paper_splits/paper_split_train.csv`
- `data/daic-woz/paper_splits/paper_split_val.csv`
- `data/daic-woz/paper_splits/paper_split_test.csv`

## Provenance

The split IDs were **reverse-engineered from paper authors' output files** during an internal reproduction effort.

The derivation metadata is stored in:
- `data/daic-woz/paper_splits/paper_split_metadata.json`

Note: The upstream paper-output files referenced in `paper_split_metadata.json` are **not stored in this repo**, so re-deriving the split from raw paper outputs is not currently reproducible here; the split CSVs themselves are the authoritative record for this project.

## Sanity Checks

You can verify the splits cover all labeled participants with no overlap:

```bash
uv run python - <<'PY'
import pandas as pd

labels = pd.concat([
    pd.read_csv("data/daic-woz/train_split_Depression_AVEC2017.csv"),
    pd.read_csv("data/daic-woz/dev_split_Depression_AVEC2017.csv"),
], ignore_index=True)
labeled_ids = set(labels["Participant_ID"])

paper = pd.concat([
    pd.read_csv("data/daic-woz/paper_splits/paper_split_train.csv"),
    pd.read_csv("data/daic-woz/paper_splits/paper_split_val.csv"),
    pd.read_csv("data/daic-woz/paper_splits/paper_split_test.csv"),
], ignore_index=True)
paper_ids = set(paper["Participant_ID"])

print("labeled:", len(labeled_ids))
print("paper:", len(paper_ids))
print("same_ids:", labeled_ids == paper_ids)
PY
```
