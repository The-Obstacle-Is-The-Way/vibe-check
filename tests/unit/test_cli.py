from __future__ import annotations

import os
from typing import TYPE_CHECKING

from vibe_check.cli import build_parser

if TYPE_CHECKING:
    from pathlib import Path

    from _pytest.monkeypatch import MonkeyPatch


def test_cli_parses_score_corpus_args() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "score-corpus",
            "--input",
            "data/sqpsychconv/qwen-2.5",
            "--checkpoint",
            "sqlite:///tmp/checkpoints.db",
            "--output",
            "data/outputs/dev_run",
            "--limit",
            "5",
        ]
    )
    assert args.command == "score-corpus"
    assert args.limit == 5
    assert args.live is False


def test_cli_parses_force_flag() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "score-corpus",
            "--input",
            "data/sqpsychconv/qwen-2.5",
            "--checkpoint",
            "sqlite:///tmp/checkpoints.db",
            "--output",
            "data/outputs/dev_run",
            "--force",
        ]
    )
    assert args.command == "score-corpus"
    assert args.force is True


def test_cli_export_provider_api_keys_sets_gemini_env(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    from vibe_check.cli import export_provider_api_keys
    from vibe_check.settings import Settings

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    settings = Settings(google_api_key="test-google")
    export_provider_api_keys(settings)

    assert os.environ["GOOGLE_API_KEY"] == "test-google"
    assert os.environ["GEMINI_API_KEY"] == "test-google"


def test_cli_parses_diagnostics_args() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "diagnostics",
            "--scored",
            "data/outputs/run/scored.jsonl",
            "--output",
            "data/outputs/run/diagnostics.json",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert args.command == "diagnostics"
    assert args.format == "json"
    assert args.strict is True


def test_cli_parses_export_args() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "export",
            "--input",
            "data/outputs/run/scored.jsonl",
            "--output-dir",
            "data/outputs/run/export",
            "--format",
            "jsonl,csv",
        ]
    )
    assert args.command == "export"
    assert args.format == "jsonl,csv"


def test_cli_parses_validate_export_args() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "validate-export",
            "--input",
            "data/outputs/run/export/vibe_check_labels.jsonl",
        ]
    )
    assert args.command == "validate-export"
