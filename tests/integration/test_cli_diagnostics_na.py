from __future__ import annotations

import json
from typing import TYPE_CHECKING

from vibe_check.cli import main

if TYPE_CHECKING:
    from pathlib import Path


def test_cli_diagnostics_with_na(tmp_path: Path) -> None:
    scored = tmp_path / "scored.jsonl"
    output = tmp_path / "report.json"

    from tests.unit.utils import make_minimal_aggregated_phq8_na

    rows = [
        make_minimal_aggregated_phq8_na(
            file_id="m1", condition="mdd", na_items={"fatigue"}, base_score=2
        ),
        make_minimal_aggregated_phq8_na(
            file_id="m2", condition="mdd", na_items=set(), base_score=2
        ),
        make_minimal_aggregated_phq8_na(
            file_id="c1", condition="control", na_items={"sleep"}, base_score=0
        ),
        make_minimal_aggregated_phq8_na(
            file_id="c2", condition="control", na_items=set(), base_score=0
        ),
    ]

    lines: list[str] = []
    for r in rows:
        row = r.model_dump(mode="json")
        row["computed_split"] = "train"
        row["scoring_text"] = "Client: ..."
        row["dialogue_view"] = "client_qa"
        lines.append(json.dumps(row))

    scored.write_text("\n".join(lines) + "\n", encoding="utf-8")

    rc = main(["diagnostics", "--scored", str(scored), "--output", str(output), "--format", "json"])
    assert rc == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert "coverage" in payload
    assert "assertion_distribution" in payload
