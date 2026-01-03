"""Batch runner for corpus-scale scoring (SPEC-06)."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from vibe_check.data import load_corpus, preprocess_dialogue
from vibe_check.graph.single_dialogue import (
    build_single_dialogue_graph,
    invoke_with_checkpoint_resume,
)
from vibe_check.run.export import write_row, write_run_manifest, write_scored_jsonl
from vibe_check.run.ledger import JobLedger
from vibe_check.sqlite import sqlite_path_from_conn_string

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
) -> None:
    """Score a corpus and write outputs to disk, safe to resume."""
    output_dir.mkdir(parents=True, exist_ok=True)

    corpus = load_corpus(input_path)
    if limit is not None:
        corpus = corpus[:limit]

    ledger = JobLedger(output_dir / "ledger.sqlite")
    ledger.initialize([d.file_id for d in corpus])

    graph = build_single_dialogue_graph(jurors=jurors, judge_item=judge_item)

    from langgraph.checkpoint.sqlite import SqliteSaver

    checkpoint_path = sqlite_path_from_conn_string(checkpoint_db)
    if checkpoint_path != Path(":memory:"):
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)

    condition_counts: dict[str, int] = {"mdd": 0, "control": 0}
    split_counts: dict[str, int] = {"train": 0, "dev": 0, "test": 0}
    arbitration_count = 0
    token_totals: dict[str, int] = {
        "input_tokens": 0,
        "output_tokens": 0,
        "reasoning_tokens": 0,
        "total_tokens": 0,
    }

    with SqliteSaver.from_conn_string(str(checkpoint_path)) as saver:
        app = graph.compile(checkpointer=saver)

        for dialogue in corpus:
            condition_counts[dialogue.condition] = condition_counts.get(dialogue.condition, 0) + 1
            split = dialogue.computed_split
            if split is None:
                raise ValueError(f"computed_split missing for {dialogue.file_id}")
            split_counts[split] = split_counts.get(split, 0) + 1

            if ledger.get_status(dialogue.file_id) == "done":
                continue

            ledger.mark_running(dialogue.file_id)
            try:
                views = preprocess_dialogue(dialogue)
                scoring_text = (
                    views.client_qa_text if dialogue_view == "client_qa" else views.client_only_text
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

                final_state = invoke_with_checkpoint_resume(
                    app,
                    checkpointer=saver,
                    initial_state=initial_state,
                    thread_id=dialogue.file_id,
                    max_concurrency=max_concurrency,
                )
                result = final_state["final_output"]
                if result is None:
                    raise RuntimeError("graph completed without final_output")

                arbitration_count += 1 if result.triggered_arbitration else 0
                for report in result.juror_reports:
                    if report.usage is None:
                        continue
                    if report.usage.input_tokens is not None:
                        token_totals["input_tokens"] += report.usage.input_tokens
                    if report.usage.output_tokens is not None:
                        token_totals["output_tokens"] += report.usage.output_tokens
                    if report.usage.reasoning_tokens is not None:
                        token_totals["reasoning_tokens"] += report.usage.reasoning_tokens
                    if report.usage.total_tokens is not None:
                        token_totals["total_tokens"] += report.usage.total_tokens

                row: dict[str, Any] = result.model_dump(mode="json")
                row["computed_split"] = dialogue.computed_split
                row["dialogue_view"] = dialogue_view
                write_row(output_dir, row)
                ledger.mark_done(dialogue.file_id)
            except Exception as e:
                ledger.mark_failed(
                    dialogue.file_id, error_code=type(e).__name__, error_message=str(e)
                )
                if fail_fast:
                    raise
                continue

    write_scored_jsonl(output_dir)

    manifest: dict[str, Any] = {
        "dialogues_total": len(corpus),
        "completed": sum(1 for fid in ledger.list_all() if ledger.get_status(fid) == "done"),
        "failed": sum(1 for fid in ledger.list_all() if ledger.get_status(fid) == "failed"),
        "arbitration_rate": (arbitration_count / len(corpus)) if corpus else 0.0,
        "counts_by_condition": condition_counts,
        "counts_by_split": split_counts,
        "token_usage_totals": token_totals,
    }
    write_run_manifest(output_dir, manifest)
