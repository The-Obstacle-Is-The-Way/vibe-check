# SPEC-08: Label Export Contract

**Status**: DRAFT (2026-01-02)
**Slice Type**: Vertical (Scored Corpus → Label Export)
**Dependencies**: SPEC-06 (Batch Runner & Export)
**Estimated Scope**: ~50 lines of code, ~50 lines of tests

---

## 1. Objective

Define the **label export format** for downstream consumption. vibe-check produces PHQ-8 labels; consumers (like `ai-psychiatrist`) generate their own embeddings.

> **CRITICAL SCOPE BOUNDARY**
>
> | Repo | Responsibility | Embeddings? |
> |------|----------------|-------------|
> | **vibe-check** | Score SQPsychConv → PHQ-8 labels | **NO** |
> | **ai-psychiatrist** | Embed + retrieve + predict | **YES** (already has this) |
>
> vibe-check does NOT generate embeddings. That's ai-psychiatrist's job.

### Goals

1. **Export scored labels** in `.jsonl` and `.csv` formats
2. **Schema validation** to ensure output is parseable
3. **Clear contract** for downstream consumers

### Success Criteria

```python
from vibe_check.export import validate_label_export

result = validate_label_export("data/outputs/scored_sqpsychconv.jsonl")

assert result.is_valid
assert result.n_dialogues > 0
assert all(0 <= r.phq8_total <= 24 for r in result.records)
```

---

## 2. Deliverables

### 2.1 Export Files

| File | Format | Purpose |
|------|--------|---------|
| `scored_sqpsychconv.jsonl` | JSON Lines | Primary export (one record per dialogue) |
| `scored_sqpsychconv.csv` | CSV | Flat version for pandas/spreadsheets |
| `validation_report.json` | JSON | Inter-model agreement stats |

### 2.2 Source Files

| File | Purpose |
|------|---------|
| `src/vibe_check/export/__init__.py` | Package exports |
| `src/vibe_check/export/schemas.py` | Pydantic schemas for export records |
| `src/vibe_check/export/writer.py` | JSONL/CSV writers |
| `src/vibe_check/export/validator.py` | Schema validation |

---

## 3. Export Schema

### 3.1 JSONL Record Schema

```python
from pydantic import BaseModel, Field
from typing import Literal

class ScoredDialogueExport(BaseModel):
    """Single dialogue export record."""

    # Identity
    dialogue_id: str
    condition: Literal["mdd", "control"]

    # PHQ-8 Scores (THE PRIMARY OUTPUT)
    phq8_item_1: int = Field(ge=0, le=3)
    phq8_item_2: int = Field(ge=0, le=3)
    phq8_item_3: int = Field(ge=0, le=3)
    phq8_item_4: int = Field(ge=0, le=3)
    phq8_item_5: int = Field(ge=0, le=3)
    phq8_item_6: int = Field(ge=0, le=3)
    phq8_item_7: int = Field(ge=0, le=3)
    phq8_item_8: int = Field(ge=0, le=3)
    phq8_total: int = Field(ge=0, le=24)

    # Text (for downstream embedding - THEY do this, not us)
    client_qa_text: str

    # Provenance
    juror_votes: dict[str, list[int]]  # Per-item vote history
    arbitration_triggered: dict[str, bool]  # Which items needed judge
    run_id: str
```

### 3.2 CSV Schema

Flat version with columns:
```
dialogue_id,condition,phq8_item_1,...,phq8_item_8,phq8_total,client_qa_text,run_id
```

---

## 4. CLI Interface

```bash
# Export scored corpus to JSONL + CSV
uv run python -m vibe_check.cli export \
  --input data/outputs/run_manifest.json \
  --output-dir data/outputs/ \
  --format jsonl,csv

# Validate export
uv run python -m vibe_check.cli validate-export \
  --input data/outputs/scored_sqpsychconv.jsonl
```

---

## 5. Testing Strategy

- **Unit**: Schema validation edge cases
- **Integration**: Round-trip export → validate → load

---

## 6. Non-Goals

- **Embedding generation** (ai-psychiatrist's job)
- **Transfer evaluation** (ai-psychiatrist's job)
- **Real clinical data** (NEVER in vibe-check)

---

## 7. Anti-Patterns

> **DO NOT add embedding code to vibe-check.**
>
> The original SPEC-vibe-check.md included embedding generation as "Phase 2".
> This was SCOPE CREEP. Embeddings belong in ai-psychiatrist where:
> - The retrieval infrastructure already exists
> - DAIC-WOZ evaluation happens (locally)
> - Few-shot prompting is implemented
>
> vibe-check's ONLY job: Score SQPsychConv → Export labels.
