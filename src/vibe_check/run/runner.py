"""Batch runner for corpus-scale scoring (SPEC-06)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, Any

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

    from vibe_check.graph.single_dialogue import DialogueViewName, JudgeItemFn, Juror
    from vibe_check.graph.state import ScoringState


def score_corpus(
    *,
    input_path: str | Path,
    output_dir: Path,
    checkpoint_db: str,
    jurors: Sequence[Juror],
    judge_item: JudgeItemFn,
    limit: int | None = None,
    prompt_version: str,
    dialogue_view: DialogueViewName = "client_qa",
    max_concurrency: int = 1,
    fail_fast: bool = False,
    dirichlet_alpha: float = 0.5,
    arbitration_total_std_threshold: float = 2.0,
    arbitration_max_prob_threshold: float = 0.60,
    arbitration_entropy_threshold: float = 1.2,
) -> None:
    """Score a corpus and write outputs to disk, safe to resume."""
    asyncio.run(
        score_corpus_async(
            input_path=input_path,
            output_dir=output_dir,
            checkpoint_db=checkpoint_db,
            jurors=jurors,
            judge_item=judge_item,
            limit=limit,
            prompt_version=prompt_version,
            dialogue_view=dialogue_view,
            max_concurrency=max_concurrency,
            fail_fast=fail_fast,
            dirichlet_alpha=dirichlet_alpha,
            arbitration_total_std_threshold=arbitration_total_std_threshold,
            arbitration_max_prob_threshold=arbitration_max_prob_threshold,
            arbitration_entropy_threshold=arbitration_entropy_threshold,
        )
    )


async def score_corpus_async(
    *,
    input_path: str | Path,
    output_dir: Path,
    checkpoint_db: str,
    jurors: Sequence[Juror],
    judge_item: JudgeItemFn,
    limit: int | None = None,
    prompt_version: str,
    dialogue_view: DialogueViewName = "client_qa",
    max_concurrency: int = 1,
    fail_fast: bool = False,
    dirichlet_alpha: float = 0.5,
    arbitration_total_std_threshold: float = 2.0,
    arbitration_max_prob_threshold: float = 0.60,
    arbitration_entropy_threshold: float = 1.2,
) -> None:
    """Async batch runner implementation for corpus-scale scoring."""
    if max_concurrency < 1:
        raise ValueError("max_concurrency must be >= 1")

    output_dir.mkdir(parents=True, exist_ok=True)

    corpus = load_corpus(input_path)
    if limit is not None:
        corpus = corpus[:limit]

    # Initialize graph and checkpointing
    graph = build_single_dialogue_graph(
        jurors=jurors,
        judge_item=judge_item,
        dirichlet_alpha=dirichlet_alpha,
        arbitration_total_std_threshold=arbitration_total_std_threshold,
        arbitration_max_prob_threshold=arbitration_max_prob_threshold,
        arbitration_entropy_threshold=arbitration_entropy_threshold,
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

    # Use Ledger context manager for persistent connection
    with JobLedger(output_dir / "ledger.sqlite") as ledger:
        ledger.initialize([d.file_id for d in corpus])
        reset_count = ledger.reset_running_items()
        if reset_count > 0:
            # We don't have a logger here yet, but it's fine.
            # Could print or just rely on the fact it's handled.
            pass

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
                        max_concurrency=max_concurrency,
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
            }
            write_run_manifest(output_dir, manifest)
