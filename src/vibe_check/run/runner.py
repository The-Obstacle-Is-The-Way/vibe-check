"""Batch runner for corpus-scale scoring (SPEC-06)."""

from __future__ import annotations

import asyncio
import hashlib
import json
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Any

from vibe_check.constants import phq8_rubric_hash
from vibe_check.data import load_corpus, preprocess_dialogue
from vibe_check.graph.single_dialogue import (
    build_single_dialogue_graph,
    invoke_with_checkpoint_resume,
)
from vibe_check.run.export import (
    compute_arbitration_rate_from_rows,
    write_row,
    write_run_manifest,
    write_scored_jsonl,
)
from vibe_check.run.ledger import JobLedger
from vibe_check.schemas.scoring import TokenUsage
from vibe_check.sqlite import open_async_sqlite_saver, sqlite_path_from_conn_string

if TYPE_CHECKING:
    from collections.abc import Sequence

    from vibe_check.graph.single_dialogue import JudgeItemFn, Juror
    from vibe_check.graph.state import ScoringState
    from vibe_check.run.config import RunConfig


def score_corpus(
    *,
    config: RunConfig,
    jurors: Sequence[Juror],
    judge_item: JudgeItemFn,
) -> None:
    """Score a corpus and write outputs to disk, safe to resume."""
    asyncio.run(score_corpus_async(config=config, jurors=jurors, judge_item=judge_item))


async def score_corpus_async(
    *,
    config: RunConfig,
    jurors: Sequence[Juror],
    judge_item: JudgeItemFn,
) -> None:
    """Async batch runner implementation for corpus-scale scoring."""
    input_path = config.input_path
    output_dir = config.output_dir
    checkpoint_db = config.checkpoint_db
    prompt_version = config.prompt_version
    dialogue_view = config.dialogue_view
    limit = config.limit
    max_concurrency = config.max_concurrency
    fail_fast = config.fail_fast
    force = config.force

    dirichlet_alpha = config.dirichlet_alpha
    disagreement_range_threshold = config.disagreement_range_threshold
    arbitration_total_std_threshold = config.arbitration_total_std_threshold
    arbitration_max_prob_threshold = config.arbitration_max_prob_threshold
    arbitration_entropy_threshold = config.arbitration_entropy_threshold
    clinical_ambiguity_band_low = config.clinical_ambiguity_band_low
    clinical_ambiguity_band_high = config.clinical_ambiguity_band_high
    insufficient_evidence_threshold = config.insufficient_evidence_threshold

    if max_concurrency < 1:
        raise ValueError("max_concurrency must be >= 1")

    output_dir.mkdir(parents=True, exist_ok=True)

    corpus_full = load_corpus(input_path)
    dataset_file_ids = sorted(d.file_id for d in corpus_full)
    dataset_fingerprint = hashlib.sha256("\n".join(dataset_file_ids).encode("utf-8")).hexdigest()

    corpus = corpus_full
    if limit is not None:
        corpus = corpus[:limit]

    run_config = {
        "input_path": str(Path(input_path).resolve()),
        "checkpoint_db": str(checkpoint_db),
        "dataset_fingerprint": dataset_fingerprint,
        "limit": limit,
        "prompt_version": prompt_version,
        "phq8_rubric_hash": phq8_rubric_hash(),
        "dialogue_view": dialogue_view,
        "max_concurrency": max_concurrency,
        "graph_recursion_limit": int(config.graph_recursion_limit),
        "dirichlet_alpha": dirichlet_alpha,
        "disagreement_range_threshold": disagreement_range_threshold,
        "arbitration_total_std_threshold": arbitration_total_std_threshold,
        "arbitration_max_prob_threshold": arbitration_max_prob_threshold,
        "arbitration_entropy_threshold": arbitration_entropy_threshold,
        "clinical_ambiguity_band_low": clinical_ambiguity_band_low,
        "clinical_ambiguity_band_high": clinical_ambiguity_band_high,
        "insufficient_evidence_threshold": insufficient_evidence_threshold,
        "llm_temperature": config.llm_temperature,
        "llm_top_p": config.llm_top_p,
        "llm_max_tokens": config.llm_max_tokens,
        "llm_timeout": config.llm_timeout,
        "llm_seed": config.llm_seed,
        "jurors": [
            {
                "class": j.__class__.__name__,
                "model_id": getattr(j, "model_id", None),
                "run_number": getattr(j, "run_number", None),
            }
            for j in jurors
        ],
        "judge_item": {
            "module": getattr(judge_item, "__module__", None),
            "name": getattr(judge_item, "__name__", None),
            "class": judge_item.__class__.__name__,
        },
    }
    run_config_json = json.dumps(run_config, sort_keys=True, separators=(",", ":"))
    run_fingerprint = hashlib.sha256(run_config_json.encode("utf-8")).hexdigest()

    # Initialize graph and checkpointing
    graph = build_single_dialogue_graph(
        jurors=jurors,
        judge_item=judge_item,
        dirichlet_alpha=dirichlet_alpha,
        disagreement_range_threshold=disagreement_range_threshold,
        arbitration_total_std_threshold=arbitration_total_std_threshold,
        arbitration_max_prob_threshold=arbitration_max_prob_threshold,
        arbitration_entropy_threshold=arbitration_entropy_threshold,
        clinical_ambiguity_band=(clinical_ambiguity_band_low, clinical_ambiguity_band_high),
        insufficient_evidence_threshold=insufficient_evidence_threshold,
    )

    checkpoint_path = sqlite_path_from_conn_string(checkpoint_db)
    if checkpoint_path != Path(":memory:"):
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)

    condition_counts: dict[str, int] = {"mdd": 0, "control": 0}
    split_counts: dict[str, int] = {"train": 0, "dev": 0, "test": 0}
    for dialogue in corpus:
        condition_counts[dialogue.condition] = condition_counts.get(dialogue.condition, 0) + 1
        split = dialogue.computed_split
        if split is None:
            raise ValueError(f"computed_split missing for {dialogue.file_id}")
        split_counts[split] = split_counts.get(split, 0) + 1

    ledger_path = output_dir / "ledger.sqlite"

    def _reset_paths() -> None:
        rows_dir = output_dir / "rows"
        if rows_dir.exists():
            shutil.rmtree(rows_dir)
        for path in (
            ledger_path,
            output_dir / "scored.jsonl",
            output_dir / "run_manifest.json",
        ):
            if path.exists():
                path.unlink()
        for suffix in (".sqlite-wal", ".sqlite-shm", "-wal", "-shm"):
            p = Path(str(checkpoint_path) + suffix)
            if p.exists():
                p.unlink()
        if checkpoint_path.exists() and checkpoint_path != Path(":memory:"):
            checkpoint_path.unlink()

    # Use Ledger context manager for persistent connection
    while True:
        with JobLedger(ledger_path) as ledger:
            try:
                ledger.ensure_run_config(
                    fingerprint=run_fingerprint,
                    config_json=run_config_json,
                )
            except ValueError as e:
                if not force:
                    raise ValueError(
                        "run configuration mismatch (use a new --output/--checkpoint or pass --force to reset)"
                    ) from e
            else:
                break

        _reset_paths()
        force = False

    with JobLedger(ledger_path) as ledger:
        ledger.initialize([d.file_id for d in corpus])
        ledger.reset_running_items()

        async with open_async_sqlite_saver(checkpoint_path) as saver:
            app = graph.compile(checkpointer=saver)

            dialogues_to_score = [d for d in corpus if ledger.get_status(d.file_id) != "done"]
            worker_count = (
                min(max_concurrency, len(dialogues_to_score)) if dialogues_to_score else 0
            )

            async def process_dialogue(dialogue: Any) -> None:
                ledger.mark_running(dialogue.file_id)
                try:
                    views = preprocess_dialogue(dialogue)
                    scoring_text = (
                        views.client_qa_text
                        if dialogue_view == "client_qa"
                        else views.client_only_text
                    )
                    initial_state: ScoringState = {
                        "file_id": dialogue.file_id,
                        "condition": dialogue.condition,
                        "dialogue": dialogue.dialogue,
                        "scoring_text": scoring_text,
                        "prompt_version": prompt_version,
                        "jury_results": [],
                        "needs_arbitration": False,
                        "final_output": None,
                    }

                    final_state = await invoke_with_checkpoint_resume(
                        app,
                        checkpointer=saver,
                        initial_state=initial_state,
                        thread_id=dialogue.file_id,
                        graph_max_concurrency=max(len(jurors), 1),
                        recursion_limit=int(config.graph_recursion_limit),
                    )
                    result = final_state["final_output"]
                    if result is None:
                        raise RuntimeError("graph completed without final_output")

                    # Aggregate tokens for this specific job
                    t_input = 0
                    t_output = 0
                    t_reasoning = 0
                    t_total = 0

                    for report in result.juror_reports:
                        if report.usage:
                            t_input += report.usage.input_tokens or 0
                            t_output += report.usage.output_tokens or 0
                            t_reasoning += report.usage.reasoning_tokens or 0
                            t_total += report.usage.total_tokens or 0
                    if result.judge_usage:
                        t_input += result.judge_usage.input_tokens or 0
                        t_output += result.judge_usage.output_tokens or 0
                        t_reasoning += result.judge_usage.reasoning_tokens or 0
                        t_total += result.judge_usage.total_tokens or 0

                    job_tokens = TokenUsage(
                        input_tokens=t_input,
                        output_tokens=t_output,
                        reasoning_tokens=t_reasoning,
                        total_tokens=t_total,
                    )

                    row: dict[str, Any] = result.model_dump(mode="json")
                    row["computed_split"] = dialogue.computed_split
                    row["dialogue_view"] = dialogue_view
                    row["scoring_text"] = scoring_text
                    row["truncated_utterance_count"] = int(views.truncated_utterance_count)
                    row["meta_text_removed_count"] = int(views.meta_text_removed_count)
                    row["unknown_speaker_count"] = int(views.unknown_speaker_count)
                    row["orphan_line_count"] = int(views.orphan_line_count)
                    write_row(output_dir, row)

                    ledger.mark_done(dialogue.file_id, token_usage=job_tokens)

                except Exception as e:
                    ledger.mark_failed(
                        dialogue.file_id, error_code=type(e).__name__, error_message=str(e)
                    )
                    if fail_fast:
                        raise

            if worker_count:
                queue: asyncio.Queue[Any] = asyncio.Queue()
                for dialogue in dialogues_to_score:
                    queue.put_nowait(dialogue)
                for _ in range(worker_count):
                    queue.put_nowait(None)

                async def worker() -> None:
                    while True:
                        dialogue = await queue.get()
                        try:
                            if dialogue is None:
                                return
                            await process_dialogue(dialogue)
                        finally:
                            queue.task_done()

                async with asyncio.TaskGroup() as tg:
                    for _ in range(worker_count):
                        tg.create_task(worker())

                await queue.join()

            # After loop, generate manifest using aggregated data from Ledger
            write_scored_jsonl(output_dir)

            aggregated_tokens = ledger.get_aggregated_tokens()
            arbitrated_count, row_count = compute_arbitration_rate_from_rows(output_dir)

            completed = sum(1 for fid in ledger.list_all() if ledger.get_status(fid) == "done")

            manifest: dict[str, Any] = {
                "dialogues_total": len(corpus),
                "completed": completed,
                "failed": sum(1 for fid in ledger.list_all() if ledger.get_status(fid) == "failed"),
                "arbitration_rate": (arbitrated_count / completed) if completed else 0.0,
                "rows_written": row_count,
                "arbitrated_dialogues": arbitrated_count,
                "counts_by_condition": condition_counts,
                "counts_by_split": split_counts,
                "token_usage_totals": aggregated_tokens,
                "run_fingerprint": run_fingerprint,
                "phq8_rubric_hash": run_config["phq8_rubric_hash"],
                "run_config": run_config,
            }
            write_run_manifest(output_dir, manifest)
