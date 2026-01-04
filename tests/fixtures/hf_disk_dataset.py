"""Helpers for creating tiny HuggingFace `save_to_disk()` datasets in tests."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from datasets import Dataset, DatasetDict

if TYPE_CHECKING:
    from pathlib import Path

Condition = Literal["mdd", "control"]


def write_sqpsychconv_like_dataset(tmp_path: Path, *, n_train: int = 6, n_test: int = 2) -> Path:
    """Create a tiny SQPsychConv-like DatasetDict saved to disk.

    This avoids requiring the real (untracked) dataset in CI while still exercising
    our HF-on-disk loading code paths.
    """
    if n_train < 1:
        raise ValueError("n_train must be >= 1")
    if n_test < 0:
        raise ValueError("n_test must be >= 0")

    def make_rows(n: int, *, offset: int) -> dict[str, list[str]]:
        file_ids = [f"active{offset + i:04d}" for i in range(n)]
        conditions: list[Condition] = [("mdd" if i % 2 == 0 else "control") for i in range(n)]
        return {
            "file_id": file_ids,
            "condition": list(conditions),
            "client_model": ["test"] * n,
            "therapist_model": ["test"] * n,
            "dialogue": [
                "Therapist: How are you feeling today?\n"
                f"Client: I'm feeling down and tired. (id={file_id})"
                for file_id in file_ids
            ],
        }

    train = Dataset.from_dict(make_rows(n_train, offset=1))
    splits: dict[str, Dataset] = {"train": train}
    if n_test:
        splits["test"] = Dataset.from_dict(make_rows(n_test, offset=10_000))

    ds = DatasetDict(splits)
    out_dir = tmp_path / "sqpsychconv_test"
    ds.save_to_disk(str(out_dir))
    return out_dir
