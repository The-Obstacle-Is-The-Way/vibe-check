from __future__ import annotations

from vibe_check.data.splitter import compute_split


def test_split_deterministic() -> None:
    assert compute_split("active436") == compute_split("active436")


def test_split_distribution() -> None:
    splits = [compute_split(f"file_{i}") for i in range(1000)]
    train_pct = splits.count("train") / 1000
    assert 0.75 < train_pct < 0.85


def test_known_file_ids() -> None:
    assert compute_split("active436") in ["train", "dev", "test"]
    assert compute_split("active422") in ["train", "dev", "test"]
