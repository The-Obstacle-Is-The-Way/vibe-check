# SPEC-13: NA-Aware Schema Changes

> **Status**: IMPLEMENTED (Phase 1 complete)
> **Depends On**: clinical-alignment-review.md §12.1–12.2 (APPROVED)
> **Blocks**: SPEC-14, SPEC-15, SPEC-16, SPEC-17

---

## 1. Overview

This spec defines TDD requirements for updating `PHQ8ItemScore` to support NA-aware scoring with clinical assertion semantics, exactly as specified in SSOT §12.1.

**Core Change**: Add `discussed: bool` + `assertion` field; allow `score: int | None`.

---

## 2. Schema: `PHQ8ItemScore` (REVISED)

### 2.1 Current Schema (to be replaced)

```python
# File: src/vibe_check/schemas/scoring.py (current)
class PHQ8ItemScore(BaseModel):
    score: Literal[0, 1, 2, 3]       # REQUIRED
    confidence: float                 # REQUIRED 0.0-1.0
    evidence: list[str]              # max 3
    insufficient_evidence: bool       # TO BE REMOVED
```

### 2.2 New Schema (per SSOT §12.1)

```python
# File: src/vibe_check/schemas/scoring.py (new)
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from vibe_check.constants import MAX_EVIDENCE_SNIPPET_CHARS, MAX_EVIDENCE_SNIPPET_WORDS

Assertion = Literal["present", "denied", "possible", "not_mentioned"]


class PHQ8ItemScore(BaseModel):
    """Single PHQ-8 item score with clinical assertion semantics (SSOT §12.1)."""

    model_config = ConfigDict(extra="forbid")

    # NEW: Was this symptom domain mentioned for CLIENT+timeframe?
    discussed: bool = Field(
        description="True if there is evidence about the CLIENT's recent status for this item"
    )

    score: Literal[0, 1, 2, 3] | None = Field(
        description="0-3 severity; None if not_mentioned"
    )

    assertion: Assertion = Field(
        description="Clinical-NLP-inspired assertion label (extended with not_mentioned)"
    )

    confidence: float | None = Field(
        default=None, ge=0.0, le=1.0,
        description="Model confidence; None when score is None"
    )

    evidence: list[str] = Field(
        default_factory=list, max_length=3,
        description="Up to 3 supporting quotes (empty for not_mentioned)"
    )

    # REMOVED: insufficient_evidence (superseded by assertion)

    @field_validator("evidence")
    @classmethod
    def _validate_evidence_snippets(cls, value: list[str]) -> list[str]:
        for snippet in value:
            cleaned = snippet.strip()
            if not cleaned:
                raise ValueError("evidence snippets must be non-empty after stripping whitespace")
            if len(cleaned) > MAX_EVIDENCE_SNIPPET_CHARS:
                raise ValueError(f"evidence snippet exceeds {MAX_EVIDENCE_SNIPPET_CHARS} chars")
            if len(cleaned.split()) > MAX_EVIDENCE_SNIPPET_WORDS:
                raise ValueError(f"evidence snippet exceeds {MAX_EVIDENCE_SNIPPET_WORDS} words")
        return value

    @model_validator(mode="after")
    def _validate_assertion_consistency(self) -> "PHQ8ItemScore":
        """Enforce SSOT §12.1 assertion semantics."""
        if self.assertion == "not_mentioned":
            if self.discussed is not False:
                raise ValueError("not_mentioned requires discussed=False")
            if self.score is not None:
                raise ValueError("not_mentioned requires score=None")
            if self.confidence is not None:
                raise ValueError("not_mentioned requires confidence=None")
            if self.evidence:
                raise ValueError("not_mentioned requires evidence=[]")
        elif self.assertion == "denied":
            if self.discussed is not True:
                raise ValueError("denied requires discussed=True")
            if self.score != 0:
                raise ValueError("denied requires score=0")
            if self.confidence is None:
                raise ValueError("denied requires confidence (not None)")
            if not self.evidence:
                raise ValueError("denied requires at least one evidence snippet")
        elif self.assertion == "possible":
            if self.discussed is not True:
                raise ValueError("possible requires discussed=True")
            if self.score != 1:
                raise ValueError("possible requires score=1 (SSOT Q4 answer)")
            if self.confidence is None:
                raise ValueError("possible requires confidence (not None)")
            if not self.evidence:
                raise ValueError("possible requires at least one evidence snippet")
        elif self.assertion == "present":
            if self.discussed is not True:
                raise ValueError("present requires discussed=True")
            if self.score not in (1, 2, 3):
                raise ValueError("present requires score in {1, 2, 3}")
            if self.confidence is None:
                raise ValueError("present requires confidence (not None)")
            if not self.evidence:
                raise ValueError("present requires at least one evidence snippet")
        return self
```

---

## 3. Assertion Semantics Table (SSOT §12.1)

| Assertion | discussed | score | confidence | evidence | When to Use |
|-----------|-----------|-------|------------|----------|-------------|
| `present` | `True` | 1-3 | Required (0.0-1.0) | Required (≥1) | Symptom clearly described |
| `denied` | `True` | 0 | Required (0.0-1.0) | Required (≥1) | Patient explicitly denies |
| `possible` | `True` | 1 | Required (0.0-1.0) | Required (≥1) | Hedged/uncertain mention |
| `not_mentioned` | `False` | None | None | Empty `[]` | No evidence for CLIENT+timeframe |

---

## 4. TDD Test Cases: `PHQ8ItemScore`

### 4.1 Valid Constructions

```python
# File: tests/unit/test_schemas_scoring.py

import pytest
from pydantic import ValidationError
from vibe_check.schemas.scoring import PHQ8ItemScore


class TestPHQ8ItemScoreValid:
    """Valid construction tests."""

    def test_present_score_2(self):
        item = PHQ8ItemScore(
            discussed=True,
            score=2,
            assertion="present",
            confidence=0.85,
            evidence=["I've been really tired lately"]
        )
        assert item.discussed is True
        assert item.score == 2
        assert item.assertion == "present"
        assert item.confidence == 0.85

    def test_present_score_1(self):
        item = PHQ8ItemScore(
            discussed=True,
            score=1,
            assertion="present",
            confidence=0.70,
            evidence=["Sometimes I feel down"]
        )
        assert item.score == 1

    def test_present_score_3(self):
        item = PHQ8ItemScore(
            discussed=True,
            score=3,
            assertion="present",
            confidence=0.95,
            evidence=["Every single day I can't sleep"]
        )
        assert item.score == 3

    def test_denied(self):
        item = PHQ8ItemScore(
            discussed=True,
            score=0,
            assertion="denied",
            confidence=0.92,
            evidence=["My sleep has been fine"]
        )
        assert item.score == 0
        assert item.assertion == "denied"

    def test_possible(self):
        item = PHQ8ItemScore(
            discussed=True,
            score=1,
            assertion="possible",
            confidence=0.55,
            evidence=["Maybe I've been a bit tired"]
        )
        assert item.score == 1
        assert item.assertion == "possible"

    def test_not_mentioned(self):
        item = PHQ8ItemScore(
            discussed=False,
            score=None,
            assertion="not_mentioned",
            confidence=None,
            evidence=[]
        )
        assert item.discussed is False
        assert item.score is None
        assert item.assertion == "not_mentioned"
        assert item.confidence is None
        assert item.evidence == []

    def test_confidence_boundary_zero(self):
        item = PHQ8ItemScore(
            discussed=True, score=0, assertion="denied",
            confidence=0.0, evidence=["no issues"]
        )
        assert item.confidence == 0.0

    def test_confidence_boundary_one(self):
        item = PHQ8ItemScore(
            discussed=True, score=3, assertion="present",
            confidence=1.0, evidence=["severe symptoms"]
        )
        assert item.confidence == 1.0

    def test_max_evidence_snippets(self):
        item = PHQ8ItemScore(
            discussed=True, score=2, assertion="present", confidence=0.8,
            evidence=["quote 1", "quote 2", "quote 3"]
        )
        assert len(item.evidence) == 3
```

### 4.2 Invalid Constructions (ValidationError)

```python
class TestPHQ8ItemScoreInvalid:
    """Invalid construction tests - must raise ValidationError."""

    # --- Assertion/score consistency ---

    def test_present_requires_score_1_2_3_not_0(self):
        with pytest.raises(ValidationError, match="present requires score in"):
            PHQ8ItemScore(
                discussed=True, score=0, assertion="present",
                confidence=0.80, evidence=["feeling down"]
            )

    def test_denied_requires_score_0(self):
        with pytest.raises(ValidationError, match="denied requires score=0"):
            PHQ8ItemScore(
                discussed=True, score=2, assertion="denied",
                confidence=0.90, evidence=["I'm sleeping fine"]
            )

    def test_possible_requires_score_1(self):
        with pytest.raises(ValidationError, match="possible requires score=1"):
            PHQ8ItemScore(
                discussed=True, score=2, assertion="possible",
                confidence=0.55, evidence=["maybe tired"]
            )

    def test_possible_requires_score_1_not_0(self):
        with pytest.raises(ValidationError, match="possible requires score=1"):
            PHQ8ItemScore(
                discussed=True, score=0, assertion="possible",
                confidence=0.55, evidence=["maybe not"]
            )

    def test_not_mentioned_requires_score_none(self):
        with pytest.raises(ValidationError, match="not_mentioned requires score=None"):
            PHQ8ItemScore(
                discussed=False, score=0, assertion="not_mentioned",
                confidence=None, evidence=[]
            )

    # --- Assertion/discussed consistency ---

    def test_not_mentioned_requires_discussed_false(self):
        with pytest.raises(ValidationError, match="not_mentioned requires discussed=False"):
            PHQ8ItemScore(
                discussed=True, score=None, assertion="not_mentioned",
                confidence=None, evidence=[]
            )

    def test_present_requires_discussed_true(self):
        with pytest.raises(ValidationError, match="present requires discussed=True"):
            PHQ8ItemScore(
                discussed=False, score=2, assertion="present",
                confidence=0.80, evidence=["feeling down"]
            )

    def test_denied_requires_discussed_true(self):
        with pytest.raises(ValidationError, match="denied requires discussed=True"):
            PHQ8ItemScore(
                discussed=False, score=0, assertion="denied",
                confidence=0.90, evidence=["I'm fine"]
            )

    # --- Assertion/confidence consistency ---

    def test_not_mentioned_requires_confidence_none(self):
        with pytest.raises(ValidationError, match="not_mentioned requires confidence=None"):
            PHQ8ItemScore(
                discussed=False, score=None, assertion="not_mentioned",
                confidence=0.50, evidence=[]
            )

    def test_present_requires_confidence(self):
        with pytest.raises(ValidationError, match="present requires confidence"):
            PHQ8ItemScore(
                discussed=True, score=2, assertion="present",
                confidence=None, evidence=["feeling down"]
            )

    def test_denied_requires_confidence(self):
        with pytest.raises(ValidationError, match="denied requires confidence"):
            PHQ8ItemScore(
                discussed=True, score=0, assertion="denied",
                confidence=None, evidence=["I'm fine"]
            )

    # --- Assertion/evidence consistency ---

    def test_not_mentioned_requires_empty_evidence(self):
        with pytest.raises(ValidationError, match="not_mentioned requires evidence="):
            PHQ8ItemScore(
                discussed=False, score=None, assertion="not_mentioned",
                confidence=None, evidence=["some quote"]
            )

    def test_present_requires_evidence(self):
        with pytest.raises(ValidationError, match="present requires at least one evidence"):
            PHQ8ItemScore(
                discussed=True, score=2, assertion="present",
                confidence=0.80, evidence=[]
            )

    def test_denied_requires_evidence(self):
        with pytest.raises(ValidationError, match="denied requires at least one evidence"):
            PHQ8ItemScore(
                discussed=True, score=0, assertion="denied",
                confidence=0.90, evidence=[]
            )

    def test_possible_requires_evidence(self):
        with pytest.raises(ValidationError, match="possible requires at least one evidence"):
            PHQ8ItemScore(
                discussed=True, score=1, assertion="possible",
                confidence=0.60, evidence=[]
            )

    # --- Evidence constraint tests ---

    def test_evidence_snippet_max_chars(self):
        long_snippet = "x" * 401  # Exceeds MAX_EVIDENCE_SNIPPET_CHARS (400)
        with pytest.raises(ValidationError, match="exceeds 400 chars"):
            PHQ8ItemScore(
                discussed=True, score=1, assertion="present",
                confidence=0.70, evidence=[long_snippet]
            )

    def test_evidence_snippet_max_words(self):
        many_words = " ".join(["word"] * 51)  # Exceeds MAX_EVIDENCE_SNIPPET_WORDS (50)
        with pytest.raises(ValidationError, match="exceeds 50 words"):
            PHQ8ItemScore(
                discussed=True, score=1, assertion="present",
                confidence=0.70, evidence=[many_words]
            )

    def test_evidence_snippet_whitespace_only(self):
        with pytest.raises(ValidationError, match="non-empty after stripping"):
            PHQ8ItemScore(
                discussed=True, score=1, assertion="present",
                confidence=0.70, evidence=["   \t\n  "]
            )

    def test_evidence_snippet_empty_string(self):
        with pytest.raises(ValidationError, match="non-empty after stripping"):
            PHQ8ItemScore(
                discussed=True, score=1, assertion="present",
                confidence=0.70, evidence=[""]
            )

    def test_evidence_exceeds_max_length(self):
        with pytest.raises(ValidationError, match="at most 3 items"):
            PHQ8ItemScore(
                discussed=True, score=2, assertion="present",
                confidence=0.80, evidence=["a", "b", "c", "d"]
            )

    # --- Confidence range tests ---

    def test_confidence_above_one(self):
        with pytest.raises(ValidationError, match="less than or equal to 1"):
            PHQ8ItemScore(
                discussed=True, score=1, assertion="present",
                confidence=1.1, evidence=["quote"]
            )

    def test_confidence_below_zero(self):
        with pytest.raises(ValidationError, match="greater than or equal to 0"):
            PHQ8ItemScore(
                discussed=True, score=1, assertion="present",
                confidence=-0.1, evidence=["quote"]
            )
```

---

## 5. Schema: `PHQ8Assessment` Updates

### 5.1 Changes Required

- `total_score` → computed from non-None scores (imputed: NA=0)
- Add `discussed_count: int` field
- Keep `mentions_self_harm` and `self_harm_evidence` (unchanged)
- Update model validator for new item schema

### 5.2 New Schema

```python
# File: src/vibe_check/schemas/scoring.py (additions to PHQ8Assessment)

class PHQ8Assessment(BaseModel):
    """The raw output from the LLM (items + total + safety)."""

    model_config = ConfigDict(extra="forbid")

    anhedonia: PHQ8ItemScore
    depressed_mood: PHQ8ItemScore
    sleep: PHQ8ItemScore
    fatigue: PHQ8ItemScore
    appetite: PHQ8ItemScore
    guilt: PHQ8ItemScore
    concentration: PHQ8ItemScore
    psychomotor: PHQ8ItemScore

    # Computed fields (imputed: NA→0)
    total_score: int = Field(ge=0, le=24, description="Sum of item scores; NA items contribute 0")
    discussed_count: int = Field(ge=0, le=8, description="Count of items with discussed=True")

    # Safety fields (unchanged)
    mentions_self_harm: bool = False
    self_harm_evidence: list[str] = Field(default_factory=list, max_length=3)

    @property
    def item_scores(self) -> dict[str, int | None]:
        """Return item scores (None for not_mentioned)."""
        return {
            "anhedonia": self.anhedonia.score,
            "depressed_mood": self.depressed_mood.score,
            "sleep": self.sleep.score,
            "fatigue": self.fatigue.score,
            "appetite": self.appetite.score,
            "guilt": self.guilt.score,
            "concentration": self.concentration.score,
            "psychomotor": self.psychomotor.score,
        }

    @model_validator(mode="before")
    @classmethod
    def _canonicalize_computed_fields(cls, data: Any) -> Any:
        """Compute total_score and discussed_count from items."""
        if not isinstance(data, dict):
            return data

        item_keys = (
            "anhedonia", "depressed_mood", "sleep", "fatigue",
            "appetite", "guilt", "concentration", "psychomotor",
        )

        total = 0
        discussed = 0
        for key in item_keys:
            item = data.get(key)
            if item is None:
                continue
            score = item.get("score") if isinstance(item, dict) else getattr(item, "score", None)
            disc = item.get("discussed") if isinstance(item, dict) else getattr(item, "discussed", None)

            if score is not None:
                total += int(score)
            if disc is True:
                discussed += 1

        # Canonicalize (overwrite if inconsistent)
        data["total_score"] = total
        data["discussed_count"] = discussed
        return data

    @model_validator(mode="after")
    def _check_computed_fields(self) -> "PHQ8Assessment":
        """Validate computed fields match actual items."""
        expected_total = sum(
            s if s is not None else 0
            for s in self.item_scores.values()
        )
        expected_discussed = sum(
            1 for item in [self.anhedonia, self.depressed_mood, self.sleep, self.fatigue,
                          self.appetite, self.guilt, self.concentration, self.psychomotor]
            if item.discussed
        )
        if self.total_score != expected_total:
            raise ValueError(f"total_score={self.total_score} != computed {expected_total}")
        if self.discussed_count != expected_discussed:
            raise ValueError(f"discussed_count={self.discussed_count} != computed {expected_discussed}")
        return self
```

### 5.3 TDD Test Cases: `PHQ8Assessment`

```python
class TestPHQ8AssessmentNA:
    """PHQ8Assessment tests with NA items."""

    def _make_item(self, score: int | None, assertion: str) -> dict:
        if assertion == "not_mentioned":
            return {"discussed": False, "score": None, "assertion": "not_mentioned",
                    "confidence": None, "evidence": []}
        elif assertion == "denied":
            return {"discussed": True, "score": 0, "assertion": "denied",
                    "confidence": 0.9, "evidence": ["I'm fine"]}
        else:
            return {"discussed": True, "score": score, "assertion": assertion,
                    "confidence": 0.8, "evidence": ["quote"]}

    def test_all_items_discussed(self):
        assessment = PHQ8Assessment(
            anhedonia=self._make_item(2, "present"),
            depressed_mood=self._make_item(3, "present"),
            sleep=self._make_item(1, "present"),
            fatigue=self._make_item(2, "present"),
            appetite=self._make_item(0, "denied"),
            guilt=self._make_item(1, "present"),
            concentration=self._make_item(2, "present"),
            psychomotor=self._make_item(0, "denied"),
        )
        assert assessment.total_score == 11  # 2+3+1+2+0+1+2+0
        assert assessment.discussed_count == 8

    def test_with_na_items(self):
        assessment = PHQ8Assessment(
            anhedonia=self._make_item(2, "present"),
            depressed_mood=self._make_item(3, "present"),
            sleep=self._make_item(None, "not_mentioned"),
            fatigue=self._make_item(2, "present"),
            appetite=self._make_item(None, "not_mentioned"),
            guilt=self._make_item(None, "not_mentioned"),
            concentration=self._make_item(1, "possible"),
            psychomotor=self._make_item(None, "not_mentioned"),
        )
        # total_score = 2+3+0+2+0+0+1+0 = 8 (NA→0)
        assert assessment.total_score == 8
        assert assessment.discussed_count == 4

    def test_all_na(self):
        assessment = PHQ8Assessment(
            anhedonia=self._make_item(None, "not_mentioned"),
            depressed_mood=self._make_item(None, "not_mentioned"),
            sleep=self._make_item(None, "not_mentioned"),
            fatigue=self._make_item(None, "not_mentioned"),
            appetite=self._make_item(None, "not_mentioned"),
            guilt=self._make_item(None, "not_mentioned"),
            concentration=self._make_item(None, "not_mentioned"),
            psychomotor=self._make_item(None, "not_mentioned"),
        )
        assert assessment.total_score == 0
        assert assessment.discussed_count == 0
```

---

## 6. Schema: `PHQ8TotalScore` (NEW)

### 6.1 Definition (per SSOT §12.2)

```python
# File: src/vibe_check/schemas/scoring.py (new class)

from decimal import ROUND_HALF_UP, Decimal


class PHQ8TotalScore(BaseModel):
    """Total score with full provenance (SSOT §12.2)."""

    model_config = ConfigDict(extra="forbid")

    # Source data
    discussed_count: int = Field(ge=0, le=8)
    discussed_sum: int = Field(ge=0, le=24)

    # Derived (validated by model_validator)
    coverage: float = Field(ge=0.0, le=1.0)  # discussed_count / 8
    na_count: int = Field(ge=0, le=8)        # 8 - discussed_count

    # Prorated (only when discussed_count >= 7)
    prorated_total: float | None = Field(default=None, ge=0.0, le=24.0)
    prorated_total_rounded: int | None = Field(default=None, ge=0, le=24)

    # Imputed (NA→0)
    imputed_total: int = Field(ge=0, le=24)

    # Validity flags
    is_min_coverage: bool    # discussed_count >= 4
    is_proration_valid: bool # discussed_count >= 7

    @classmethod
    def from_item_scores(cls, item_scores: dict[str, int | None]) -> "PHQ8TotalScore":
        """Canonical constructor from item scores dict."""
        if len(item_scores) != 8:
            raise ValueError("item_scores must have exactly 8 items")

        discussed_scores = [s for s in item_scores.values() if s is not None]
        discussed_count = len(discussed_scores)
        discussed_sum = sum(discussed_scores)
        na_count = 8 - discussed_count

        coverage = discussed_count / 8.0
        imputed_total = discussed_sum  # NA items contribute 0

        is_min_coverage = discussed_count >= 4
        is_proration_valid = discussed_count >= 7

        prorated_total: float | None = None
        prorated_total_rounded: int | None = None
        if is_proration_valid and discussed_count > 0:
            prorated_total = (discussed_sum / discussed_count) * 8
            # Round half up (SSOT/APA convention)
            prorated_total_rounded = int(
                Decimal(str(prorated_total)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
            )

        return cls(
            discussed_count=discussed_count,
            discussed_sum=discussed_sum,
            coverage=coverage,
            na_count=na_count,
            prorated_total=prorated_total,
            prorated_total_rounded=prorated_total_rounded,
            imputed_total=imputed_total,
            is_min_coverage=is_min_coverage,
            is_proration_valid=is_proration_valid,
        )

    @model_validator(mode="after")
    def _validate_consistency(self) -> "PHQ8TotalScore":
        """Enforce internal consistency."""
        if self.na_count != 8 - self.discussed_count:
            raise ValueError("na_count must equal 8 - discussed_count")
        if abs(self.coverage - self.discussed_count / 8.0) > 1e-9:
            raise ValueError("coverage must equal discussed_count / 8")
        if self.is_min_coverage != (self.discussed_count >= 4):
            raise ValueError("is_min_coverage inconsistent with discussed_count")
        if self.is_proration_valid != (self.discussed_count >= 7):
            raise ValueError("is_proration_valid inconsistent with discussed_count")
        if not self.is_proration_valid:
            if self.prorated_total is not None or self.prorated_total_rounded is not None:
                raise ValueError("proration fields must be None when is_proration_valid=False")
        return self
```

### 6.2 TDD Test Cases: `PHQ8TotalScore`

```python
class TestPHQ8TotalScore:
    """PHQ8TotalScore tests."""

    def test_full_coverage(self):
        scores = {
            "anhedonia": 2, "depressed_mood": 3, "sleep": 1, "fatigue": 2,
            "appetite": 0, "guilt": 1, "concentration": 2, "psychomotor": 0,
        }
        total = PHQ8TotalScore.from_item_scores(scores)
        assert total.discussed_count == 8
        assert total.discussed_sum == 11
        assert total.coverage == 1.0
        assert total.na_count == 0
        assert total.imputed_total == 11
        assert total.prorated_total == 11.0
        assert total.prorated_total_rounded == 11
        assert total.is_min_coverage is True
        assert total.is_proration_valid is True

    def test_high_coverage_7_items(self):
        # 7 items, sum=14, one NA
        scores = {
            "anhedonia": 2, "depressed_mood": 3, "sleep": 1, "fatigue": 2,
            "appetite": None, "guilt": 2, "concentration": 2, "psychomotor": 2,
        }
        total = PHQ8TotalScore.from_item_scores(scores)
        assert total.discussed_count == 7
        assert total.discussed_sum == 14
        assert total.na_count == 1
        assert total.coverage == 0.875
        assert total.imputed_total == 14
        # prorated = (14/7) * 8 = 16.0
        assert total.prorated_total == 16.0
        assert total.prorated_total_rounded == 16
        assert total.is_proration_valid is True

    def test_proration_rounding_half_up(self):
        # 7 items, sum=13 → prorated = (13/7)*8 = 14.857... → 15
        scores = {
            "anhedonia": 2, "depressed_mood": 2, "sleep": 2, "fatigue": 2,
            "appetite": None, "guilt": 2, "concentration": 2, "psychomotor": 1,
        }
        total = PHQ8TotalScore.from_item_scores(scores)
        assert abs(total.prorated_total - 14.857142857142858) < 0.001
        assert total.prorated_total_rounded == 15  # Round half up

    def test_low_coverage_6_items(self):
        # 6 items, proration NOT valid (< 7)
        scores = {
            "anhedonia": 2, "depressed_mood": 3, "sleep": None, "fatigue": None,
            "appetite": 1, "guilt": 2, "concentration": 2, "psychomotor": 1,
        }
        total = PHQ8TotalScore.from_item_scores(scores)
        assert total.discussed_count == 6
        assert total.na_count == 2
        assert total.is_min_coverage is True  # 6 >= 4
        assert total.is_proration_valid is False  # 6 < 7
        assert total.prorated_total is None
        assert total.prorated_total_rounded is None

    def test_below_min_coverage_3_items(self):
        scores = {
            "anhedonia": 2, "depressed_mood": 3, "sleep": None, "fatigue": None,
            "appetite": None, "guilt": None, "concentration": None, "psychomotor": 1,
        }
        total = PHQ8TotalScore.from_item_scores(scores)
        assert total.discussed_count == 3
        assert total.is_min_coverage is False  # 3 < 4
        assert total.is_proration_valid is False

    def test_all_na(self):
        scores = {k: None for k in [
            "anhedonia", "depressed_mood", "sleep", "fatigue",
            "appetite", "guilt", "concentration", "psychomotor"
        ]}
        total = PHQ8TotalScore.from_item_scores(scores)
        assert total.discussed_count == 0
        assert total.discussed_sum == 0
        assert total.imputed_total == 0
        assert total.is_min_coverage is False
        assert total.is_proration_valid is False

    def test_consistency_validator_catches_bad_na_count(self):
        with pytest.raises(ValidationError, match="na_count must equal"):
            PHQ8TotalScore(
                discussed_count=5, discussed_sum=10, coverage=0.625,
                na_count=2,  # Wrong! Should be 3
                imputed_total=10, is_min_coverage=True, is_proration_valid=False
            )

    def test_consistency_validator_catches_bad_coverage(self):
        with pytest.raises(ValidationError, match="coverage must equal"):
            PHQ8TotalScore(
                discussed_count=5, discussed_sum=10, coverage=0.5,  # Wrong! Should be 0.625
                na_count=3, imputed_total=10, is_min_coverage=True, is_proration_valid=False
            )

    def test_consistency_validator_catches_proration_when_invalid(self):
        with pytest.raises(ValidationError, match="proration fields must be None"):
            PHQ8TotalScore(
                discussed_count=5, discussed_sum=10, coverage=0.625,
                na_count=3, prorated_total=16.0, prorated_total_rounded=16,  # Invalid!
                imputed_total=10, is_min_coverage=True, is_proration_valid=False
            )
```

---

## 7. Backward Compatibility

### 7.1 SPEC-08 Export Unchanged

The existing `aggregated_to_export_record()` function in `src/vibe_check/export/writer.py` must continue to produce int-only scores by imputing NA→0.

**Test coverage location**: SPEC-08 compatibility is verified in SPEC-16 (export specs), including type-level checks that `ScoredDialogueExport` remains int-only and rejects `None` inputs.

### 7.2 PHQ8Report Compatibility

`PHQ8Report` extends `PHQ8Assessment`, so it inherits all new fields automatically.

---

## 8. Files Affected

| File | Change Type | Description |
|------|-------------|-------------|
| `src/vibe_check/schemas/scoring.py` | **MAJOR** | Add `discussed`, `assertion`, `PHQ8TotalScore`; update validators |
| `src/vibe_check/constants.py` | **MINOR** | Add `Assertion` type alias (optional) |
| `tests/unit/test_schemas_scoring.py` | **MAJOR** | All tests in Section 4-6 |
| `tests/conftest.py` | **MODERATE** | Update fixtures for new schema |

---

## 9. Acceptance Criteria

- [ ] All tests in Section 4.1 (valid constructions) pass
- [ ] All tests in Section 4.2 (invalid constructions) raise `ValidationError`
- [ ] All tests in Section 5.3 (`PHQ8Assessment`) pass
- [ ] All tests in Section 6.2 (`PHQ8TotalScore`) pass
- [ ] `PHQ8TotalScore.from_item_scores()` is the canonical constructor
- [ ] Proration uses ROUND_HALF_UP
- [ ] SPEC-08 export unchanged (imputes NA→0)
- [ ] `ruff check` + `mypy --strict` pass
- [ ] pytest coverage ≥90% for `schemas/scoring.py`

---

## 10. Sign-Off

| Role | Status |
|------|--------|
| Author | IMPLEMENTED |
| Senior Review | APPROVED |
