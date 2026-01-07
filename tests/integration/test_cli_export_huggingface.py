from __future__ import annotations

import json
from typing import TYPE_CHECKING

from vibe_check.cli import main

if TYPE_CHECKING:
    from pathlib import Path


def test_cli_export_huggingface_only(tmp_path: Path) -> None:
    scored = tmp_path / "scored.jsonl"
    exports_dir = tmp_path / "exports"

    from tests.unit.utils import make_minimal_aggregated_phq8_na

    row = make_minimal_aggregated_phq8_na(file_id="active001").model_dump(mode="json")
    row["computed_split"] = "train"
    scored.write_text(json.dumps(row) + "\n", encoding="utf-8")

    rc = main(
        [
            "export",
            "--input",
            str(scored),
            "--output-dir",
            str(exports_dir),
            "--format",
            "huggingface",
        ]
    )
    assert rc == 0
    assert (exports_dir / "vibe_check_labels_huggingface.jsonl").exists()
    assert not (exports_dir / "vibe_check_labels.jsonl").exists()


def test_cli_export_all_formats(tmp_path: Path) -> None:
    scored = tmp_path / "scored.jsonl"
    exports_dir = tmp_path / "exports"

    from tests.unit.utils import make_minimal_aggregated_phq8_na

    row = make_minimal_aggregated_phq8_na(file_id="active001").model_dump(mode="json")
    row["computed_split"] = "dev"
    row["scoring_text"] = "Client: ..."
    row["dialogue_view"] = "client_qa"
    scored.write_text(json.dumps(row) + "\n", encoding="utf-8")

    rc = main(
        [
            "export",
            "--input",
            str(scored),
            "--output-dir",
            str(exports_dir),
            "--format",
            "jsonl,csv,huggingface",
        ]
    )
    assert rc == 0
    assert (exports_dir / "vibe_check_labels.jsonl").exists()
    assert (exports_dir / "vibe_check_labels.csv").exists()
    assert (exports_dir / "vibe_check_labels_huggingface.jsonl").exists()
