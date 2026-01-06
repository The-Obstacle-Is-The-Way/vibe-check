# SPEC-13: NA-Aware Schema Changes

> **Status**: DRAFT - Pending Senior Review
> **Depends On**: clinical-alignment-review.md (APPROVED)
> **Blocks**: SPEC-14 (Prompts), SPEC-15 (Aggregation), SPEC-16 (Export)

---

## 1. Overview

This spec defines TDD requirements for updating `PHQ8ItemScore` to support NA-aware scoring with clinical assertion semantics.

**Core Change**: A juror can now indicate "no evidence" (`score=None`) instead of being forced to pick 0-3.

---

## 2. Schema: `PHQ8ItemScore`

### 2.1 Current Schema (to be replaced)

```python
class PHQ8ItemScore(BaseModel):
    score: Literal[0, 1, 2, 3]  # REQUIRED
    confidence: float           # REQUIRED
    evidence: list[str]
    insufficient_evidence: bool
```

### 2.2 New Schema

```python
class PHQ8ItemScore(BaseModel):
    """Single PHQ-8 item score with clinical assertion semantics."""

    model_config = ConfigDict(extra="forbid")

    score: Literal[0, 1, 2, 3] | None = Field(
        description="0-3 severity; None if not_mentioned"
    )
    assertion: Literal["present", "denied", "possible", "not_mentioned"] = Field(
        description="Clinical-NLP-inspired assertion label"
    )
    confidence: float | None = Field(
        default=None, ge=0.0, le=1.0,
        description="Model confidence; None when score is None"
    )
    evidence: list[str] = Field(
        default_factory=list, max_length=3,
        description="Supporting quotes (empty for not_mentioned)"
    )
```

**Removed**: `insufficient_evidence` (superseded by `assertion`)

---

## 3. Assertion Semantics

| Assertion | Score | Confidence | Evidence | When to Use |
|-----------|-------|------------|----------|-------------|
| `present` | 1-3 | Required (0.0-1.0) | Required (1-3 quotes) | Symptom clearly described |
| `denied` | 0 | Required (0.0-1.0) | Required (denial quote) | Patient explicitly denies symptom |
| `possible` | 1 | Required (0.0-1.0) | Required (hedged quote) | Uncertain/hedged mention |
| `not_mentioned` | None | None | Empty list | No evidence for CLIENT+timeframe |

---

## 4. TDD Test Cases

### 4.1 Valid Constructions

```python
# TEST: present assertion with score 2
def test_present_assertion_valid():
    item = PHQ8ItemScore(
        score=2,
        assertion="present",
        confidence=0.85,
        evidence=["I've been really tired lately"]
    )
    assert item.score == 2
    assert item.assertion == "present"
    assert item.confidence == 0.85

# TEST: denied assertion with score 0
def test_denied_assertion_valid():
    item = PHQ8ItemScore(
        score=0,
        assertion="denied",
        confidence=0.92,
        evidence=["My sleep has been fine"]
    )
    assert item.score == 0
    assert item.assertion == "denied"

# TEST: possible assertion defaults to score 1
def test_possible_assertion_valid():
    item = PHQ8ItemScore(
        score=1,
        assertion="possible",
        confidence=0.60,
        evidence=["Maybe I've been a bit tired"]
    )
    assert item.score == 1
    assert item.assertion == "possible"

# TEST: not_mentioned assertion with None score
def test_not_mentioned_assertion_valid():
    item = PHQ8ItemScore(
        score=None,
        assertion="not_mentioned",
        confidence=None,
        evidence=[]
    )
    assert item.score is None
    assert item.assertion == "not_mentioned"
    assert item.confidence is None
    assert item.evidence == []
```

### 4.2 Invalid Constructions (Must Raise ValidationError)

```python
# TEST: present requires score 1-3
def test_present_requires_nonzero_score():
    with pytest.raises(ValidationError):
        PHQ8ItemScore(
            score=0,  # INVALID: present must be 1-3
            assertion="present",
            confidence=0.80,
            evidence=["feeling down"]
        )

# TEST: denied requires score 0
def test_denied_requires_zero_score():
    with pytest.raises(ValidationError):
        PHQ8ItemScore(
            score=2,  # INVALID: denied must be 0
            assertion="denied",
            confidence=0.90,
            evidence=["I'm sleeping fine"]
        )

# TEST: not_mentioned requires score None
def test_not_mentioned_requires_none_score():
    with pytest.raises(ValidationError):
        PHQ8ItemScore(
            score=0,  # INVALID: not_mentioned must be None
            assertion="not_mentioned",
            confidence=None,
            evidence=[]
        )

# TEST: not_mentioned requires confidence None
def test_not_mentioned_requires_none_confidence():
    with pytest.raises(ValidationError):
        PHQ8ItemScore(
            score=None,
            assertion="not_mentioned",
            confidence=0.50,  # INVALID: must be None
            evidence=[]
        )

# TEST: not_mentioned requires empty evidence
def test_not_mentioned_requires_empty_evidence():
    with pytest.raises(ValidationError):
        PHQ8ItemScore(
            score=None,
            assertion="not_mentioned",
            confidence=None,
            evidence=["some quote"]  # INVALID: must be empty
        )

# TEST: present/denied/possible require non-empty evidence
def test_present_requires_evidence():
    with pytest.raises(ValidationError):
        PHQ8ItemScore(
            score=2,
            assertion="present",
            confidence=0.80,
            evidence=[]  # INVALID: must have evidence
        )

# TEST: present/denied/possible require confidence
def test_denied_requires_confidence():
    with pytest.raises(ValidationError):
        PHQ8ItemScore(
            score=0,
            assertion="denied",
            confidence=None,  # INVALID: must have confidence
            evidence=["I'm sleeping well"]
        )

# TEST: possible can only be score 1 (not 0, 2, or 3)
def test_possible_must_be_score_one():
    with pytest.raises(ValidationError):
        PHQ8ItemScore(
            score=2,  # INVALID: possible must be 1
            assertion="possible",
            confidence=0.55,
            evidence=["maybe a little tired"]
        )
```

### 4.3 Edge Cases

```python
# TEST: maximum evidence snippets (3)
def test_max_evidence_snippets():
    item = PHQ8ItemScore(
        score=3,
        assertion="present",
        confidence=0.95,
        evidence=["quote 1", "quote 2", "quote 3"]
    )
    assert len(item.evidence) == 3

# TEST: evidence snippet length validation (inherited from current)
def test_evidence_snippet_max_length():
    long_snippet = "x" * 501  # Exceeds MAX_EVIDENCE_SNIPPET_CHARS
    with pytest.raises(ValidationError):
        PHQ8ItemScore(
            score=1,
            assertion="present",
            confidence=0.70,
            evidence=[long_snippet]
        )

# TEST: confidence boundary values
def test_confidence_boundaries():
    # Valid: 0.0
    item = PHQ8ItemScore(score=0, assertion="denied", confidence=0.0, evidence=["no issues"])
    assert item.confidence == 0.0

    # Valid: 1.0
    item = PHQ8ItemScore(score=3, assertion="present", confidence=1.0, evidence=["severe"])
    assert item.confidence == 1.0

    # Invalid: > 1.0
    with pytest.raises(ValidationError):
        PHQ8ItemScore(score=1, assertion="present", confidence=1.1, evidence=["quote"])

    # Invalid: < 0.0
    with pytest.raises(ValidationError):
        PHQ8ItemScore(score=1, assertion="present", confidence=-0.1, evidence=["quote"])
```

---

## 5. Schema: `PHQ8Assessment` Updates

### 5.1 Changes Required

- `total_score` field must be computed from non-None scores only
- Add `discussed_count` field
- Add model validator for assertion/score consistency across items

### 5.2 TDD Test Cases

```python
# TEST: Assessment with all items discussed
def test_assessment_all_discussed():
    assessment = PHQ8Assessment(
        anhedonia=PHQ8ItemScore(score=2, assertion="present", confidence=0.8, evidence=["..."]),
        depressed_mood=PHQ8ItemScore(score=3, assertion="present", confidence=0.9, evidence=["..."]),
        sleep=PHQ8ItemScore(score=1, assertion="present", confidence=0.7, evidence=["..."]),
        fatigue=PHQ8ItemScore(score=2, assertion="present", confidence=0.8, evidence=["..."]),
        appetite=PHQ8ItemScore(score=0, assertion="denied", confidence=0.9, evidence=["..."]),
        guilt=PHQ8ItemScore(score=1, assertion="present", confidence=0.6, evidence=["..."]),
        concentration=PHQ8ItemScore(score=2, assertion="present", confidence=0.8, evidence=["..."]),
        psychomotor=PHQ8ItemScore(score=0, assertion="denied", confidence=0.7, evidence=["..."]),
    )
    assert assessment.total_score == 11
    assert assessment.discussed_count == 8

# TEST: Assessment with NA items
def test_assessment_with_na_items():
    assessment = PHQ8Assessment(
        anhedonia=PHQ8ItemScore(score=2, assertion="present", confidence=0.8, evidence=["..."]),
        depressed_mood=PHQ8ItemScore(score=3, assertion="present", confidence=0.9, evidence=["..."]),
        sleep=PHQ8ItemScore(score=None, assertion="not_mentioned", confidence=None, evidence=[]),
        fatigue=PHQ8ItemScore(score=2, assertion="present", confidence=0.8, evidence=["..."]),
        appetite=PHQ8ItemScore(score=None, assertion="not_mentioned", confidence=None, evidence=[]),
        guilt=PHQ8ItemScore(score=None, assertion="not_mentioned", confidence=None, evidence=[]),
        concentration=PHQ8ItemScore(score=1, assertion="possible", confidence=0.5, evidence=["..."]),
        psychomotor=PHQ8ItemScore(score=None, assertion="not_mentioned", confidence=None, evidence=[]),
    )
    # total_score = 2 + 3 + 2 + 1 = 8 (NA items not counted)
    assert assessment.total_score == 8
    assert assessment.discussed_count == 4
```

---

## 6. Schema: `PHQ8TotalScore` (NEW)

### 6.1 Definition

```python
class PHQ8TotalScore(BaseModel):
    """Total score with full provenance."""

    model_config = ConfigDict(extra="forbid")

    # Raw discussed items
    discussed_count: int = Field(ge=0, le=8)
    discussed_sum: int = Field(ge=0, le=24)
    coverage: float = Field(ge=0.0, le=1.0)  # discussed_count / 8

    # Prorated (for PHQ-8 comparability)
    prorated_total: float | None = Field(default=None, ge=0.0, le=24.0)
    prorated_total_rounded: int | None = Field(default=None, ge=0, le=24)

    # Conservative imputation (for ML)
    imputed_total: int = Field(ge=0, le=24)  # NA treated as 0
    na_count: int = Field(ge=0, le=8)

    # Validity flags
    is_min_coverage: bool  # discussed_count >= 4
    is_proration_valid: bool  # discussed_count >= 7
```

### 6.2 TDD Test Cases

```python
# TEST: Full coverage (8/8 items discussed)
def test_total_score_full_coverage():
    total = PHQ8TotalScore(
        discussed_count=8,
        discussed_sum=12,
        coverage=1.0,
        prorated_total=12.0,
        prorated_total_rounded=12,
        imputed_total=12,
        na_count=0,
        is_min_coverage=True,
        is_proration_valid=True,
    )
    assert total.coverage == 1.0
    assert total.is_proration_valid is True

# TEST: High coverage (7/8 items) - proration valid
def test_total_score_high_coverage():
    # 7 items discussed, sum=14, one NA
    # prorated = (14/7) * 8 = 16.0
    total = PHQ8TotalScore(
        discussed_count=7,
        discussed_sum=14,
        coverage=0.875,
        prorated_total=16.0,
        prorated_total_rounded=16,
        imputed_total=14,  # NA treated as 0
        na_count=1,
        is_min_coverage=True,
        is_proration_valid=True,
    )
    assert total.is_proration_valid is True

# TEST: Low coverage (4/8 items) - proration invalid
def test_total_score_low_coverage():
    # 4 items discussed, sum=8, four NA
    # proration NOT valid (< 7 items)
    total = PHQ8TotalScore(
        discussed_count=4,
        discussed_sum=8,
        coverage=0.5,
        prorated_total=None,  # Cannot prorate
        prorated_total_rounded=None,
        imputed_total=8,
        na_count=4,
        is_min_coverage=True,  # 4 >= 4
        is_proration_valid=False,  # 4 < 7
    )
    assert total.is_min_coverage is True
    assert total.is_proration_valid is False

# TEST: Below minimum coverage (3/8 items)
def test_total_score_below_min_coverage():
    total = PHQ8TotalScore(
        discussed_count=3,
        discussed_sum=6,
        coverage=0.375,
        prorated_total=None,
        prorated_total_rounded=None,
        imputed_total=6,
        na_count=5,
        is_min_coverage=False,  # 3 < 4
        is_proration_valid=False,
    )
    assert total.is_min_coverage is False

# TEST: Proration rounding (fractional case)
def test_total_score_proration_rounding():
    # 7 items, sum=15 → prorated = (15/7)*8 = 17.14... → rounds to 17
    total = PHQ8TotalScore(
        discussed_count=7,
        discussed_sum=15,
        coverage=0.875,
        prorated_total=17.142857142857142,
        prorated_total_rounded=17,  # Round to nearest
        imputed_total=15,
        na_count=1,
        is_min_coverage=True,
        is_proration_valid=True,
    )
    assert total.prorated_total_rounded == 17
```

---

## 7. Migration / Backward Compatibility

### 7.1 Rules

1. **No changes to SPEC-08 export** - existing `ScoredDialogueExport` remains int-only
2. **Internal schemas change** - `PHQ8ItemScore`, `PHQ8Assessment`, `PHQ8Report`
3. **New total fields** - `PHQ8TotalScore` added to `AggregatedPHQ8`
4. **Test data migration** - existing test fixtures must be updated

### 7.2 Compatibility Test Cases

```python
# TEST: SPEC-08 export still produces int-only scores
def test_spec08_export_int_only():
    # Even with NA-aware internal schema, SPEC-08 export imputes NA as 0
    export = ScoredDialogueExport.from_aggregated(aggregated_with_na)
    assert isinstance(export.phq8_item_1, int)
    assert export.phq8_item_1 >= 0  # NA → 0
```

---

## 8. Files Affected

| File | Change Type |
|------|-------------|
| `src/vibe_check/schemas/scoring.py` | **MAJOR** - Schema rewrite |
| `tests/unit/test_schemas_scoring.py` | **MAJOR** - New test cases |
| `tests/conftest.py` | **MODERATE** - Update fixtures |

---

## 9. Acceptance Criteria

- [ ] All test cases in Section 4 pass
- [ ] All test cases in Section 5 pass
- [ ] All test cases in Section 6 pass
- [ ] Ruff + mypy pass with `--strict`
- [ ] No changes to SPEC-08 export contract
- [ ] pytest coverage >= 90% for `schemas/scoring.py`

---

## 10. Sign-Off

| Role | Status |
|------|--------|
| Author | DRAFT |
| Senior Review | PENDING |
