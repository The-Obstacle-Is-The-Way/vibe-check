"""Export validation utilities (SPEC-08)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from vibe_check.export.schemas import ScoredDialogueExport


class ExportValidationIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    line_number: int = Field(ge=1)
    error: str


class ExportValidationReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_valid: bool
    n_dialogues: int = Field(ge=0)
    n_errors: int = Field(ge=0)
    issues: list[ExportValidationIssue] = Field(default_factory=list)
    records: list[ScoredDialogueExport] = Field(default_factory=list)


def validate_label_export(path: str | Path) -> ExportValidationReport:
    """Validate a public export JSONL file against the ScoredDialogueExport schema."""
    export_path = Path(path)
    issues: list[ExportValidationIssue] = []
    records: list[ScoredDialogueExport] = []

    for idx, line in enumerate(export_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            raw: dict[str, Any] = json.loads(line)
            record = ScoredDialogueExport.model_validate(raw)
            records.append(record)
        except Exception as e:
            issues.append(ExportValidationIssue(line_number=idx, error=f"{type(e).__name__}: {e}"))

    return ExportValidationReport(
        is_valid=len(issues) == 0,
        n_dialogues=len(records),
        n_errors=len(issues),
        issues=issues,
        records=records,
    )
