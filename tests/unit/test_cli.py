from __future__ import annotations

from vibe_check.cli import build_parser


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
