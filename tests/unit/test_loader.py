from __future__ import annotations

import csv
from typing import TYPE_CHECKING

import pytest

from vibe_check.data.loader import load_corpus

if TYPE_CHECKING:
    from pathlib import Path


def test_load_corpus_csv_sorted_and_split_set(tmp_path: Path) -> None:
    csv_path = tmp_path / "sample.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["file_id", "condition", "client_model", "therapist_model", "dialogue"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "file_id": "b",
                "condition": "control",
                "client_model": "x",
                "therapist_model": "y",
                "dialogue": "Therapist: Hello\nClient: Hi",
            }
        )
        writer.writerow(
            {
                "file_id": "a",
                "condition": "mdd",
                "client_model": "x",
                "therapist_model": "y",
                "dialogue": "Therapist: Hello\nClient: Hi",
            }
        )

    corpus = load_corpus(csv_path, source="csv")
    assert [d.file_id for d in corpus] == ["a", "b"]
    assert all(d.computed_split is not None for d in corpus)


def test_load_corpus_missing_path() -> None:
    with pytest.raises(FileNotFoundError):
        load_corpus("does-not-exist.csv")
