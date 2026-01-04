# Data Flow

This document traces the complete journey of data through the vibe-check system.

---

## Stage 1: Corpus Loading

**Input**: HuggingFace Arrow files or CSV

**Output**: `list[SQPsychConvDialogue]`

```
data/sqpsychconv/qwen-2.5/
├── train/data-00000-of-00001.arrow
└── test/data-00000-of-00001.arrow
         │
         ▼
    load_corpus()
         │
         ▼
list[SQPsychConvDialogue]
```

### Schema: SQPsychConvDialogue

```python
class SQPsychConvDialogue(BaseModel):
    file_id: str                           # "active436"
    condition: Literal["mdd", "control"]   # MDD or control group
    client_model: str                      # "qwen-2.5"
    therapist_model: str                   # "qwen-2.5"
    dialogue: str                          # Raw dialogue text
    computed_split: SplitName | None = None  # "train", "dev", "test", or None
```

---

## Stage 2: Preprocessing

**Input**: `SQPsychConvDialogue`

**Output**: `DialogueViews`

```
SQPsychConvDialogue
      │
      ▼
preprocess_dialogue()
      │
      ├── Parse speaker labels
      ├── Remove artifacts
      └── Build views
      │
      ▼
DialogueViews
```

### Schema: DialogueViews

```python
class DialogueViews(BaseModel):
    file_id: str
    dialogue_clean: str      # Normalized full dialogue
    client_only_text: str    # Client utterances only
    client_qa_text: str      # Client + therapist questions
    client_utterance_count: int
    therapist_utterance_count: int
    short_answer_count: int
    has_empty_client_text: bool = False
    has_unknown_speaker: bool = False
```

---

## Stage 3: Juror Scoring

**Input**: `scoring_text` (from selected view)

**Output**: `PHQ8Report` (per juror)

```
scoring_text
      │
      ├──────────────────────────────────────────┐
      │         │         │         │         │  │
      ▼         ▼         ▼         ▼         ▼  ▼
  Juror 1   Juror 2   Juror 3   Juror 4   Juror 5   Juror 6
      │         │         │         │         │  │
      ▼         ▼         ▼         ▼         ▼  ▼
 PHQ8Report PHQ8Report PHQ8Report PHQ8Report PHQ8Report PHQ8Report
```

### Schema: PHQ8Report

```python
class PHQ8Report(PHQ8Assessment):
    # 8 PHQ items
    anhedonia: PHQ8ItemScore
    depressed_mood: PHQ8ItemScore
    sleep: PHQ8ItemScore
    fatigue: PHQ8ItemScore
    appetite: PHQ8ItemScore
    guilt: PHQ8ItemScore
    concentration: PHQ8ItemScore
    psychomotor: PHQ8ItemScore

    total_score: int  # 0-24

    mentions_self_harm: bool = False
    self_harm_evidence: list[str] = Field(default_factory=list, max_length=3)

    # Metadata
    model_id: str
    run_number: int
    usage: TokenUsage | None
    scored_at: datetime

class PHQ8ItemScore(BaseModel):
    score: Literal[0, 1, 2, 3]
    confidence: float  # 0.0-1.0
    evidence: list[str] = Field(default_factory=list, max_length=3)  # Up to 3 quotes
    insufficient_evidence: bool = False
```

---

## Stage 4: Aggregation

**Input**: `list[PHQ8Report]` (default: 6 reports)

**Output**: `AggregatedPHQ8`

```
N × PHQ8Report (default: 6)
      │
      ▼
aggregate_reports()
      │
      ├── Collect votes per item
      ├── Compute Dirichlet posteriors
      ├── Convolve for total distribution
      ├── Detect arbitration triggers
      └── Compute final scores
      │
      ▼
AggregatedPHQ8
```

### Schema: AggregatedPHQ8

```python
class AggregatedPHQ8(BaseModel):
    # Identity
    file_id: str
    condition: Literal["mdd", "control"]

    # Per-item aggregation (8 items)
    items: dict[str, ItemAggregation]

    # Total score distribution (0-24)
    total_mode: int           # Most probable total
    total_expected: float     # Expected value
    total_std: float          # Standard deviation
    total_posterior: dict[int, float]  # P(total=k) for k in 0-24
    total_ci_90: tuple[int, int]       # 90% credible interval

    # Severity (from posterior mode)
    severity_bucket: SeverityBucket    # "0-4", "5-9", "10-14", "15-19", "20-24"
    severity_bucket_probs: dict[str, float]

    # Final results (may be updated by judge)
    final_item_scores: dict[str, int]      # {"anhedonia": 1, ...}
    final_total_score: int                 # 0-24
    final_severity_bucket: SeverityBucket
    final_source: Literal["jury_mode", "jury_expected", "judge_override"]

    # Arbitration metadata
    triggered_arbitration: bool
    arbitration_items: list[str]           # Items needing judge review
    arbitration_reasons: dict[str, str]    # Why each item was flagged

    # Safety signals
    mentions_self_harm: bool
    self_harm_evidence: list[str]

    # Provenance
    juror_reports: list[PHQ8Report]        # All 6 juror outputs
    judge_resolution: dict[str, Any] | None  # Judge decisions if arbitrated
    judge_usage: TokenUsage | None          # Aggregated judge token usage (if arbitrated)

    prompt_version: str
    scored_at: datetime


class ItemAggregation(BaseModel):
    votes: list[int]               # [1, 2, 1, 1, 2, 2] from 6 jurors
    vote_counts: dict[str, int]    # {"0": 0, "1": 2, "2": 4, "3": 0}
    posterior: dict[str, float]    # Dirichlet posterior probabilities

    mode: int                      # 0-3
    expected: float                # 0.0-3.0
    entropy: float                 # Shannon entropy (uncertainty)
    vote_range: int                # max - min vote
    clinical_prob: float           # P(score >= 2)

    needs_arbitration: bool
    arbitration_reason: str | None
```

---

## Stage 5: Judge Resolution (Optional)

**Input**: Contested item + evidence

**Output**: `JudgeItemReport`

```
AggregatedPHQ8 (with arbitration_items)
      │
      ▼
For each contested item:
      │
      ├── Build judge prompt with:
      │   • Scoring text
      │   • Juror votes
      │   • Juror evidence
      │
      ▼
  Judge LLM
      │
      ▼
JudgeItemReport
      │
      ▼
Update final_item_scores
```

### Schema: JudgeItemReport

```python
class JudgeItemResolution(BaseModel):
    item: str                       # "anhedonia"
    final_score: Literal[0, 1, 2, 3]  # PHQ-8 score
    confidence: float               # 0.0-1.0
    rationale: str                  # Explanation


class JudgeItemReport(JudgeItemResolution):
    usage: TokenUsage | None = None  # Token usage metadata (if available)
```

---

## Stage 6: Persistence

**Input**: `AggregatedPHQ8`

**Output**: `scored.jsonl` + ledger update

```
AggregatedPHQ8
      │
      ├──────────────┬────────────────┐
      ▼              ▼                ▼
scored.jsonl   run_manifest.json   ledger.sqlite
(materialize)  (end-of-run stats) (mark done)
```

---

## Stage 7: Diagnostics

**Input**: `scored.jsonl`

**Output**: `DiagnosticReport`

```
scored.jsonl
      │
      ▼
RunDiagnostics.compute()
      │
      ├── Load all rows
      ├── Compute reliability (Krippendorff α)
      ├── Compute consistency (Cronbach α)
      ├── Compute separation (MDD vs Control)
      └── Compute arbitration stats
      │
      ▼
DiagnosticReport
```

---

## Stage 8: Export

**Input**: `scored.jsonl`

**Output**: `vibe_check_labels.jsonl` + `vibe_check_labels.csv`

```
scored.jsonl (internal format)
      │
      ▼
write_label_exports()
      │
      ├── Flatten AggregatedPHQ8 → ScoredDialogueExport
      ├── Write JSONL
      └── Write CSV
      │
      ▼
vibe_check_labels.jsonl  vibe_check_labels.csv (public format)
```

### Schema: ScoredDialogueExport

```python
class ScoredDialogueExport(BaseModel):
    dialogue_id: str
    condition: Literal["mdd", "control"]

    phq8_item_1: int  # 0-3 (anhedonia)
    phq8_item_2: int  # 0-3 (depressed_mood)
    phq8_item_3: int  # 0-3 (sleep)
    phq8_item_4: int  # 0-3 (fatigue)
    phq8_item_5: int  # 0-3 (appetite)
    phq8_item_6: int  # 0-3 (guilt)
    phq8_item_7: int  # 0-3 (concentration)
    phq8_item_8: int  # 0-3 (psychomotor)

    phq8_total: int   # 0-24 (validated sum of items)
    severity_bucket: SeverityBucket  # "0-4", "5-9", etc.

    client_qa_text: str

    juror_votes: dict[str, list[int]]      # {"anhedonia": [1, 2, 1, ...], ...}
    arbitration_triggered: dict[str, bool]  # {"anhedonia": false, ...}

    run_id: str
    prompt_version: str
```

---

## Complete Flow Summary

```
Arrow/CSV
    ↓
SQPsychConvDialogue
    ↓
DialogueViews
    ↓
scoring_text (client_qa)
    ↓
6 × PHQ8Report
    ↓
AggregatedPHQ8
    ↓ (if arbitration)
AggregatedPHQ8 (updated)
    ↓
scored.jsonl
    ↓
DiagnosticReport
    ↓
vibe_check_labels.jsonl / vibe_check_labels.csv
```
