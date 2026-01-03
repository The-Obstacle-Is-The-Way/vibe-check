from __future__ import annotations

from vibe_check.cli import build_parser


def test_cli_parses_score_corpus_args() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "score-corpus",
            "--input",
            "data/sqpsychconv/qwq",
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
