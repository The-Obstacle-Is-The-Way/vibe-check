"""Helpers for loading small real-data samples in tests."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Literal, cast

from vibe_check.schemas.input import SQPsychConvDialogue

Condition = Literal["mdd", "control"]


def load_dialogue_from_csv(file_id: str, csv_path: str | Path) -> SQPsychConvDialogue:
    path = Path(csv_path)
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("file_id") == file_id:
                condition_raw = str(row["condition"])
                if condition_raw not in {"mdd", "control"}:
                    raise ValueError(f"Invalid condition in {path}: {condition_raw!r}")
                return SQPsychConvDialogue(
                    file_id=str(row["file_id"]),
                    condition=cast("Condition", condition_raw),
                    client_model=str(row["client_model"]),
                    therapist_model=str(row["therapist_model"]),
                    dialogue=str(row["dialogue"]),
                )
    raise KeyError(f"file_id not found in {path}: {file_id}")
