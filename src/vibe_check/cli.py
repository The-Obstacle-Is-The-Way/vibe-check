"""Command-line interface for vibe-check (SPEC-06)."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from vibe_check.run.factory import (
    build_fake_judge_item,
    build_fake_jury,
    build_real_judge_item,
    build_real_jury,
)
from vibe_check.run.runner import score_corpus
from vibe_check.settings import Settings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="vibe-check")
    sub = parser.add_subparsers(dest="command", required=True)

    score = sub.add_parser("score-corpus", help="Score a SQPsychConv corpus and write outputs.")
    score.add_argument("--input", required=True, help="Path to HF dataset dir or CSV.")
    score.add_argument(
        "--checkpoint", required=True, help="SQLite checkpoint DB (path or sqlite:///...)."
    )
    score.add_argument(
        "--output", required=True, help="Output directory (writes ledger + rows + JSONL)."
    )
    score.add_argument("--limit", type=int, default=None, help="Limit number of dialogues (debug).")
    score.add_argument(
        "--live",
        action="store_true",
        help="Use real provider-backed jurors/judge (requires API keys; may cost money).",
    )
    score.add_argument(
        "--prompt-version", default="v1.0.0", help="Prompt version label to embed in outputs."
    )
    score.add_argument(
        "--dialogue-view",
        choices=["client_qa", "client_only"],
        default="client_qa",
        help="Which deterministic view to score.",
    )
    score.add_argument(
        "--max-concurrency", type=int, default=1, help="Max concurrency for graph execution."
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "score-corpus":
        settings = Settings()

        if args.live:
            # Export API keys to environment for PydanticAI providers
            # (They read env vars directly, not our Settings object)
            if settings.openai_api_key:
                os.environ.setdefault("OPENAI_API_KEY", settings.openai_api_key)
            if settings.anthropic_api_key:
                os.environ.setdefault("ANTHROPIC_API_KEY", settings.anthropic_api_key)
            if settings.google_api_key:
                os.environ.setdefault("GOOGLE_API_KEY", settings.google_api_key)

            # Override prompt version from CLI if provided, though settings has it too.
            # CLI wins.
            settings.prompt_version = args.prompt_version
            jurors = build_real_jury(settings)
            judge_item = build_real_judge_item(settings)
        else:
            jurors = build_fake_jury()
            judge_item = build_fake_judge_item()

        score_corpus(
            input_path=args.input,
            output_dir=Path(args.output),
            checkpoint_db=args.checkpoint,
            jurors=jurors,
            judge_item=judge_item,
            limit=args.limit,
            prompt_version=args.prompt_version,
            dialogue_view=args.dialogue_view,
            max_concurrency=args.max_concurrency,
            dirichlet_alpha=settings.dirichlet_alpha,
            arbitration_total_std_threshold=settings.arbitration_total_std_threshold,
        )
        return 0

    raise AssertionError(f"Unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
