"""Sampling utilities for building a human-annotated golden set (SPEC-09)."""

from __future__ import annotations

import csv
import json
import random
from pathlib import Path
from typing import Any


def _mean_item_entropy(row: dict[str, Any]) -> float:
    items = row.get("items")
    if not isinstance(items, dict):
        raise ValueError("scored.jsonl row missing required dict field: items")

    entropies: list[float] = []
    for item in items.values():
        if not isinstance(item, dict):
            continue
        entropy = item.get("entropy")
        if isinstance(entropy, int | float):
            entropies.append(float(entropy))
    if not entropies:
        return 0.0
    return sum(entropies) / len(entropies)


def _max_vote_range(row: dict[str, Any]) -> int:
    items = row.get("items")
    if not isinstance(items, dict):
        raise ValueError("scored.jsonl row missing required dict field: items")

    ranges: list[int] = []
    for item in items.values():
        if not isinstance(item, dict):
            continue
        vr = item.get("vote_range")
        if isinstance(vr, int):
            ranges.append(vr)
    return max(ranges) if ranges else 0


def _load_scored_rows(scored_jsonl: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in scored_jsonl.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        raw = json.loads(line)
        if not isinstance(raw, dict):
            raise ValueError("scored.jsonl row is not an object")
        rows.append(raw)
    return rows


def sample_for_annotation(
    *,
    scored_jsonl: str | Path,
    n: int,
    output_csv: str | Path,
    strategy: str = "hybrid",
    seed: int = 0,
) -> None:
    """Sample dialogues from `scored.jsonl` for human annotation."""
    if n < 1:
        raise ValueError("n must be >= 1")
    if strategy != "hybrid":
        raise ValueError("Only strategy='hybrid' is supported")

    scored_path = Path(scored_jsonl)
    rows = _load_scored_rows(scored_path)
    if not rows:
        raise ValueError("scored.jsonl is empty")

    # Validate file_id presence and build candidate set.
    normalized: list[dict[str, Any]] = []
    for row in rows:
        file_id = row.get("file_id")
        if not isinstance(file_id, str) or not file_id.strip():
            raise ValueError("scored.jsonl row missing required field: file_id")
        normalized.append(row)

    if n > len(normalized):
        raise ValueError("n exceeds available dialogues in scored.jsonl")

    n_uncertain_target = n // 2

    candidates: list[dict[str, Any]] = []
    for row in normalized:
        triggered = row.get("triggered_arbitration") is True
        mean_entropy = _mean_item_entropy(row)
        max_range = _max_vote_range(row)
        if triggered or mean_entropy > 1.0 or max_range >= 2:
            candidates.append(row)

    candidates.sort(
        key=lambda r: (
            r.get("triggered_arbitration") is True,
            _mean_item_entropy(r),
            _max_vote_range(r),
            str(r.get("file_id", "")),
        ),
        reverse=True,
    )
    uncertain = candidates[: min(n_uncertain_target, len(candidates))]

    remaining = [r for r in normalized if r not in uncertain]
    rng = random.Random(seed)
    n_random = n - len(uncertain)
    random_slice = rng.sample(remaining, k=n_random)

    sampled = uncertain + random_slice
    sampled.sort(key=lambda r: str(r["file_id"]))

    output_path = Path(output_csv)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "file_id",
        "annotator_id",
        "phq8_total",
        "phq8_item_1",
        "phq8_item_2",
        "phq8_item_3",
        "phq8_item_4",
        "phq8_item_5",
        "phq8_item_6",
        "phq8_item_7",
        "phq8_item_8",
        "self_harm_flag",
        "notes",
    ]

    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in sampled:
            writer.writerow({k: (row["file_id"] if k == "file_id" else "") for k in fieldnames})
