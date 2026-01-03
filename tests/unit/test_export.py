from __future__ import annotations

import json
from typing import TYPE_CHECKING

from tests.fixtures.sample_votes import create_mock_report

from vibe_check.aggregation.aggregate import aggregate_reports
from vibe_check.run.export import write_row, write_scored_jsonl

if TYPE_CHECKING:
    from pathlib import Path


def test_export_jsonl_is_sorted_by_file_id(tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    a = aggregate_reports(
        [create_mock_report(i) for i in range(6)],
        file_id="a",
        condition="mdd",
        prompt_version="v1",
    )
    b = aggregate_reports(
        [create_mock_report(i) for i in range(6)],
        file_id="b",
        condition="control",
        prompt_version="v1",
    )

    write_row(out_dir, b.model_dump(mode="json"))
    write_row(out_dir, a.model_dump(mode="json"))

    write_scored_jsonl(out_dir)
    lines = (out_dir / "scored.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    first = json.loads(lines[0])
    second = json.loads(lines[1])
    assert first["file_id"] == "a"
    assert second["file_id"] == "b"
