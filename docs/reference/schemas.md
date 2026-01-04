# Schemas Reference

All Pydantic data models used in vibe-check.

---

## Input Schemas

### SQPsychConvDialogue

Input corpus record from SQPsychConv dataset.

**File**: `schemas/input.py`

| Field | Type | Description |
|-------|------|-------------|
| `file_id` | `str` | Unique identifier (e.g., "active436") |
| `condition` | `Literal["mdd", "control"]` | "mdd" or "control" |
| `client_model` | `str` | LLM used for synthetic client |
| `therapist_model` | `str` | LLM used for synthetic therapist |
| `dialogue` | `str` | Raw dialogue text |
| `computed_split` | `Literal["train", "dev", "test"] \| None` | Deterministic split (may be null) |

**Example**:

```json
{
  "file_id": "active436",
  "condition": "mdd",
  "client_model": "qwen-2.5",
  "therapist_model": "qwen-2.5",
  "dialogue": "Therapist: How have you been feeling?\nClient: Not great...",
  "computed_split": "train"
}
```

---

### DialogueViews

Preprocessed dialogue views.

**File**: `schemas/views.py`

| Field | Type | Description |
|-------|------|-------------|
| `file_id` | `str` | Identifier |
| `dialogue_clean` | `str` | Normalized full dialogue |
| `client_only_text` | `str` | Client utterances only |
| `client_qa_text` | `str` | Client + therapist questions |
| `client_utterance_count` | `int` | Number of client turns |
| `therapist_utterance_count` | `int` | Number of therapist turns |
| `short_answer_count` | `int` | Client responses < 5 words |
| `has_empty_client_text` | `bool` | True if no client text |
| `has_unknown_speaker` | `bool` | True if unknown speakers found |

**Example**:

```json
{
  "file_id": "active436",
  "dialogue_clean": "Therapist: How have you been?\nClient: Not well.",
  "client_only_text": "Not well.",
  "client_qa_text": "Therapist: How have you been?\nClient: Not well.",
  "client_utterance_count": 8,
  "therapist_utterance_count": 9,
  "short_answer_count": 2,
  "has_empty_client_text": false,
  "has_unknown_speaker": false
}
```

---

## Scoring Schemas

### PHQ8ItemScore

Single PHQ-8 item score from a juror.

**File**: `schemas/scoring.py`

| Field | Type | Description |
|-------|------|-------------|
| `score` | `0 \| 1 \| 2 \| 3` | Item score |
| `confidence` | `float` | Confidence (0.0-1.0) |
| `evidence` | `list[str]` | Up to 3 supporting quotes |
| `insufficient_evidence` | `bool` | True if evidence lacking |

**Example**:

```json
{
  "score": 2,
  "confidence": 0.85,
  "evidence": [
    "I haven't enjoyed anything lately",
    "Activities feel empty"
  ],
  "insufficient_evidence": false
}
```

---

### PHQ8Assessment

Raw LLM output from juror.

**File**: `schemas/scoring.py`

| Field | Type | Description |
|-------|------|-------------|
| `anhedonia` | `PHQ8ItemScore` | Item 1 |
| `depressed_mood` | `PHQ8ItemScore` | Item 2 |
| `sleep` | `PHQ8ItemScore` | Item 3 |
| `fatigue` | `PHQ8ItemScore` | Item 4 |
| `appetite` | `PHQ8ItemScore` | Item 5 |
| `guilt` | `PHQ8ItemScore` | Item 6 |
| `concentration` | `PHQ8ItemScore` | Item 7 |
| `psychomotor` | `PHQ8ItemScore` | Item 8 |
| `total_score` | `int` | Sum of items (0-24) |
| `mentions_self_harm` | `bool` | Self-harm detected |
| `self_harm_evidence` | `list[str]` | Supporting quotes |

---

### PHQ8Report

Full juror report with metadata.

**File**: `schemas/scoring.py`

Extends `PHQ8Assessment` with:

| Field | Type | Description |
|-------|------|-------------|
| `model_id` | `str` | Model identifier |
| `run_number` | `int` | Run number (1 or 2) |
| `usage` | `TokenUsage \| None` | Token counts |
| `scored_at` | `datetime` | Timestamp |

**Example**:

```json
{
  "anhedonia": {"score": 2, "confidence": 0.85, ...},
  "depressed_mood": {"score": 3, "confidence": 0.92, ...},
  "sleep": {"score": 2, "confidence": 0.78, ...},
  "fatigue": {"score": 2, "confidence": 0.80, ...},
  "appetite": {"score": 1, "confidence": 0.70, ...},
  "guilt": {"score": 3, "confidence": 0.88, ...},
  "concentration": {"score": 2, "confidence": 0.75, ...},
  "psychomotor": {"score": 1, "confidence": 0.65, ...},
  "total_score": 16,
  "mentions_self_harm": false,
  "self_harm_evidence": [],
  "model_id": "gpt-5.2",
  "run_number": 1,
  "usage": {
    "input_tokens": 1250,
    "output_tokens": 450,
    "reasoning_tokens": null,
    "total_tokens": 1700
  },
  "scored_at": "2026-01-03T12:34:56Z"
}
```

---

### TokenUsage

Token counts from LLM call.

**File**: `schemas/scoring.py`

| Field | Type | Description |
|-------|------|-------------|
| `input_tokens` | `int \| None` | Input token count |
| `output_tokens` | `int \| None` | Output token count |
| `reasoning_tokens` | `int \| None` | Reasoning tokens (if applicable) |
| `total_tokens` | `int \| None` | Total tokens |

---

## Aggregation Schemas

### ItemAggregation

Per-item aggregation statistics.

**File**: `schemas/output.py`

| Field | Type | Description |
|-------|------|-------------|
| `votes` | `list[int]` | All juror votes |
| `vote_counts` | `dict[str, int]` | Count per score |
| `posterior` | `dict[str, float]` | Probability distribution |
| `mode` | `int` | Most likely score |
| `expected` | `float` | Expected value |
| `entropy` | `float` | Shannon entropy |
| `vote_range` | `int` | Max - min vote |
| `clinical_prob` | `float` | P(score >= 2) |
| `needs_arbitration` | `bool` | Arbitration triggered |
| `arbitration_reason` | `str \| None` | Why arbitration needed |

**Example**:

```json
{
  "votes": [1, 2, 1, 2, 1, 2],
  "vote_counts": {"0": 0, "1": 3, "2": 3, "3": 0},
  "posterior": {"0": 0.083, "1": 0.417, "2": 0.417, "3": 0.083},
  "mode": 1,
  "expected": 1.5,
  "entropy": 1.05,
  "vote_range": 1,
  "clinical_prob": 0.50,
  "needs_arbitration": false,
  "arbitration_reason": null
}
```

---

### AggregatedPHQ8

Final aggregated output.

**File**: `schemas/output.py`

| Field | Type | Description |
|-------|------|-------------|
| `file_id` | `str` | Dialogue identifier |
| `condition` | `Literal["mdd", "control"]` | "mdd" or "control" |
| `items` | `dict[str, ItemAggregation]` | Per-item stats |
| `total_mode` | `int` | Mode of total distribution |
| `total_expected` | `float` | Expected total |
| `total_std` | `float` | Standard deviation |
| `total_posterior` | `dict[int, float]` | Total score distribution |
| `total_ci_90` | `tuple[int, int]` | 90% credible interval |
| `severity_bucket` | `Literal["0-4", "5-9", "10-14", "15-19", "20-24"]` | Severity classification |
| `severity_bucket_probs` | `dict[str, float]` | Bucket probabilities |
| `final_item_scores` | `dict[str, int]` | Final scores per item |
| `final_total_score` | `int` | Final total (0-24) |
| `final_severity_bucket` | `Literal["0-4", "5-9", "10-14", "15-19", "20-24"]` | Final severity |
| `final_source` | `Literal["jury_mode", "jury_expected", "judge_override"]` | Source of final scores |
| `triggered_arbitration` | `bool` | Judge invoked |
| `arbitration_items` | `list[str]` | Items arbitrated |
| `arbitration_reasons` | `dict[str, str]` | Why each item |
| `mentions_self_harm` | `bool` | Any juror flagged self-harm |
| `self_harm_evidence` | `list[str]` | Combined evidence |
| `juror_reports` | `list[PHQ8Report]` | All 6 reports |
| `judge_resolution` | `dict \| None` | Judge decisions |
| `judge_usage` | `TokenUsage \| None` | Aggregated judge token usage |
| `prompt_version` | `str` | Prompt version |
| `scored_at` | `datetime` | Timestamp |

---

## Judge Schemas

### JudgeItemResolution

Judge decision for one item.

**File**: `judge/schema.py`

| Field | Type | Description |
|-------|------|-------------|
| `item` | `str` | Item name |
| `final_score` | `0 \| 1 \| 2 \| 3` | Judge's score |
| `confidence` | `float` | Confidence (0.0-1.0) |
| `rationale` | `str` | Explanation |

**Example**:

```json
{
  "item": "anhedonia",
  "final_score": 2,
  "confidence": 0.85,
  "rationale": "Client explicitly states lack of enjoyment in multiple activities."
}
```

---

### JudgeItemReport

Judge decision with token usage metadata.

**File**: `judge/schema.py`

Extends `JudgeItemResolution` with:

| Field | Type | Description |
|-------|------|-------------|
| `usage` | `TokenUsage \| None` | Token counts for this judge call |

**Example**:

```json
{
  "item": "anhedonia",
  "final_score": 2,
  "confidence": 0.85,
  "rationale": "Client explicitly states lack of enjoyment in multiple activities.",
  "usage": {
    "input_tokens": 2500,
    "output_tokens": 150,
    "reasoning_tokens": null,
    "total_tokens": 2650
  }
}
```

---

## Export Schemas

### ScoredDialogueExport

Public export format.

**File**: `export/schemas.py`

| Field | Type | Description |
|-------|------|-------------|
| `dialogue_id` | `str` | Identifier |
| `condition` | `Literal["mdd", "control"]` | "mdd" or "control" |
| `phq8_item_1` | `int` | Anhedonia score |
| `phq8_item_2` | `int` | Depressed mood score |
| `phq8_item_3` | `int` | Sleep score |
| `phq8_item_4` | `int` | Fatigue score |
| `phq8_item_5` | `int` | Appetite score |
| `phq8_item_6` | `int` | Guilt score |
| `phq8_item_7` | `int` | Concentration score |
| `phq8_item_8` | `int` | Psychomotor score |
| `phq8_total` | `int` | Total (0-24) |
| `severity_bucket` | `Literal["0-4", "5-9", "10-14", "15-19", "20-24"]` | Severity classification |
| `client_qa_text` | `str` | Scoring text |
| `juror_votes` | `dict[str, list[int]]` | All votes per item |
| `arbitration_triggered` | `dict[str, bool]` | Per-item arbitration flags |
| `run_id` | `str` | Run identifier |
| `prompt_version` | `str` | Prompt version |

**Example**:

```json
{
  "dialogue_id": "active436",
  "condition": "mdd",
  "phq8_item_1": 2,
  "phq8_item_2": 3,
  "phq8_item_3": 2,
  "phq8_item_4": 2,
  "phq8_item_5": 1,
  "phq8_item_6": 3,
  "phq8_item_7": 2,
  "phq8_item_8": 1,
  "phq8_total": 16,
  "severity_bucket": "15-19",
  "client_qa_text": "Therapist: How have you been?\nClient: Not well...",
  "juror_votes": {
    "anhedonia": [1, 2, 2, 2, 1, 2],
    "depressed_mood": [3, 3, 3, 2, 3, 3]
  },
  "arbitration_triggered": {"anhedonia": false, "depressed_mood": true},
  "run_id": "2026-01-03_production",
  "prompt_version": "v1.0.0"
}
```

---

## Diagnostics Schemas

### DiagnosticReport

Quality metrics report.

**File**: `diagnostics/report.py`

| Field | Type | Description |
|-------|------|-------------|
| `run_id` | `str` | Run identifier |
| `computed_at` | `datetime` | When diagnostics were computed |
| `n_dialogues` | `int` | Total dialogues |
| `n_mdd` | `int` | MDD count |
| `n_control` | `int` | Control count |
| `reliability` | `ReliabilityMetrics` | Agreement metrics |
| `consistency` | `ConsistencyMetrics` | Internal consistency |
| `separation` | `SeparationMetrics` | Condition separation |
| `arbitration` | `ArbitrationMetrics` | Arbitration stats |
| `passes_reliability_gate` | `bool` | α ≥ 0.67 |
| `passes_consistency_gate` | `bool` | α ≥ 0.70 |
| `passes_separation_gate` | `bool` | MDD > Control, p < 0.01, d ≥ 0.5 |
| `passes_arbitration_gate` | `bool` | Rate < 30% |
