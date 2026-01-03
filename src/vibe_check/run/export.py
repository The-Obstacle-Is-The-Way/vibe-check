"""Export utilities for batch runs (rows + JSONL + manifest)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

ROWS_DIR = "rows"


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def write_row(output_dir: Path, row: dict[str, Any]) -> None:
    """Write a single dialogue output row as `rows/{file_id}.json` (atomic)."""
    file_id = str(row.get("file_id", "")).strip()
    if not file_id:
        raise ValueError("row missing required field: file_id")

    rows_dir = output_dir / ROWS_DIR
    rows_dir.mkdir(parents=True, exist_ok=True)
    path = rows_dir / f"{file_id}.json"
    _atomic_write_text(path, json.dumps(row, ensure_ascii=False, sort_keys=True))


def write_scored_jsonl(output_dir: Path) -> None:
    """Materialize `scored.jsonl` from per-dialogue row files (sorted by file_id)."""
    rows_dir = output_dir / ROWS_DIR
    if not rows_dir.exists():
        # No rows written yet, produce empty file
        _atomic_write_text(output_dir / "scored.jsonl", "")
        return

    row_files = sorted(rows_dir.glob("*.json"), key=lambda p: p.stem)
    lines: list[str] = []
    for path in row_files:
        row = json.loads(path.read_text(encoding="utf-8"))
        lines.append(json.dumps(row, ensure_ascii=False, sort_keys=True))

    _atomic_write_text(output_dir / "scored.jsonl", "\n".join(lines) + ("\n" if lines else ""))


def write_run_manifest(output_dir: Path, manifest: dict[str, Any]) -> None:
    _atomic_write_text(
        output_dir / "run_manifest.json",
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
    )
