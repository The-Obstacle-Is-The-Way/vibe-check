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
        "--max-concurrency",
        type=int,
        default=None,
        help="Max concurrency for graph execution (defaults to Settings.max_concurrent_dialogues).",
    )

    diagnostics = sub.add_parser("diagnostics", help="Compute run diagnostics from scored.jsonl.")
    diagnostics.add_argument("--scored", required=True, help="Path to scored.jsonl.")
    diagnostics.add_argument("--output", required=True, help="Path to write the report.")
    diagnostics.add_argument(
        "--format",
        choices=["json", "markdown"],
        default="json",
        help="Output format for the report.",
    )
    diagnostics.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero if any quality gate fails.",
    )

    export = sub.add_parser("export", help="Export public label files from scored.jsonl.")
    export.add_argument("--input", required=True, help="Path to internal scored.jsonl.")
    export.add_argument("--output-dir", required=True, help="Directory to write export files.")
    export.add_argument(
        "--format",
        default="jsonl,csv",
        help="Comma-separated formats to write: jsonl,csv",
    )

    validate_export = sub.add_parser("validate-export", help="Validate a public export JSONL file.")
    validate_export.add_argument("--input", required=True, help="Path to vibe_check_labels.jsonl.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "score-corpus":
        settings = Settings()
        max_concurrency = (
            int(args.max_concurrency)
            if args.max_concurrency is not None
            else int(settings.max_concurrent_dialogues)
        )

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
            max_concurrency=max_concurrency,
            dirichlet_alpha=settings.dirichlet_alpha,
            arbitration_total_std_threshold=settings.arbitration_total_std_threshold,
            arbitration_max_prob_threshold=settings.arbitration_max_prob_threshold,
            arbitration_entropy_threshold=settings.arbitration_entropy_threshold,
        )
        return 0

    if args.command == "diagnostics":
        from vibe_check.diagnostics import RunDiagnostics
        from vibe_check.diagnostics.report import render_diagnostic_report_markdown

        scored_path = Path(args.scored)
        manifest_guess = scored_path.with_name("run_manifest.json")
        diagnostics = RunDiagnostics(
            scored_jsonl=scored_path,
            run_manifest=manifest_guess if manifest_guess.exists() else None,
        )
        report = diagnostics.compute()

        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if args.format == "markdown":
            output_path.write_text(render_diagnostic_report_markdown(report), encoding="utf-8")
        else:
            output_path.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")

        if args.strict and not report.passes_all_gates:
            return 2
        return 0

    if args.command == "export":
        from vibe_check.export.writer import write_label_exports

        formats = {part.strip() for part in str(args.format).split(",") if part.strip()}
        validation = write_label_exports(
            scored_jsonl=args.input,
            output_dir=args.output_dir,
            formats=formats,
        )
        return 0 if validation.is_valid else 2

    if args.command == "validate-export":
        from vibe_check.export.validator import validate_label_export

        validation_report = validate_label_export(args.input)
        report_path = Path(args.input).with_name("validation_report.json")
        report_path.write_text(
            validation_report.model_dump_json(indent=2, exclude={"records"}) + "\n",
            encoding="utf-8",
        )
        return 0 if validation_report.is_valid else 2

    raise AssertionError(f"Unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
