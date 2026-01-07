# SPEC-16: HuggingFace NA-Aware Export (Phase 1)

> **Status**: DRAFT v2 (post-senior review)
> **Depends On**: SPEC-13 (NA-aware juror schema), SPEC-15 (NA-aware aggregation), SPEC-17 (NA-aware judge)
> **Must Not Modify**: `src/vibe_check/export/schemas.py` (SPEC-08 stable public contract)

---

## 1. Overview

This spec defines a **separate** NA-aware export format intended for HuggingFace publication and research use. It preserves:
- Per-item `assertion` and `score=null` for `not_mentioned`
- Coverage/proration provenance in totals
- Prompt + model provenance metadata

This export is **not** a replacement for SPEC-08; SPEC-08 remains int-only.

---

## 2. CLI Contract (must match existing argparse CLI)

### 2.1 CLI Signature

```bash
# Current (SPEC-08):
vibe-check export --input scored.jsonl --output-dir ./exports --format jsonl,csv

# Extended (adds HuggingFace):
vibe-check export --input scored.jsonl --output-dir ./exports --format jsonl,csv,huggingface
```

### 2.2 Format Semantics (no ambiguity)

Let `formats = set(args.format.split(","))` (trimmed).

- If `formats` contains `huggingface`, write `vibe_check_labels_huggingface.jsonl`.
- SPEC-08 exports are written **only** for `spec08_formats = formats - {"huggingface"}`:
  - If `spec08_formats` is empty, do **not** write SPEC-08 files.
  - Otherwise, call existing `write_label_exports(scored_jsonl, output_dir, formats=spec08_formats)`.

### 2.3 Output Files

- `vibe_check_labels.jsonl` (SPEC-08, unchanged, always int-only)
- `vibe_check_labels.csv` (SPEC-08, unchanged, only when `csv` requested)
- `vibe_check_labels_huggingface.jsonl` (**NEW**, NA-aware)

---

## 3. HuggingFace Export Schema (SSOT §12.4)

### 3.1 Pydantic Schema

```python
# File: src/vibe_check/export/huggingface_schema.py
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from vibe_check.constants import PHQ8_ITEMS

Assertion = Literal["present", "denied", "possible", "not_mentioned"]
Split = Literal["train", "dev", "test"]


class HuggingFaceItemExport(BaseModel):
    """Single PHQ-8 item in HuggingFace export (final label; NA-aware)."""

    model_config = ConfigDict(extra="forbid")

    score: Literal[0, 1, 2, 3] | None = Field(
        description="Severity score; null iff assertion=='not_mentioned'",
    )
    assertion: Assertion
    confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="null iff assertion=='not_mentioned'",
    )
    evidence: list[str] = Field(
        default_factory=list,
        max_length=3,
        description="[] iff assertion=='not_mentioned'; otherwise 1-3 snippets",
    )

    @model_validator(mode="after")
    def _validate_semantics(self) -> "HuggingFaceItemExport":
        # not_mentioned: strict nulls
        if self.assertion == "not_mentioned":
            if self.score is not None:
                raise ValueError("not_mentioned requires score=None")
            if self.confidence is not None:
                raise ValueError("not_mentioned requires confidence=None")
            if self.evidence:
                raise ValueError("not_mentioned requires evidence=[]")
            return self

        # For all discussed assertions: score/confidence/evidence required
        if self.score is None:
            raise ValueError(f"{self.assertion} requires score != None")
        if self.confidence is None:
            raise ValueError(f"{self.assertion} requires confidence != None")
        if not self.evidence:
            raise ValueError(f"{self.assertion} requires at least one evidence snippet")

        # Assertion-specific score constraints (SSOT §12.1)
        if self.assertion == "denied" and self.score != 0:
            raise ValueError("denied requires score=0")
        if self.assertion == "present" and self.score not in (1, 2, 3):
            raise ValueError("present requires score in {1, 2, 3}")
        if self.assertion == "possible" and self.score != 1:
            raise ValueError("possible requires score=1")
        return self


class HuggingFaceTotalsExport(BaseModel):
    """Totals/provenance section for HuggingFace export (SSOT §12.2/§12.4)."""

    model_config = ConfigDict(extra="forbid")

    discussed_count: int = Field(ge=0, le=8)
    discussed_sum: int = Field(ge=0, le=24)
    coverage: float = Field(ge=0.0, le=1.0)  # discussed_count / 8

    prorated_total: float | None = None
    prorated_total_rounded: int | None = Field(default=None, ge=0, le=24)

    imputed_total: int = Field(ge=0, le=24)
    na_count: int = Field(ge=0, le=8)

    is_min_coverage: bool
    is_proration_valid: bool

    @model_validator(mode="after")
    def _validate_consistency(self) -> "HuggingFaceTotalsExport":
        if self.na_count != 8 - self.discussed_count:
            raise ValueError("na_count must equal 8 - discussed_count")
        if abs(self.coverage - (self.discussed_count / 8.0)) > 1e-9:
            raise ValueError("coverage must equal discussed_count / 8")
        if self.is_min_coverage != (self.discussed_count >= 4):
            raise ValueError("is_min_coverage inconsistent with discussed_count")
        if self.is_proration_valid != (self.discussed_count >= 7):
            raise ValueError("is_proration_valid inconsistent with discussed_count")

        if not self.is_proration_valid:
            if self.prorated_total is not None or self.prorated_total_rounded is not None:
                raise ValueError("proration fields must be None when is_proration_valid=False")
        else:
            if self.prorated_total is None or self.prorated_total_rounded is None:
                raise ValueError("proration fields must be set when is_proration_valid=True")
        return self


class HuggingFaceMetadataExport(BaseModel):
    """Run metadata (SSOT §12.4)."""

    model_config = ConfigDict(extra="forbid")

    prompt_version: str = Field(min_length=1)
    juror_models: list[str] = Field(min_length=1)
    runs_per_model: int = Field(ge=1)
    arbitration_triggered: bool
    judge_model: str | None = None

    @model_validator(mode="after")
    def _validate_judge_model(self) -> "HuggingFaceMetadataExport":
        if not self.arbitration_triggered and self.judge_model is not None:
            raise ValueError("judge_model must be None when arbitration_triggered=False")
        return self


class HuggingFaceDialogueExport(BaseModel):
    """One exported record (1 row in JSONL)."""

    model_config = ConfigDict(extra="forbid")

    dialogue_id: str = Field(min_length=1)
    condition: Literal["mdd", "control"]
    split: Split

    items: dict[str, HuggingFaceItemExport]
    totals: HuggingFaceTotalsExport
    scoring_metadata: HuggingFaceMetadataExport

    @model_validator(mode="after")
    def _validate_item_keys(self) -> "HuggingFaceDialogueExport":
        expected = set(PHQ8_ITEMS)
        actual = set(self.items.keys())
        if actual != expected:
            missing = expected - actual
            extra = actual - expected
            raise ValueError(f"items must match PHQ8_ITEMS. Missing={missing}, Extra={extra}")
        return self
```

---

## 4. Export Implementation (conversion + writer)

### 4.1 Conversion Rules (ironclad)

For each scored.jsonl row:

1. `dialogue_id` = `AggregatedPHQ8.file_id`
2. `condition` = `AggregatedPHQ8.condition`
3. `split` = `raw["computed_split"]` (must be one of `train/dev/test`; error if missing)
4. For each PHQ-8 item:
   - Default to jury consensus from `AggregatedPHQ8.items[item].consensus_*`
   - If `AggregatedPHQ8.judge_resolution` contains the item, **override** with judge decision
   - `confidence/evidence` are sourced deterministically:
     - If final assertion is `not_mentioned`: `confidence=null`, `evidence=[]`
     - Else if final source is judge override: use judge `confidence` + `evidence`
     - Else (jury): select the single juror report with **max confidence** among jurors matching the final `(assertion, score)`; tie-break by `(model_id, run_number)` ascending; use that juror's `confidence` + `evidence`
5. `totals` is taken from `AggregatedPHQ8.totals` (must satisfy SSOT invariants)
6. `scoring_metadata`:
   - `prompt_version` = `AggregatedPHQ8.prompt_version`
   - `juror_models` = sorted unique `PHQ8Report.model_id`
   - `runs_per_model` = max `PHQ8Report.run_number` (must be consistent across juror_models; otherwise raise)
   - `arbitration_triggered` = `AggregatedPHQ8.triggered_arbitration`
   - `judge_model`:
     - If `arbitration_triggered` is false: `null`
     - Else: best-effort from `run_manifest.json` (if present); otherwise `null`

### 4.2 Writer API

```python
# File: src/vibe_check/export/huggingface.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from vibe_check.constants import PHQ8_ITEMS
from vibe_check.export.huggingface_schema import (
    HuggingFaceDialogueExport,
    HuggingFaceItemExport,
    HuggingFaceMetadataExport,
    HuggingFaceTotalsExport,
    Split,
)
from vibe_check.schemas.output import AggregatedPHQ8


def write_huggingface_export(
    *,
    scored_jsonl: str | Path,
    output_dir: str | Path,
    run_manifest: str | Path | None = None,
) -> None:
    """Write NA-aware HuggingFace export JSONL (separate from SPEC-08)."""
    scored_path = Path(scored_jsonl)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = Path(run_manifest) if run_manifest is not None else scored_path.with_name("run_manifest.json")
    judge_model: str | None = None
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        run_cfg = manifest.get("run_config") if isinstance(manifest, dict) else None
        # Best-effort: allow future additions without breaking export.
        if isinstance(run_cfg, dict):
            judge_model = cast(str | None, run_cfg.get("judge_model") or run_cfg.get("judge_model_id"))
            judge_item = run_cfg.get("judge_item")
            if judge_model is None and isinstance(judge_item, dict):
                judge_model = cast(str | None, judge_item.get("model_id"))

    exports: list[HuggingFaceDialogueExport] = []

    for line in scored_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        raw: dict[str, Any] = json.loads(line)
        split = raw.get("computed_split")
        if split not in ("train", "dev", "test"):
            raise ValueError(f"computed_split must be train/dev/test, got {split!r}")

        filtered = {k: raw[k] for k in AggregatedPHQ8.model_fields if k in raw}
        aggregated = AggregatedPHQ8.model_validate(filtered)

        exports.append(_aggregated_to_record(aggregated, split=cast(Split, split), judge_model=judge_model))

    exports.sort(key=lambda r: r.dialogue_id)
    output_path = out_dir / "vibe_check_labels_huggingface.jsonl"
    output_path.write_text(
        "\n".join(json.dumps(e.model_dump(mode="json"), sort_keys=True) for e in exports) + "\n",
        encoding="utf-8",
    )


def _aggregated_to_record(
    aggregated: AggregatedPHQ8,
    *,
    split: Split,
    judge_model: str | None,
) -> HuggingFaceDialogueExport:
    # Juror provenance
    juror_models = sorted({r.model_id for r in aggregated.juror_reports})
    runs_per_model = max(r.run_number for r in aggregated.juror_reports)
    for model_id in juror_models:
        runs = {r.run_number for r in aggregated.juror_reports if r.model_id == model_id}
        if runs != set(range(1, runs_per_model + 1)):
            raise ValueError(f"inconsistent runs for model_id={model_id!r}: {sorted(runs)}")

    metadata = HuggingFaceMetadataExport(
        prompt_version=aggregated.prompt_version,
        juror_models=juror_models,
        runs_per_model=runs_per_model,
        arbitration_triggered=bool(aggregated.triggered_arbitration),
        judge_model=judge_model if aggregated.triggered_arbitration else None,
    )

    items: dict[str, HuggingFaceItemExport] = {}
    judge_map = aggregated.judge_resolution or {}

    for item in PHQ8_ITEMS:
        if item in judge_map:
            # Expected: JudgeItemResolutionNA dict (SPEC-17); tolerate dict-like only.
            resolution = judge_map[item]
            assertion = resolution.get("assertion") if isinstance(resolution, dict) else None
            score = resolution.get("final_score") if isinstance(resolution, dict) else None
            confidence = resolution.get("confidence") if isinstance(resolution, dict) else None
            evidence = resolution.get("evidence") if isinstance(resolution, dict) else None
            items[item] = HuggingFaceItemExport(
                assertion=assertion,
                score=score,
                confidence=confidence,
                evidence=evidence or [],
            )
            continue

        item_agg = aggregated.items[item]
        assertion = item_agg.consensus_assertion
        score = item_agg.consensus_score
        if assertion == "not_mentioned":
            items[item] = HuggingFaceItemExport(
                assertion="not_mentioned",
                score=None,
                confidence=None,
                evidence=[],
            )
            continue

        # Deterministic evidence/confidence: max confidence among matching jurors
        candidates = []
        for r in aggregated.juror_reports:
            juror_item = getattr(r, item)
            if juror_item.assertion == assertion and juror_item.score == score:
                candidates.append((float(juror_item.confidence), r.model_id, int(r.run_number), juror_item.evidence))
        if not candidates:
            raise ValueError(f"no juror candidates for item={item!r} consensus=({assertion!r}, {score!r})")
        candidates.sort(key=lambda x: (-x[0], x[1], x[2]))
        best_confidence, _, _, best_evidence = candidates[0]

        items[item] = HuggingFaceItemExport(
            assertion=assertion,
            score=score,
            confidence=best_confidence,
            evidence=list(best_evidence),
        )

    totals = HuggingFaceTotalsExport(**aggregated.totals.model_dump())

    return HuggingFaceDialogueExport(
        dialogue_id=aggregated.file_id,
        condition=aggregated.condition,
        split=split,
        items=items,
        totals=totals,
        scoring_metadata=metadata,
    )
```

---

## 5. TDD Test Cases

### 5.1 Schema Validation (unit)

```python
# File: tests/unit/test_huggingface_schema.py
import pytest
from pydantic import ValidationError

from vibe_check.constants import PHQ8_ITEMS
from vibe_check.export.huggingface_schema import (
    HuggingFaceDialogueExport,
    HuggingFaceItemExport,
    HuggingFaceMetadataExport,
    HuggingFaceTotalsExport,
)


class TestHuggingFaceItemExport:
    def test_not_mentioned_is_strict_nulls(self):
        item = HuggingFaceItemExport(
            assertion="not_mentioned",
            score=None,
            confidence=None,
            evidence=[],
        )
        assert item.score is None

    def test_present_requires_score_1_to_3(self):
        with pytest.raises(ValidationError, match="present requires score"):
            HuggingFaceItemExport(
                assertion="present",
                score=0,
                confidence=0.8,
                evidence=["..."],
            )

    def test_denied_requires_score_0(self):
        with pytest.raises(ValidationError, match="denied requires score=0"):
            HuggingFaceItemExport(
                assertion="denied",
                score=2,
                confidence=0.8,
                evidence=["..."],
            )

    def test_possible_requires_score_1(self):
        with pytest.raises(ValidationError, match="possible requires score=1"):
            HuggingFaceItemExport(
                assertion="possible",
                score=2,
                confidence=0.6,
                evidence=["Maybe..."],
            )

    def test_non_na_requires_evidence(self):
        with pytest.raises(ValidationError, match="requires at least one evidence"):
            HuggingFaceItemExport(
                assertion="present",
                score=1,
                confidence=0.6,
                evidence=[],
            )


class TestHuggingFaceDialogueExport:
    def _make_items(self) -> dict[str, HuggingFaceItemExport]:
        items: dict[str, HuggingFaceItemExport] = {}
        for item in PHQ8_ITEMS:
            items[item] = HuggingFaceItemExport(
                assertion="present",
                score=1,
                confidence=0.8,
                evidence=["evidence"],
            )
        return items

    def _make_totals(self) -> HuggingFaceTotalsExport:
        return HuggingFaceTotalsExport(
            discussed_count=8,
            discussed_sum=8,
            coverage=1.0,
            prorated_total=8.0,
            prorated_total_rounded=8,
            imputed_total=8,
            na_count=0,
            is_min_coverage=True,
            is_proration_valid=True,
        )

    def _make_metadata(self) -> HuggingFaceMetadataExport:
        return HuggingFaceMetadataExport(
            prompt_version="v2.0.0-clinical",
            juror_models=["gpt-5.2"],
            runs_per_model=2,
            arbitration_triggered=False,
            judge_model=None,
        )

    def test_items_keys_must_match(self):
        items = self._make_items()
        del items["psychomotor"]
        with pytest.raises(ValidationError, match="Missing="):
            HuggingFaceDialogueExport(
                dialogue_id="d1",
                condition="mdd",
                split="train",
                items=items,
                totals=self._make_totals(),
                scoring_metadata=self._make_metadata(),
            )
```

### 5.2 Writer + CLI Integration (deterministic; no cli_runner fixture)

```python
# File: tests/integration/test_cli_export_huggingface.py
import json
from pathlib import Path

from vibe_check.cli import main


def test_cli_export_huggingface_only(tmp_path: Path):
    scored = tmp_path / "scored.jsonl"
    exports_dir = tmp_path / "exports"

    # Minimal scored.jsonl row: this test assumes SPEC-15 AggregatedPHQ8 schema is implemented.
    # The easiest way to build it in tests is to construct an AggregatedPHQ8 and dump to JSON.
    from tests.unit.utils import make_minimal_aggregated_phq8_na  # Introduce in this PR/spec set

    row = make_minimal_aggregated_phq8_na(file_id="active001").model_dump(mode="json")
    row["computed_split"] = "train"
    scored.write_text(json.dumps(row) + "\n", encoding="utf-8")

    rc = main(
        [
            "export",
            "--input",
            str(scored),
            "--output-dir",
            str(exports_dir),
            "--format",
            "huggingface",
        ]
    )
    assert rc == 0
    assert (exports_dir / "vibe_check_labels_huggingface.jsonl").exists()
    assert not (exports_dir / "vibe_check_labels.jsonl").exists()


def test_cli_export_all_formats(tmp_path: Path):
    scored = tmp_path / "scored.jsonl"
    exports_dir = tmp_path / "exports"

    from tests.unit.utils import make_minimal_aggregated_phq8_na

    row = make_minimal_aggregated_phq8_na(file_id="active001").model_dump(mode="json")
    row["computed_split"] = "dev"
    row["scoring_text"] = "Client: ..."
    row["dialogue_view"] = "client_qa"
    scored.write_text(json.dumps(row) + "\n", encoding="utf-8")

    rc = main(
        [
            "export",
            "--input",
            str(scored),
            "--output-dir",
            str(exports_dir),
            "--format",
            "jsonl,csv,huggingface",
        ]
    )
    assert rc == 0
    assert (exports_dir / "vibe_check_labels.jsonl").exists()
    assert (exports_dir / "vibe_check_labels.csv").exists()
    assert (exports_dir / "vibe_check_labels_huggingface.jsonl").exists()
```

**Note**: This spec introduces `tests/unit/utils.py::make_minimal_aggregated_phq8_na()` as a shared deterministic fixture builder for Phase 1 specs (SPEC-15/16/18). If you do not want a shared helper, inline an equivalent constructor in each test file.

---

## 6. Files Affected

| File | Change Type | Notes |
|------|-------------|-------|
| `src/vibe_check/export/huggingface_schema.py` | **NEW** | HF export pydantic schemas |
| `src/vibe_check/export/huggingface.py` | **NEW** | Writer + conversion |
| `src/vibe_check/cli.py` | **MODERATE** | Add `huggingface` format routing (argparse) |
| `tests/unit/test_huggingface_schema.py` | **NEW** | Schema invariants |
| `tests/integration/test_cli_export_huggingface.py` | **NEW** | CLI integration via `main([...])` |

---

## 7. Acceptance Criteria

- [ ] `possible` is **score=1 only** (schema-enforced)
- [ ] `not_mentioned` is **score=null, confidence=null, evidence=[]** (schema-enforced)
- [ ] Export writes `vibe_check_labels_huggingface.jsonl` with per-row `split`
- [ ] CLI supports comma-separated `--format ...huggingface...` with argparse
- [ ] SPEC-08 schema (`src/vibe_check/export/schemas.py`) remains unchanged
- [ ] Tests are deterministic (no live LLM calls) and runnable via pytest

---

## 8. Sign-Off

| Role | Status |
|------|--------|
| Author | DRAFT v2 |
| Senior Review | PENDING |
