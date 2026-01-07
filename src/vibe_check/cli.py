"""Command-line interface for vibe-check (SPEC-06)."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import TYPE_CHECKING, cast

from vibe_check.run.config import RunConfig
from vibe_check.run.factory import (
    build_fake_judge_item,
    build_fake_jury,
    build_real_judge_item,
    build_real_jury,
)
from vibe_check.run.runner import score_corpus
from vibe_check.settings import Settings

if TYPE_CHECKING:
    from vibe_check.graph.single_dialogue import DialogueViewName


def export_provider_api_keys(settings: Settings) -> None:
    """Export Settings API keys to env vars expected by provider SDKs."""
    # PydanticAI providers read env vars directly, not our Settings object.
    if settings.openai_api_key:
        os.environ.setdefault("OPENAI_API_KEY", settings.openai_api_key)
    if settings.anthropic_api_key:
        os.environ.setdefault("ANTHROPIC_API_KEY", settings.anthropic_api_key)
    if settings.google_api_key:
        # Some integrations still read GEMINI_API_KEY; keep it in sync with GOOGLE_API_KEY.
        os.environ.setdefault("GOOGLE_API_KEY", settings.google_api_key)
        os.environ.setdefault("GEMINI_API_KEY", settings.google_api_key)


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
        "--prompt-version",
        default="v2.0.0-clinical",
        help="Prompt version label to embed in outputs.",
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
        help=(
            "Max concurrent dialogues to process (jurors run in parallel within each dialogue; "
            "defaults to Settings.max_concurrent_dialogues)."
        ),
    )
    score.add_argument(
        "--force",
        action="store_true",
        help="Allow resetting an existing run directory/checkpoint when the run config differs.",
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
        help="Comma-separated formats to write: jsonl,csv,huggingface",
    )

    validate_export = sub.add_parser("validate-export", help="Validate a public export JSONL file.")
    validate_export.add_argument("--input", required=True, help="Path to vibe_check_labels.jsonl.")

    calibration = sub.add_parser("calibration", help="Human-in-the-loop calibration tools.")
    calibration_sub = calibration.add_subparsers(dest="calibration_command", required=True)

    sample = calibration_sub.add_parser(
        "sample",
        help="Sample dialogues from scored.jsonl for human annotation.",
    )
    sample.add_argument("--scored", required=True, help="Path to scored.jsonl.")
    sample.add_argument("--n", type=int, required=True, help="Number of dialogues to sample.")
    sample.add_argument(
        "--strategy",
        choices=["hybrid"],
        default="hybrid",
        help="Sampling strategy (currently only hybrid is supported).",
    )
    sample.add_argument("--seed", type=int, default=0, help="Seed for deterministic sampling.")
    sample.add_argument("--output", required=True, help="Path to write the CSV template.")

    evaluate = calibration_sub.add_parser(
        "evaluate",
        help="Evaluate system outputs against a human-labeled golden set CSV.",
    )
    evaluate.add_argument("--system", required=True, help="Path to system scored.jsonl.")
    evaluate.add_argument("--human", required=True, help="Path to human-labeled golden_set.csv.")
    evaluate.add_argument("--output", required=True, help="Path to write calibration_report.json.")
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
            if not str(args.prompt_version).startswith("v2"):
                parser.error(
                    "--live requires a v2.* prompt version (NA-aware schema); "
                    f"got --prompt-version={args.prompt_version!r}"
                )
            missing: list[str] = []
            if not settings.openai_api_key:
                missing.append("OPENAI_API_KEY")
            if not settings.anthropic_api_key:
                missing.append("ANTHROPIC_API_KEY")
            if not settings.google_api_key:
                missing.append("GOOGLE_API_KEY (or GEMINI_API_KEY)")

            if missing:
                parser.error(f"--live requires API keys: {', '.join(missing)}")

            export_provider_api_keys(settings)

            # BUG-027 fix: Pass CLI args to factory functions, not Settings defaults
            jurors = build_real_jury(
                settings,
                prompt_version=args.prompt_version,
                dialogue_view=args.dialogue_view,
            )
            judge_item = build_real_judge_item(
                settings,
                prompt_version=args.prompt_version,
            )
        else:
            jurors = build_fake_jury()
            judge_item = build_fake_judge_item()

        run_config = RunConfig(
            input_path=Path(args.input),
            output_dir=Path(args.output),
            checkpoint_db=str(args.checkpoint),
            prompt_version=str(args.prompt_version),
            dialogue_view=cast("DialogueViewName", args.dialogue_view),
            limit=args.limit,
            max_concurrency=max_concurrency,
            force=bool(args.force),
            graph_recursion_limit=int(settings.graph_recursion_limit),
            dirichlet_alpha=float(settings.dirichlet_alpha),
            disagreement_range_threshold=int(settings.disagreement_range_threshold),
            arbitration_total_std_threshold=float(settings.arbitration_total_std_threshold),
            arbitration_max_prob_threshold=float(settings.arbitration_max_prob_threshold),
            arbitration_entropy_threshold=float(settings.arbitration_entropy_threshold),
            clinical_ambiguity_band_low=float(settings.clinical_ambiguity_band_low),
            clinical_ambiguity_band_high=float(settings.clinical_ambiguity_band_high),
            insufficient_evidence_threshold=int(settings.insufficient_evidence_threshold),
            llm_temperature=float(settings.llm_temperature),
            llm_top_p=float(settings.llm_top_p),
            llm_max_tokens=int(settings.llm_max_tokens),
            llm_timeout=float(settings.llm_timeout),
            llm_seed=(int(settings.llm_seed) if settings.llm_seed is not None else None),
        )
        score_corpus(config=run_config, jurors=jurors, judge_item=judge_item)
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
        formats = {part.strip() for part in str(args.format).split(",") if part.strip()}

        if "huggingface" in formats:
            from vibe_check.export.huggingface import write_huggingface_export

            write_huggingface_export(
                scored_jsonl=args.input,
                output_dir=args.output_dir,
            )

        spec08_formats = formats - {"huggingface"}
        if spec08_formats:
            from vibe_check.export.writer import write_label_exports

            validation = write_label_exports(
                scored_jsonl=args.input,
                output_dir=args.output_dir,
                formats=spec08_formats,
            )
            return 0 if validation.is_valid else 2

        return 0

    if args.command == "validate-export":
        from vibe_check.export.validator import validate_label_export

        validation_report = validate_label_export(args.input)
        report_path = Path(args.input).with_name("validation_report.json")
        report_path.write_text(
            validation_report.model_dump_json(indent=2, exclude={"records"}) + "\n",
            encoding="utf-8",
        )
        return 0 if validation_report.is_valid else 2

    if args.command == "calibration":
        from vibe_check.calibration.evaluate import (
            evaluate_golden_set,
            render_confusion_matrix_table,
        )
        from vibe_check.calibration.sample import sample_for_annotation

        if args.calibration_command == "sample":
            sample_for_annotation(
                scored_jsonl=args.scored,
                n=int(args.n),
                output_csv=args.output,
                strategy=str(args.strategy),
                seed=int(args.seed),
            )
            return 0

        if args.calibration_command == "evaluate":
            calibration_report = evaluate_golden_set(
                system_scored_jsonl=args.system,
                human_csv=args.human,
            )
            Path(args.output).parent.mkdir(parents=True, exist_ok=True)
            Path(args.output).write_text(
                calibration_report.model_dump_json(indent=2) + "\n",
                encoding="utf-8",
            )
            print(render_confusion_matrix_table(calibration_report))

            # Safety gate: if we have any human positives, missing any is a hard failure.
            if calibration_report.self_harm_recall < 1.0:
                return 2
            return 0

        raise AssertionError(f"Unknown calibration command: {args.calibration_command}")

    raise AssertionError(f"Unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
