# Dataset Card: DAIC-WOZ

**Source**: AVEC 2017 Depression Sub-challenge (Distress Analysis Interview Corpus)
**Local Path**: `data/daic-woz/`
**License**: Research use only (not redistributable)
**Verified**: 2026-01-06

---

## Summary

DAIC-WOZ is a real clinical interview dataset collected by the USC Institute for Creative Technologies. Participants were interviewed by an animated virtual interviewer (Ellie) about their experiences, with the goal of detecting psychological distress indicators.

**Key difference from SQPsychConv**: DAIC-WOZ contains **real human interviews** with **ground truth PHQ-8 labels** (self-reported by participants). SQPsychConv contains synthetic roleplay dialogues without ground truth PHQ-8.

---

## Dataset Splits

### AVEC 2017 Official Splits

| Split | Participants | PHQ-8 Labels | Purpose |
|-------|--------------|--------------|---------|
| **Train** | 107 | Yes | Model training |
| **Dev** | 35 | Yes | Validation |
| **Test** | 47 | **No** (in `test_split_Depression_AVEC2017.csv`) | Competition evaluation |
| **Total** | 189 | 142 labeled (train+dev) | |

Notes:
- `test_split_Depression_AVEC2017.csv` is unlabeled and contains only `participant_ID` (lowercase) and `Gender`.
- Some DAIC-WOZ distributions (including this repo) also include `full_test_split.csv` with `PHQ_Score`/`PHQ_Binary` for the 47 test IDs; treat this as **non-AVEC** and avoid using it for model selection or training unless you explicitly want a 189-labeled setting.

### Paper Splits (Research Reproduction)

Alternative splits used in published research (reverse-engineered from paper outputs):

| Split | Participants | Source |
|-------|--------------|--------|
| **Train** | 58 | `paper_splits/paper_split_train.csv` |
| **Val** | 43 | `paper_splits/paper_split_val.csv` |
| **Test** | 41 | `paper_splits/paper_split_test.csv` |
| **Total** | 142 | All labeled participants |

See `paper_splits/paper_split_metadata.json` for derivation methodology.

---

## Schema

### Train/Dev Labels CSV (`train_split_Depression_AVEC2017.csv`, `dev_split_Depression_AVEC2017.csv`)

| Field | Type | Description |
|-------|------|-------------|
| `Participant_ID` | int | Unique participant ID (300-492) |
| `PHQ8_Binary` | int | 1 if PHQ8_Score >= 10, else 0 |
| `PHQ8_Score` | int | Total PHQ-8 score (0-24; observed max 23 in train+dev) |
| `Gender` | int | 0 = male, 1 = female |
| `PHQ8_NoInterest` | int | Item 1: Anhedonia (0-3) |
| `PHQ8_Depressed` | int | Item 2: Depressed mood (0-3) |
| `PHQ8_Sleep` | int | Item 3: Sleep problems (0-3) |
| `PHQ8_Tired` | int | Item 4: Fatigue (0-3) |
| `PHQ8_Appetite` | int | Item 5: Appetite changes (0-3) |
| `PHQ8_Failure` | int | Item 6: Guilt/failure (0-3) |
| `PHQ8_Concentrating` | int | Item 7: Concentration (0-3) |
| `PHQ8_Moving` | int | Item 8: Psychomotor (0-3) |

**PHQ-8 Item Mapping** (for cross-reference with vibe-check):

| DAIC-WOZ Column | vibe-check Item Key |
|-----------------|---------------------|
| `PHQ8_NoInterest` | `anhedonia` |
| `PHQ8_Depressed` | `depressed_mood` |
| `PHQ8_Sleep` | `sleep` |
| `PHQ8_Tired` | `fatigue` |
| `PHQ8_Appetite` | `appetite` |
| `PHQ8_Failure` | `guilt` |
| `PHQ8_Concentrating` | `concentration` |
| `PHQ8_Moving` | `psychomotor` |

### Test Split CSV (`test_split_Depression_AVEC2017.csv`)

This file is **unlabeled** in the official AVEC packaging:
- `participant_ID` (int, note lowercase `p`)
- `Gender` (int; 0 = male, 1 = female)

### Optional Full Test Labels (`full_test_split.csv`)

If present, this file contains **test totals only** (no per-item PHQ-8 columns):
- `Participant_ID` (int)
- `PHQ_Binary` (int; 1 iff `PHQ_Score >= 10`)
- `PHQ_Score` (int; 0-24)
- `Gender` (int)

### Transcripts

**Full transcripts**: `transcripts/{PID}_P/{PID}_TRANSCRIPT.csv` (tab-separated, despite `.csv` extension)

| Field | Type | Description |
|-------|------|-------------|
| `start_time` | float | Utterance start (seconds) |
| `stop_time` | float | Utterance end (seconds) |
| `speaker` | string | `Ellie` (interviewer) or `Participant` |
| `value` | string | Utterance text |

**Participant-only**: `transcripts_participant_only/{PID}_P/{PID}_TRANSCRIPT.csv`

Same schema but filtered to `speaker == Participant` only.

---

## Interview Structure

Unlike SQPsychConv (therapy roleplay), DAIC-WOZ interviews follow a **semi-structured format**:

1. **Rapport building**: "How are you doing today?", "Where are you from?"
2. **Life questions**: Work, family, relationships, memorable experiences
3. **Mental health probes**: Sleep, stress, mood (embedded naturally)
4. **Closing**: "Is there anything else you'd like to share?"

**Key insight for PHQ-8 scoring**: PHQ-8 items are NOT explicitly asked. The interviewer asks open-ended questions, and participants may or may not mention symptoms relevant to each PHQ-8 domain.

---

## Data Quality Notes

### Patched Values

Two upstream data issues were corrected (see `DATA_PROVENANCE.md`):

| Participant | Issue | Fix |
|-------------|-------|-----|
| **319** | Missing `PHQ8_Sleep` | Reconstructed as **2** via sum invariant |
| **409** | Incorrect `PHQ8_Binary` | Corrected to **1** (score=10 meets threshold) |

### Label Distribution

**Train + Dev combined (142 participants)**:

| PHQ8_Binary | Count | Percentage |
|-------------|-------|------------|
| 0 (control) | 99 | 69.7% |
| 1 (depression) | 43 | 30.3% |

Train: 76 control / 31 depression. Dev: 23 control / 12 depression.

**PHQ-8 Score Distribution**:

| Severity | Score Range | Count | Percentage |
|----------|-------------|-------|------------|
| None/minimal | 0-4 | 64 | 45.1% |
| Mild | 5-9 | 35 | 24.6% |
| Moderate | 10-14 | 25 | 17.6% |
| Moderately severe | 15-19 | 13 | 9.2% |
| Severe | 20-24 | 5 | 3.5% |

### Known Upstream Transcript Issues

These are not fatal for text-only experiments, but they matter for multimodal/audio alignment pipelines:
- Long interruptions: sessions 373, 444
- Missing Ellie transcriptions in some files: sessions 451, 458, 480
- Transcript/audio misalignment: sessions 318, 321, 341, 362

---

## Transcript Statistics

| Metric | Value |
|--------|-------|
| Total transcripts | 189 |
| Official labeled transcripts (train+dev) | 142 |
| Total utterances (full transcripts) | 47,400 |
| Avg utterances per transcript | 250.8 |
| Avg participant utterances per transcript | 170.4 |

---

## Local File Structure

```
data/daic-woz/
├── DATA_PROVENANCE.md              # Patch documentation
├── train_split_Depression_AVEC2017.csv   # AVEC train (107, labeled)
├── dev_split_Depression_AVEC2017.csv     # AVEC dev (35, labeled)
├── test_split_Depression_AVEC2017.csv    # AVEC test (47, no PHQ labels; columns: participant_ID, Gender)
├── full_test_split.csv                   # Optional test labels (totals only; columns: PHQ_Score, PHQ_Binary, Gender)
│
├── paper_splits/                   # Research reproduction splits
│   ├── paper_split_train.csv       # 58 participants
│   ├── paper_split_val.csv         # 43 participants
│   ├── paper_split_test.csv        # 41 participants
│   └── paper_split_metadata.json   # Derivation methodology
│
├── transcripts/                    # Full transcripts (Ellie + Participant)
│   └── {PID}_P/{PID}_TRANSCRIPT.csv
│
├── transcripts_participant_only/   # Participant utterances only
│   └── {PID}_P/{PID}_TRANSCRIPT.csv
│
├── embeddings/                     # Pre-computed embeddings
│   └── *.npz, *.json, *.meta.json
│
├── experiments/                    # Experiment configs
│   └── registry.yaml
│
└── outputs/                        # Model outputs
```

---

## Usage

### Load Labels

```python
import pandas as pd

# AVEC splits
train = pd.read_csv("data/daic-woz/train_split_Depression_AVEC2017.csv")
dev = pd.read_csv("data/daic-woz/dev_split_Depression_AVEC2017.csv")

# Paper splits (for research reproduction)
paper_train = pd.read_csv("data/daic-woz/paper_splits/paper_split_train.csv")
```

### Load Transcript

```python
import pandas as pd

pid = 303
transcript = pd.read_csv(f"data/daic-woz/transcripts/{pid}_P/{pid}_TRANSCRIPT.csv", sep="\t")
participant_only = transcript[transcript["speaker"] == "Participant"]
```

### Verify Data Integrity

```bash
# Check sum invariant holds for all participants
uv run python -c "
import pandas as pd
train = pd.read_csv('data/daic-woz/train_split_Depression_AVEC2017.csv')
dev = pd.read_csv('data/daic-woz/dev_split_Depression_AVEC2017.csv')
item_cols = ['PHQ8_NoInterest', 'PHQ8_Depressed', 'PHQ8_Sleep', 'PHQ8_Tired',
             'PHQ8_Appetite', 'PHQ8_Failure', 'PHQ8_Concentrating', 'PHQ8_Moving']
for df, name in [(train, 'train'), (dev, 'dev')]:
    sums = df[item_cols].sum(axis=1)
    mismatches = df[sums != df['PHQ8_Score']]
    print(f'{name}: {len(mismatches)} mismatches')
"
```

---

## Relationship to vibe-check Pipeline

```
SQPsychConv (synthetic)              DAIC-WOZ (real)
2,090 dialogues                      142 labeled interviews (official train+dev)
NO ground truth PHQ-8                HAS ground truth PHQ-8
        │                                   │
        ▼                                   │
┌──────────────────────┐                    │
│ vibe-check           │                    │
│ Assign PHQ-8 labels  │                    │
└──────────┬───────────┘                    │
           │                                │
           ▼                                ▼
┌──────────────────────────────────────────────────────┐
│ ai-psychiatrist: Compare predicted vs ground truth   │
│ - Train embeddings on labeled SQPsychConv            │
│ - Transfer to predict on DAIC-WOZ                    │
│ - Evaluate against DAIC-WOZ ground truth             │
└──────────────────────────────────────────────────────┘
```

**DAIC-WOZ serves as the VALIDATION corpus** for transfer learning experiments.

---

## Domain Shift Analysis (Keyword Heuristics)

Results from `scripts/corpus_comparison.py` (2026-01-06):

### Overall Coverage

| Metric | SQPsychConv | DAIC-WOZ | Assessment |
|--------|-------------|----------|------------|
| **Corpus size** | 2,090 | 189 | |
| **Avg word count** | 1,040 | 1,469 | DAIC-WOZ ~40% longer |
| **Avg items mentioned** | 4.68/8 (58.5%) | 4.42/8 (55.3%) | **Similar** |

### Per-Item Coverage Rates

| Item | SQPsychConv | DAIC-WOZ | Δ | Risk |
|------|-------------|----------|---|------|
| anhedonia | 31.1% | 77.2% | **-46.1%** | ⚠️ HIGH |
| depressed_mood | 89.9% | 66.7% | +23.2% | ⚠️ HIGH |
| sleep | 77.6% | 85.2% | -7.6% | ✅ OK |
| fatigue | 80.6% | 56.1% | +24.5% | ⚠️ HIGH |
| appetite | 19.5% | 47.6% | **-28.1%** | ⚠️ HIGH |
| guilt | 37.2% | 54.0% | -16.7% | ⚠️ MODERATE |
| concentration | 89.4% | 23.3% | **+66.1%** | ⚠️ HIGH |
| psychomotor | 43.1% | 32.3% | +10.8% | ✅ OK |

### Interpretation

**Good news**: Overall coverage is similar (~55-58%). Both corpora discuss roughly 4-5/8 PHQ-8 items on average.

**Bad news**: Per-item coverage differs significantly for 6/8 items:
- **concentration**: SQPsychConv discusses it 89% of the time, DAIC-WOZ only 23%
- **anhedonia**: DAIC-WOZ discusses it 77% of the time, SQPsychConv only 31%
- **appetite**: DAIC-WOZ discusses it 48% of the time, SQPsychConv only 20%

**Implications**:
1. If we train embeddings that rely heavily on "concentration" signal, they may not transfer well
2. NA patterns are DIFFERENT between corpora - don't over-encode missingness
3. Use **masked per-item representations** rather than totals for transfer learning

### Coverage Distribution

| Items Mentioned | SQPsychConv | DAIC-WOZ |
|-----------------|-------------|----------|
| 0-2 items | 4.7% | 13.8% |
| 3-4 items | 37.3% | 33.3% |
| 5-6 items | 52.2% | 47.1% |
| 7-8 items | 5.8% | 5.8% |

**Similar overall distribution** - most dialogues in both corpora discuss 4-6 items.

### Keyword Heuristic Limitations

This analysis uses simple keyword matching - NOT clinical NLP. False positives/negatives are expected:
- "concentrate" in "I need to concentrate on work" ≠ PHQ-8 concentration problems
- "tired" in "I'm tired of this job" ≠ PHQ-8 fatigue
- "fun/hobby/interest" mentions are often generic (especially in DAIC-WOZ) and do not imply loss of interest/pleasure

The actual NA rates from vibe-check scoring will differ; treat these as a screening signal and validate with pilot scoring.

---

## References

- Gratch et al. (2014). "The Distress Analysis Interview Corpus of human and computer interviews" (LREC). `http://www.lrec-conf.org/proceedings/lrec2014/pdf/508_Paper.pdf`
- Ringeval et al. (2017). "AVEC 2017 - Real-life Depression, and Affect Recognition Workshop and Challenge". `https://hal.science/hal-02080874` (PDF: `https://hal.science/hal-02080874v1/file/Ringeval17-A2R.pdf`)
- Bailey & Plumbley (2021). "Gender Bias in Depression Detection Using Audio Features" (DAIC-WOZ split sizes + label availability). `https://arxiv.org/abs/2010.15120`
- Kroenke et al. (2009). "The PHQ-8 as a measure of current depression in the general population". `https://pubmed.ncbi.nlm.nih.gov/18752852/`

---

## Related Documentation

- [Data Provenance](../../data/daic-woz/DATA_PROVENANCE.md) - Patch details
- [Paper Split Registry](paper-split-registry.md) - Research reproduction methodology
- [SQPsychConv Dataset](dataset-sqpsychconv-all-variants.md) - Training corpus
