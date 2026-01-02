"""Corpus loading from HuggingFace disk datasets or CSV."""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, cast

from vibe_check.data.splitter import compute_split
from vibe_check.schemas.input import SQPsychConvDialogue

SourceFormat = Literal["arrow", "csv", "auto"]
Condition = Literal["mdd", "control"]

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping


def _looks_like_hf_dataset_dir(path: Path) -> bool:
    return (
        (path / "dataset_dict.json").exists()
        or (path / "dataset_info.json").exists()
        or (path / "train").is_dir()
        or (path / "test").is_dir()
    )


def _iter_csv_rows(path: Path) -> Iterable[Mapping[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not row:
                continue
            yield cast("Mapping[str, str]", row)


def _iter_hf_rows(dataset_or_dict: Any) -> Iterable[Mapping[str, Any]]:
    if isinstance(dataset_or_dict, dict):
        for split_dataset in dataset_or_dict.values():
            yield from _iter_hf_rows(split_dataset)
        return

    for row in dataset_or_dict:
        yield cast("Mapping[str, Any]", row)


def _load_hf_from_disk(path: Path) -> Iterable[Mapping[str, Any]]:
    from datasets import load_from_disk

    ds = load_from_disk(str(path))
    if hasattr(ds, "values") and not hasattr(ds, "column_names"):
        return _iter_hf_rows(dict(ds))
    return _iter_hf_rows(ds)


def load_corpus(path: str | Path, source: SourceFormat = "auto") -> list[SQPsychConvDialogue]:
    """Load SQPsychConv dialogues from disk (HF Arrow dataset or CSV)."""
    resolved = Path(path)
    if not resolved.exists():
        raise FileNotFoundError(resolved)

    if source == "auto":
        if resolved.is_file():
            source = "csv" if resolved.suffix.lower() == ".csv" else "arrow"
        else:
            source = "arrow" if _looks_like_hf_dataset_dir(resolved) else "csv"

    rows: Iterable[Mapping[str, Any]] | Iterable[Mapping[str, str]]
    if source == "arrow":
        if resolved.is_file():
            raise ValueError(f"Arrow source expects a directory, got file: {resolved}")
        rows = _load_hf_from_disk(resolved)
    elif source == "csv":
        csv_path = resolved
        if resolved.is_dir():
            candidates = sorted(resolved.glob("*.csv"))
            if len(candidates) != 1:
                raise ValueError(
                    f"CSV source expects a .csv file or a directory with exactly one .csv; "
                    f"found {len(candidates)}: {resolved}"
                )
            csv_path = candidates[0]
        rows = _iter_csv_rows(csv_path)
    else:
        raise ValueError(f"Unknown source: {source}")

    by_file_id: dict[str, SQPsychConvDialogue] = {}
    file_id_hash: dict[str, str] = {}

    for row in rows:
        file_id = str(row.get("file_id", "")).strip()
        if not file_id:
            raise ValueError("Row missing required field: file_id")
        condition_raw = str(row.get("condition", "")).strip()
        if condition_raw not in {"mdd", "control"}:
            raise ValueError(f"Invalid condition for {file_id}: {condition_raw!r}")
        condition = cast("Condition", condition_raw)

        dialogue_text = str(row.get("dialogue", ""))
        digest = hashlib.sha256(dialogue_text.encode("utf-8")).hexdigest()

        existing_hash = file_id_hash.get(file_id)
        if existing_hash is not None:
            if existing_hash != digest:
                raise ValueError(f"Conflicting duplicate file_id detected: {file_id}")
            continue

        dialogue = SQPsychConvDialogue(
            file_id=file_id,
            condition=condition,
            client_model=str(row.get("client_model", "")).strip(),
            therapist_model=str(row.get("therapist_model", "")).strip(),
            dialogue=dialogue_text,
            computed_split=compute_split(file_id),
        )
        by_file_id[file_id] = dialogue
        file_id_hash[file_id] = digest

    corpus = sorted(by_file_id.values(), key=lambda d: d.file_id)
    if not corpus:
        raise ValueError(f"No dialogues loaded from: {resolved}")
    return corpus
