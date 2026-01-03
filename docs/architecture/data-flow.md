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
    file_id: str           # "active436"
    condition: str         # "mdd" or "control"
    client_model: str      # "qwen-2.5"
    therapist_model: str   # "qwen-2.5"
    dialogue: str          # Raw dialogue text
    computed_split: str    # "train", "dev", or "test"
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
    has_empty_client_text: bool
    has_unknown_speaker: bool
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
class PHQ8Report(BaseModel):
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

    mentions_self_harm: bool
    self_harm_evidence: list[str]

    # Metadata
    model_id: str
    run_number: int
    usage: TokenUsage | None
    scored_at: datetime

class PHQ8ItemScore(BaseModel):
    score: Literal[0, 1, 2, 3]
    confidence: float  # 0.0-1.0
    evidence: list[str]  # Up to 3 quotes
    insufficient_evidence: bool
```

---

## Stage 4: Aggregation

**Input**: `list[PHQ8Report]` (6 reports)

**Output**: `AggregatedPHQ8`

```
6 × PHQ8Report
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
    condition: str  # "mdd" or "control"

    # Per-item aggregation
    items: dict[str, ItemAggregation]

    # Total score distribution
    total_mode: int
    total_expected: float
    total_std: float
    total_posterior: dict[int, float]
    total_ci_90: tuple[int, int]

    # Severity
    severity_bucket: str
    severity_bucket_probs: dict[str, float]

    # Final results
    final_item_scores: dict[str, int]
    final_total_score: int
    final_severity_bucket: str
    final_source: str  # "jury_mode" or "judge_override"

    # Arbitration
    triggered_arbitration: bool
    arbitration_items: list[str]
    arbitration_reasons: dict[str, str]

    # Safety
    mentions_self_harm: bool
    self_harm_evidence: list[str]

    # Provenance
    juror_reports: list[PHQ8Report]
    judge_resolution: dict | None

    prompt_version: str
    scored_at: datetime

class ItemAggregation(BaseModel):
    votes: list[int]
    vote_counts: dict[str, int]
    posterior: dict[str, float]
    mode: int
    expected: float
    entropy: float
    vote_range: int
    clinical_prob: float
    needs_arbitration: bool
    arbitration_reason: str | None
```

---

## Stage 5: Judge Resolution (Optional)

**Input**: Contested item + evidence

**Output**: `JudgeItemResolution`

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
JudgeItemResolution
      │
      ▼
Update final_item_scores
```

### Schema: JudgeItemResolution

```python
class JudgeItemResolution(BaseModel):
    item: str           # "anhedonia"
    final_score: int    # 0, 1, 2, or 3
    confidence: float   # 0.0-1.0
    rationale: str      # Explanation
```

---

## Stage 6: Persistence

**Input**: `AggregatedPHQ8`

**Output**: JSONL row + ledger update

```
AggregatedPHQ8
      │
      ├──────────────┬────────────────┐
      ▼              ▼                ▼
scored.jsonl   run_manifest.json   ledger.db
(append row)   (update stats)    (mark done)
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

**Output**: `labels.jsonl` + `labels.csv`

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
labels.jsonl  labels.csv (public format)
```

### Schema: ScoredDialogueExport

```python
class ScoredDialogueExport(BaseModel):
    dialogue_id: str
    condition: str
    phq8_item_1: int
    phq8_item_2: int
    phq8_item_3: int
    phq8_item_4: int
    phq8_item_5: int
    phq8_item_6: int
    phq8_item_7: int
    phq8_item_8: int
    phq8_total: int
    severity_bucket: str
    client_qa_text: str
    juror_votes: dict[str, list[int]]
    arbitration_triggered: bool
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
labels.jsonl / labels.csv
```
