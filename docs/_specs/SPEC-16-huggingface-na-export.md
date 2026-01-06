# SPEC-16: HuggingFace NA-Aware Export

> **Status**: DRAFT - Pending Senior Review
> **Depends On**: SPEC-13 (Schema), SPEC-15 (Aggregation)
> **Blocks**: ai-psychiatrist integration

---

## 1. Overview

This spec defines TDD requirements for a new NA-aware export format for HuggingFace. This is **separate from SPEC-08** which remains unchanged (int-only).

**Core Change**: New export module that preserves `null` scores, assertions, and full provenance.

---

## 2. Design Decision: Separate Export Module

### 2.1 Why Not Modify SPEC-08?

1. **SPEC-08 is a public contract** - existing consumers expect int-only fields
2. **Breaking change** - changing `int` to `int | null` breaks Pydantic validation
3. **Different use cases** - SPEC-08 for legacy ML, HuggingFace for NA-aware research

### 2.2 Module Structure

```
src/vibe_check/export/
├── schemas.py              # SPEC-08 (UNCHANGED)
├── writer.py               # SPEC-08 writer (UNCHANGED)
├── validator.py            # SPEC-08 validator (UNCHANGED)
├── huggingface_schema.py   # NEW: NA-aware schema
└── huggingface_writer.py   # NEW: NA-aware writer
```

---

## 3. HuggingFace Export Schema

### 3.1 JSON Lines Format

```python
class HuggingFaceItemExport(BaseModel):
    """Single PHQ-8 item in HuggingFace export."""

    score: int | None
    assertion: Literal["present", "denied", "possible", "not_mentioned"]
    confidence: float | None
    evidence: list[str]


class HuggingFaceTotalsExport(BaseModel):
    """Total score section in HuggingFace export."""

    discussed_count: int
    discussed_sum: int
    coverage: float
    prorated_total: float | None
    prorated_total_rounded: int | None
    imputed_total: int
    na_count: int
    is_min_coverage: bool
    is_proration_valid: bool


class HuggingFaceMetadataExport(BaseModel):
    """Scoring metadata in HuggingFace export."""

    prompt_version: str
    juror_models: list[str]
    runs_per_model: int
    arbitration_triggered: bool
    judge_model: str | None


class HuggingFaceDialogueExport(BaseModel):
    """Complete dialogue export record for HuggingFace."""

    model_config = ConfigDict(extra="forbid")

    dialogue_id: str
    condition: Literal["mdd", "control"]
    split: str  # "train", "dev", "test"

    items: dict[str, HuggingFaceItemExport]  # 8 items
    totals: HuggingFaceTotalsExport
    scoring_metadata: HuggingFaceMetadataExport
```

### 3.2 Example Output (JSONL)

```json
{
  "dialogue_id": "active436",
  "condition": "mdd",
  "split": "train",
  "items": {
    "anhedonia": {"score": 2, "assertion": "present", "confidence": 0.85, "evidence": ["I can't enjoy anything anymore"]},
    "depressed_mood": {"score": 3, "assertion": "present", "confidence": 0.92, "evidence": ["I feel hopeless all the time"]},
    "sleep": {"score": 1, "assertion": "present", "confidence": 0.78, "evidence": ["Sometimes I have trouble sleeping"]},
    "fatigue": {"score": null, "assertion": "not_mentioned", "confidence": null, "evidence": []},
    "appetite": {"score": null, "assertion": "not_mentioned", "confidence": null, "evidence": []},
    "guilt": {"score": 0, "assertion": "denied", "confidence": 0.88, "evidence": ["I don't blame myself for anything"]},
    "concentration": {"score": 2, "assertion": "present", "confidence": 0.75, "evidence": ["I can't focus on work"]},
    "psychomotor": {"score": null, "assertion": "not_mentioned", "confidence": null, "evidence": []}
  },
  "totals": {
    "discussed_count": 5,
    "discussed_sum": 8,
    "coverage": 0.625,
    "prorated_total": null,
    "prorated_total_rounded": null,
    "imputed_total": 8,
    "na_count": 3,
    "is_min_coverage": true,
    "is_proration_valid": false
  },
  "scoring_metadata": {
    "prompt_version": "v2.0.0-clinical",
    "juror_models": ["gpt-4o", "claude-sonnet-4", "gemini-2.0-flash"],
    "runs_per_model": 2,
    "arbitration_triggered": true,
    "judge_model": "claude-opus-4"
  }
}
```

---

## 4. TDD Test Cases

### 4.1 Schema Validation

```python
# TEST: Valid full-coverage export
def test_huggingface_export_full_coverage():
    export = HuggingFaceDialogueExport(
        dialogue_id="active001",
        condition="mdd",
        split="train",
        items={
            "anhedonia": HuggingFaceItemExport(score=2, assertion="present", confidence=0.8, evidence=["..."]),
            "depressed_mood": HuggingFaceItemExport(score=3, assertion="present", confidence=0.9, evidence=["..."]),
            "sleep": HuggingFaceItemExport(score=1, assertion="present", confidence=0.7, evidence=["..."]),
            "fatigue": HuggingFaceItemExport(score=2, assertion="present", confidence=0.8, evidence=["..."]),
            "appetite": HuggingFaceItemExport(score=0, assertion="denied", confidence=0.9, evidence=["..."]),
            "guilt": HuggingFaceItemExport(score=1, assertion="present", confidence=0.6, evidence=["..."]),
            "concentration": HuggingFaceItemExport(score=2, assertion="present", confidence=0.8, evidence=["..."]),
            "psychomotor": HuggingFaceItemExport(score=0, assertion="denied", confidence=0.7, evidence=["..."]),
        },
        totals=HuggingFaceTotalsExport(
            discussed_count=8,
            discussed_sum=11,
            coverage=1.0,
            prorated_total=11.0,
            prorated_total_rounded=11,
            imputed_total=11,
            na_count=0,
            is_min_coverage=True,
            is_proration_valid=True,
        ),
        scoring_metadata=HuggingFaceMetadataExport(
            prompt_version="v2.0.0-clinical",
            juror_models=["gpt-4o", "claude-sonnet-4"],
            runs_per_model=2,
            arbitration_triggered=False,
            judge_model=None,
        ),
    )
    assert export.dialogue_id == "active001"
    assert export.totals.coverage == 1.0

# TEST: Valid export with NA items
def test_huggingface_export_with_na():
    export = HuggingFaceDialogueExport(
        dialogue_id="active002",
        condition="control",
        split="dev",
        items={
            "anhedonia": HuggingFaceItemExport(score=0, assertion="denied", confidence=0.9, evidence=["I enjoy things"]),
            "depressed_mood": HuggingFaceItemExport(score=None, assertion="not_mentioned", confidence=None, evidence=[]),
            "sleep": HuggingFaceItemExport(score=None, assertion="not_mentioned", confidence=None, evidence=[]),
            "fatigue": HuggingFaceItemExport(score=1, assertion="possible", confidence=0.5, evidence=["maybe tired"]),
            "appetite": HuggingFaceItemExport(score=0, assertion="denied", confidence=0.8, evidence=["eating fine"]),
            "guilt": HuggingFaceItemExport(score=None, assertion="not_mentioned", confidence=None, evidence=[]),
            "concentration": HuggingFaceItemExport(score=0, assertion="denied", confidence=0.85, evidence=["focus is good"]),
            "psychomotor": HuggingFaceItemExport(score=None, assertion="not_mentioned", confidence=None, evidence=[]),
        },
        totals=HuggingFaceTotalsExport(
            discussed_count=4,
            discussed_sum=1,
            coverage=0.5,
            prorated_total=None,
            prorated_total_rounded=None,
            imputed_total=1,
            na_count=4,
            is_min_coverage=True,
            is_proration_valid=False,
        ),
        scoring_metadata=HuggingFaceMetadataExport(
            prompt_version="v2.0.0-clinical",
            juror_models=["gpt-4o"],
            runs_per_model=2,
            arbitration_triggered=False,
            judge_model=None,
        ),
    )
    assert export.totals.na_count == 4
    assert export.items["depressed_mood"].score is None
    assert export.items["depressed_mood"].assertion == "not_mentioned"

# TEST: Item score/assertion consistency validation
def test_huggingface_item_validation():
    # present requires score 1-3
    with pytest.raises(ValidationError):
        HuggingFaceItemExport(score=0, assertion="present", confidence=0.8, evidence=["..."])

    # denied requires score 0
    with pytest.raises(ValidationError):
        HuggingFaceItemExport(score=2, assertion="denied", confidence=0.8, evidence=["..."])

    # not_mentioned requires score None
    with pytest.raises(ValidationError):
        HuggingFaceItemExport(score=0, assertion="not_mentioned", confidence=None, evidence=[])

    # not_mentioned requires confidence None
    with pytest.raises(ValidationError):
        HuggingFaceItemExport(score=None, assertion="not_mentioned", confidence=0.5, evidence=[])
```

### 4.2 Writer Tests

```python
# TEST: Write single dialogue to JSONL
def test_huggingface_writer_single():
    export = make_sample_export()
    writer = HuggingFaceWriter(output_path)

    writer.write(export)

    with open(output_path) as f:
        line = f.readline()
        data = json.loads(line)
        assert data["dialogue_id"] == export.dialogue_id
        assert data["items"]["anhedonia"]["score"] == export.items["anhedonia"].score

# TEST: Write multiple dialogues
def test_huggingface_writer_batch():
    exports = [make_sample_export(f"dialogue_{i}") for i in range(10)]
    writer = HuggingFaceWriter(output_path)

    for export in exports:
        writer.write(export)

    with open(output_path) as f:
        lines = f.readlines()
        assert len(lines) == 10

# TEST: null values serialize correctly
def test_huggingface_null_serialization():
    export = make_export_with_na()
    writer = HuggingFaceWriter(output_path)
    writer.write(export)

    with open(output_path) as f:
        data = json.loads(f.readline())
        # NA items should have null (not 0, not omitted)
        assert data["items"]["fatigue"]["score"] is None
        assert data["items"]["fatigue"]["confidence"] is None
        assert data["totals"]["prorated_total"] is None
```

### 4.3 Conversion from AggregatedPHQ8

```python
# TEST: Convert AggregatedPHQ8NA to HuggingFace export
def test_convert_aggregated_to_huggingface():
    aggregated = make_aggregated_result()
    export = HuggingFaceDialogueExport.from_aggregated(
        aggregated,
        split="train",
    )
    assert export.dialogue_id == aggregated.file_id
    assert export.condition == aggregated.condition
    assert len(export.items) == 8

# TEST: Conversion preserves NA items
def test_convert_preserves_na():
    aggregated = make_aggregated_with_na()
    export = HuggingFaceDialogueExport.from_aggregated(aggregated, split="dev")

    # NA items should remain None
    for item_name, item_agg in aggregated.items.items():
        if item_agg.consensus_score is None:
            assert export.items[item_name].score is None
            assert export.items[item_name].assertion == "not_mentioned"
```

### 4.4 SPEC-08 Compatibility

```python
# TEST: SPEC-08 export unchanged (int-only)
def test_spec08_export_unchanged():
    # Same aggregated result, different export
    aggregated = make_aggregated_with_na()

    # SPEC-08: NA → 0 (imputed)
    spec08 = ScoredDialogueExport.from_aggregated(aggregated)
    assert isinstance(spec08.phq8_item_4, int)  # fatigue
    assert spec08.phq8_item_4 == 0  # NA imputed as 0

    # HuggingFace: NA → null
    hf = HuggingFaceDialogueExport.from_aggregated(aggregated, split="train")
    assert hf.items["fatigue"].score is None

# TEST: Both exports from same source
def test_dual_export_from_same_source():
    aggregated = make_aggregated_result()

    spec08 = ScoredDialogueExport.from_aggregated(aggregated)
    hf = HuggingFaceDialogueExport.from_aggregated(aggregated, split="train")

    # Both should have same dialogue_id
    assert spec08.dialogue_id == hf.dialogue_id

    # SPEC-08 total = HuggingFace imputed_total
    assert spec08.phq8_total == hf.totals.imputed_total
```

---

## 5. CLI Integration

### 5.1 New Export Command

```bash
# Export to HuggingFace format
vibe-check export --format huggingface --output phq8_labels.jsonl

# Export to SPEC-08 format (default, unchanged)
vibe-check export --format spec08 --output phq8_labels.csv
```

### 5.2 TDD Test Cases

```python
# TEST: CLI exports HuggingFace format
def test_cli_huggingface_export(cli_runner):
    result = cli_runner.invoke(["export", "--format", "huggingface", "--output", "out.jsonl"])
    assert result.exit_code == 0
    assert Path("out.jsonl").exists()

# TEST: CLI default is SPEC-08
def test_cli_default_spec08(cli_runner):
    result = cli_runner.invoke(["export", "--output", "out.csv"])
    assert result.exit_code == 0
    # Should be CSV (SPEC-08), not JSONL
    with open("out.csv") as f:
        header = f.readline()
        assert "phq8_item_1" in header
```

---

## 6. Dataset Card Template

When publishing to HuggingFace, include this dataset card:

```markdown
# SQPsychConv PHQ-8 Labels (NA-Aware)

## Dataset Description
PHQ-8 symptom severity labels for the SQPsychConv synthetic therapy dialogue corpus.

## Source Corpus
- **Name**: SQPsychConv (Qwen 2.5 variant)
- **Dialogues**: 2,090
- **Conditions**: MDD (1,395) / Control (695)

## Labeling Methodology
- **Multi-juror consensus**: 6 LLM jurors (3 models × 2 runs)
- **Bayesian aggregation**: Dirichlet posteriors with convolution
- **Arbitration**: Judge review for contested items
- **NA-aware**: Items not discussed are marked `null`, not `0`

## Schema
See `huggingface_schema.py` for Pydantic definitions.

## Important Notes
- `score=null` means "not discussed in transcript" (NOT "score 0")
- `prorated_total` only computed when `discussed_count >= 7`
- `imputed_total` treats NA as 0 (use with caution)

## Intended Use
- Training depression detection models
- Transfer learning to DAIC-WOZ
- Research on transcript-based symptom inference

## Limitations
- Synthetic dialogues may not reflect real clinical conversations
- Coverage patterns may differ from real corpora
- Proration is approximate; prefer per-item scores
```

---

## 7. Files Affected

| File | Change Type |
|------|-------------|
| `src/vibe_check/export/huggingface_schema.py` | **NEW** |
| `src/vibe_check/export/huggingface_writer.py` | **NEW** |
| `src/vibe_check/cli.py` | **MODERATE** - Add format flag |
| `tests/unit/test_huggingface_export.py` | **NEW** |

---

## 8. Acceptance Criteria

- [ ] All test cases in Section 4 pass
- [ ] SPEC-08 export unchanged
- [ ] HuggingFace export preserves `null` values
- [ ] CLI supports `--format huggingface`
- [ ] Dataset card template included
- [ ] Ruff + mypy pass

---

## 9. Sign-Off

| Role | Status |
|------|--------|
| Author | DRAFT |
| Senior Review | PENDING |
