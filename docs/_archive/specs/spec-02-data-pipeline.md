# SPEC-02: Data Pipeline (Corpus Ingestion & Preprocessing)

**Status**: IMPLEMENTED (2026-01-02)
**Slice Type**: Vertical (End-to-End Data Flow)
**Dependencies**: SPEC-01 (DevEx Foundation)
**Estimated Scope**: ~200 lines of code, ~150 lines of tests

---

## 1. Objective

Build a complete data pipeline that can:
1. Load SQPsychConv dialogues from Arrow/CSV files
2. Parse raw text into structured dialogue objects
3. Validate corpus integrity (no duplicates, proper splits)
4. Extract dialogue views (client_only, client_qa)
5. Produce a deterministic train/dev/test split

### Why This Slice First?

- **Zero LLM dependencies**: Everything is pure data transformation
- **Testable without downloads**: CI uses a tiny `datasets.DatasetDict().save_to_disk()` fixture so tests pass from a clean checkout
- **Optionally verifiable on real data**: If `data/sqpsychconv/qwen-2.5` exists locally, an additional integration test validates the full corpus
- **Foundation for everything**: Can't score dialogues we can't load
- **Proves the data is trustworthy**: The spec warns splits may be broken

### Critical Data Finding (Verified 2026-01-02)

The qwen-2.5 variant has proper train/test splits:

```json
"train": { "num_examples": 1837 },
"test": { "num_examples": 253 }
```

**Note**: The bugged `qwq` variant (now deleted) had 2090/2090 identical splits. We use `qwen-2.5` which has the proper 88/12 split. However, we still apply deterministic `compute_split()` for cross-validation purposes and to maintain a dev set (spec-vibe-check.md Section 3.4).

### Success Criteria

```python
# This should work end-to-end:
from vibe_check.data import load_corpus, validate_corpus, preprocess_dialogue

corpus = load_corpus("data/sqpsychconv/qwen-2.5")
report = validate_corpus(corpus)
assert report.duplicate_count == 0
assert report.split_leakage == 0

dialogue = next(d for d in corpus if d.dialogue.strip())
views = preprocess_dialogue(dialogue)
assert views.client_qa_text  # Non-empty (contexted)
assert len(views.client_qa_text) >= len(views.client_only_text)  # QA has more context
```

---

## 2. Deliverables

### 2.1 New Files

| File | Purpose |
|------|---------|
| `src/vibe_check/schemas/input.py` | `SQPsychConvDialogue` Pydantic model |
| `src/vibe_check/schemas/views.py` | `DialogueViews` Pydantic model |
| `src/vibe_check/data/loader.py` | Load from Arrow/CSV |
| `src/vibe_check/data/validator.py` | Corpus integrity checks |
| `src/vibe_check/data/splitter.py` | Deterministic hash-based splitting |
| `src/vibe_check/preprocessing/extractor.py` | Extract dialogue views |
| `tests/unit/test_schemas_input.py` | Schema tests |
| `tests/unit/test_loader.py` | Loader tests |
| `tests/unit/test_validator.py` | Validator tests |
| `tests/unit/test_splitter.py` | Splitter tests |
| `tests/unit/test_extractor.py` | Extractor tests |
| `tests/integration/test_data_pipeline.py` | End-to-end pipeline test |
| `tests/fixtures/sample_dialogues.py` | Real sample data for tests |
| `tests/fixtures/hf_disk_dataset.py` | Tiny HF `save_to_disk()` dataset builder (CI-safe) |

### 2.2 Updated pyproject.toml

Add dependencies:
```toml
"datasets>=3.0.0",     # HuggingFace datasets for Arrow loading
"pyarrow>=18.0.0",     # Arrow file reading
```

Note: CSV loading is implemented with the standard library `csv` module (no `pandas` required).

---

## 3. Data Schemas

### 3.1 SQPsychConvDialogue (Input)

```python
from typing import Literal
from pydantic import BaseModel, Field

class SQPsychConvDialogue(BaseModel):
    """A single dialogue from the SQPsychConv dataset."""

    file_id: str = Field(description="Unique identifier, e.g., 'active436'")
    condition: Literal["mdd", "control"] = Field(description="MDD or control group")
    client_model: str = Field(description="Model used for client, e.g., 'qwen25'")
    therapist_model: str = Field(description="Model used for therapist")
    dialogue: str = Field(description="Raw dialogue text with speaker labels")

    # Computed during loading (not from raw data)
    computed_split: Literal["train", "dev", "test"] | None = Field(
        default=None,
        description="Deterministic split based on file_id hash"
    )
```

### 3.2 DialogueViews (Preprocessed)

```python
from pydantic import BaseModel, Field

class DialogueViews(BaseModel):
    """Multiple text views extracted from a single dialogue."""

    file_id: str

    # Core views (from SPEC-vibe-check Section 5.3.1)
    dialogue_clean: str = Field(
        description="Normalized speaker labels + whitespace, no semantic changes"
    )
    client_only_text: str = Field(
        description="Client utterances only (WARNING: semantic void risk)"
    )
    client_qa_text: str = Field(
        description="Client utterances + preceding therapist question for context"
    )

    # Metadata for quality checks
    client_utterance_count: int = Field(ge=0)
    therapist_utterance_count: int = Field(ge=0)
    short_answer_count: int = Field(
        ge=0,
        description="Count of very short client responses (<5 words)"
    )

    # Flags for potential issues
    has_empty_client_text: bool = False
    has_unknown_speaker: bool = False
```

### 3.3 CorpusIntegrityReport

```python
from pydantic import BaseModel, Field

class CorpusIntegrityReport(BaseModel):
    """Results of corpus validation checks."""

    total_dialogues: int
    unique_file_ids: int
    duplicate_count: int = Field(ge=0, description="Should be 0")

    # Split integrity
    train_count: int
    dev_count: int
    test_count: int
    split_leakage: int = Field(ge=0, description="Overlapping file_ids across splits, should be 0")

    # Condition distribution
    mdd_count: int
    control_count: int

    # Content warnings (not failures, just flags)
    empty_dialogue_count: int = Field(ge=0)
    unknown_speaker_count: int = Field(ge=0)

    # Hashes for deduplication
    duplicate_content_hashes: list[str] = Field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """Corpus passes all hard requirements."""
        return self.duplicate_count == 0 and self.split_leakage == 0
```

---

## 4. Core Functions

### 4.1 Loader (`data/loader.py`)

```python
def load_corpus(
    path: str | Path,
    source: Literal["arrow", "csv", "auto"] = "auto"
) -> list[SQPsychConvDialogue]:
    """Load SQPsychConv dialogues from disk.

    Args:
        path: Directory containing Arrow files or path to CSV
        source: Format to use (auto-detect by default)

    Returns:
        List of parsed dialogues with computed_split set

    Raises:
        FileNotFoundError: If path doesn't exist
        ValueError: If no valid data found
    """
```

**Implementation Notes**:
- Arrow format: Use `datasets.load_from_disk()` (supports `Dataset` and `DatasetDict`)
- CSV format: Use the standard library `csv` module (with robust quoting)
- Auto-detect: Prefer HuggingFace `save_to_disk()` layouts (`dataset_dict.json` / `dataset_info.json`), then `.arrow`, then `.csv`
- If multiple HF splits are present: concatenate all splits, then **dedupe by `file_id`** (conflicting content for the same `file_id` is a hard error)
- Always compute deterministic split after loading (ignore HF train/test labels)
- Sort the returned list by `file_id` for deterministic tests

### 4.2 Splitter (`data/splitter.py`)

```python
import hashlib

def compute_split(file_id: str) -> Literal["train", "dev", "test"]:
    """Deterministic split based on file_id hash.

    Uses SHA256 hash % 10:
    - 0-7 (80%): train
    - 8 (10%): dev
    - 9 (10%): test

    This is stable regardless of HuggingFace's broken splits.
    """
    hash_val = int(hashlib.sha256(file_id.encode()).hexdigest(), 16)
    bucket = hash_val % 10
    if bucket < 8:
        return "train"
    elif bucket == 8:
        return "dev"
    else:
        return "test"
```

**Critical**: This replaces the untrusted HuggingFace train/test splits that may have 100% overlap.

### 4.3 Validator (`data/validator.py`)

```python
def validate_corpus(dialogues: list[SQPsychConvDialogue]) -> CorpusIntegrityReport:
    """Run all corpus integrity checks.

    Checks:
    1. file_id uniqueness (0 duplicates allowed)
    2. Content deduplication via SHA256 of `dialogue_clean` (avoid false negatives from whitespace)
    3. Split leakage check (train ∩ dev ∩ test = ∅)
    4. Empty dialogue detection
    5. Unknown speaker detection

    Returns:
        Report with counts and warnings (no transcript text stored)
    """
```

### 4.4 Extractor (`preprocessing/extractor.py`)

```python
def preprocess_dialogue(dialogue: SQPsychConvDialogue) -> DialogueViews:
    """Extract all text views from a dialogue.

    Views:
    1. dialogue_clean: Normalize "Therapist:"/"Client:" labels
    2. client_only_text: Just client utterances
    3. client_qa_text: Client + preceding therapist question

    The key transformation for client_qa_text:
    - For each contiguous block of client utterances
    - Include the single most recent therapist line once
    - Do NOT repeat therapist line before every client line

    Deterministic hygiene (SQPsychConv-specific):
    - Drop obvious generation artifacts even when they are speaker-labeled
      (e.g., "Therapist:, no markdown..." or "Client: ... under 64 words ...").
    - Trim/strip common meta-instruction suffixes and long bracketed guideline blobs.
    - Drop absurdly long utterances (>4000 chars or >200 words) as likely artifacts.
    - Any discarded/unknown-speaker content sets `has_unknown_speaker=True` so downstream
      validation can quantify how often hygiene was needed (without storing text).
    """

def parse_utterances(dialogue_text: str) -> list[tuple[str, str]]:
    """Parse dialogue into (speaker, text) tuples.

    Handles:
    - "Therapist: ..." and "Client: ..." prefixes
    - Multiline utterances
    - Edge cases (empty lines, missing colons)

    Returns:
        List of (speaker, utterance_text) where speaker is normalized
        to "therapist" or "client" (lowercase)
    """
```

---

## 5. Test Specifications

### 5.1 Unit Tests

**test_schemas_input.py**:
```python
def test_dialogue_valid():
    """Valid dialogue parses correctly."""
    d = SQPsychConvDialogue(
        file_id="test123",
        condition="mdd",
        client_model="qwen25",
        therapist_model="qwen25",
        dialogue="Therapist: Hello\nClient: Hi"
    )
    assert d.file_id == "test123"
    assert d.computed_split is None  # Not set until loading

def test_dialogue_invalid_condition():
    """Invalid condition raises ValidationError."""
    with pytest.raises(ValidationError):
        SQPsychConvDialogue(
            file_id="test",
            condition="unknown",  # Must be mdd or control
            client_model="qwen25",
            therapist_model="qwen25",
            dialogue="Therapist: Hello\nClient: Hi",
        )
```

**test_splitter.py**:
```python
def test_split_deterministic():
    """Same file_id always produces same split."""
    assert compute_split("active436") == compute_split("active436")

def test_split_distribution():
    """Splits roughly follow 80/10/10 distribution."""
    splits = [compute_split(f"file_{i}") for i in range(1000)]
    train_pct = splits.count("train") / 1000
    assert 0.75 < train_pct < 0.85  # ~80% with some variance

def test_known_file_ids():
    """Verify splits for known file_ids from dataset."""
    # These are actual file_ids from the data
    assert compute_split("active436") in ["train", "dev", "test"]
    assert compute_split("active422") in ["train", "dev", "test"]
```

**test_extractor.py**:
```python
def test_parse_utterances_basic():
    """Basic dialogue parses correctly."""
    text = "Therapist: Hello\nClient: Hi there"
    result = parse_utterances(text)
    assert result == [("therapist", "Hello"), ("client", "Hi there")]

def test_parse_utterances_multiline():
    """Multiline utterances handled."""
    text = "Therapist: How are you?\nClient: I'm okay.\nNot great, but okay."
    result = parse_utterances(text)
    assert len(result) == 2
    assert "Not great" in result[1][1]

def test_client_qa_context():
    """client_qa_text includes therapist question context."""
    dialogue = SQPsychConvDialogue(
        file_id="test",
        condition="mdd",
        client_model="test",
        therapist_model="test",
        dialogue="Therapist: How is your sleep?\nClient: Terrible."
    )
    views = preprocess_dialogue(dialogue)

    # client_only loses context
    assert views.client_only_text == "Terrible."

    # client_qa preserves it
    assert "sleep" in views.client_qa_text.lower()
    assert "Terrible" in views.client_qa_text

def test_semantic_void_detection():
    """Detect when client_only would be semantically empty."""
    dialogue = SQPsychConvDialogue(
        file_id="test",
        condition="mdd",
        client_model="test",
        therapist_model="test",
        dialogue="Therapist: Rate 1-10?\nClient: 8."
    )
    views = preprocess_dialogue(dialogue)

    # "8." alone is meaningless
    assert views.short_answer_count >= 1
```

### 5.2 Integration Test

**test_data_pipeline.py**:
```python
@pytest.mark.integration
def test_full_pipeline_with_real_data():
    """Load real SQPsychConv data and validate end-to-end."""
    # Load from actual data directory
    corpus = load_corpus("data/sqpsychconv/qwen-2.5")

    # Should have data
    assert len(corpus) > 0

    # Validate integrity
    report = validate_corpus(corpus)
    assert report.duplicate_count == 0, "No duplicate file_ids"
    assert report.split_leakage == 0, "No split leakage"

    # All have computed splits
    assert all(d.computed_split is not None for d in corpus)

    # Preprocess one dialogue
    views = preprocess_dialogue(corpus[0])
    assert views.client_only_text
    assert views.client_qa_text
    assert views.client_utterance_count > 0

@pytest.mark.integration
def test_condition_distribution():
    """MDD and control conditions are both present."""
    corpus = load_corpus("data/sqpsychconv/qwen-2.5")
    report = validate_corpus(corpus)

    assert report.mdd_count > 0, "Should have MDD dialogues"
    assert report.control_count > 0, "Should have control dialogues"
```

---

## 6. Edge Cases to Handle

### 6.1 Parsing Edge Cases

| Input | Expected Behavior |
|-------|-------------------|
| Empty dialogue | Flag `has_empty_client_text`, don't crash |
| No "Client:" prefix | Flag `has_unknown_speaker`, extract empty client views |
| Unlabeled preamble/meta text | Exclude from views, flag `has_unknown_speaker` |
| Speaker-labeled meta artifacts | Drop from views, flag `has_unknown_speaker` |
| Therapist-only dialogue | `client_only_text` is empty, flagged |
| Multiple colons in text | Only split on first colon after speaker |
| Unicode/emoji in text | Preserve as-is |
| Absurdly long utterance | Drop as artifact (>4000 chars or >200 words), flag `has_unknown_speaker` |

### 6.2 Data Quality Edge Cases

| Issue | Detection | Handling |
|-------|-----------|----------|
| Duplicate file_ids | `validate_corpus` | Fail with report |
| Duplicate content (diff file_id) | SHA256 hash check | Warn in report |
| Empty string dialogue | Length check | Flag, don't process |
| Missing required fields | Pydantic validation | Raise ValidationError |
| Conflicting duplicate file_id content | Content hash mismatch | Hard fail (data corruption) |

---

## 7. Definition of Done

- [x] All schemas pass type checking
- [x] `load_corpus()` loads HF `save_to_disk()` data from `data/sqpsychconv/qwen-2.5`
- [x] `validate_corpus()` returns valid report for real data
- [x] `compute_split()` is deterministic and follows 80/10/10
- [x] `preprocess_dialogue()` produces all three views
- [x] Unit + integration tests pass with real dataset
- [x] No LLM calls or mocks in any test
- [x] `make ci` passes

---

## 8. Non-Goals (Deferred)

- `client_contextualized` view (requires LLM call, deferred to later spec)
- Near-duplicate detection via MinHash/LSH (enhancement, not MVP)
- CJK character detection (mentioned in master spec, low priority)
- Parallel loading (premature optimization)

---

## 9. Testing Philosophy

**No Mocks**: Every test uses either:
1. Real data from `data/sqpsychconv/`
2. Inline synthetic data that's explicitly constructed

**Why this works**: The data pipeline is pure transformation. Given input bytes, produce structured output. No external dependencies to mock.

**Fixture Strategy**: Create `tests/fixtures/sample_dialogues.py` with:
- 3-5 real dialogues copied from the dataset (for regression tests)
- Edge case dialogues (empty, malformed, unusual)

---

## 10. Implementation Order

1. Write schemas first (`input.py`, `views.py`) - contracts matter
2. Write `splitter.py` - simplest, no I/O
3. Write `extractor.py` - text parsing logic
4. Write `loader.py` - I/O layer
5. Write `validator.py` - ties it together
6. Write unit tests alongside each module
7. Write integration test last (needs all pieces)
