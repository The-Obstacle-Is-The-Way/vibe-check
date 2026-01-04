"""LangGraph workflow for scoring a single dialogue end-to-end (SPEC-05)."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING, Any, Literal, Protocol, cast

from langgraph.graph import END, START, StateGraph

from vibe_check.aggregation.aggregate import aggregate_reports, get_severity_bucket
from vibe_check.constants import PHQ8_ITEMS
from vibe_check.data import load_corpus, preprocess_dialogue
from vibe_check.graph.state import ScoringState
from vibe_check.judge.schema import JudgeItemReport
from vibe_check.schemas.scoring import PHQ8Report, TokenUsage

if TYPE_CHECKING:
    from pathlib import Path

    from vibe_check.schemas.output import AggregatedPHQ8


class Juror(Protocol):
    def score(self, scoring_text: str) -> PHQ8Report: ...
    async def ascore(self, scoring_text: str) -> PHQ8Report: ...


JudgeItemFn = Callable[[str, str, list[PHQ8Report], str], JudgeItemReport]

DialogueViewName = Literal["client_qa", "client_only"]


def build_single_dialogue_graph(
    *,
    jurors: Sequence[Juror],
    judge_item: JudgeItemFn,
    dirichlet_alpha: float = 0.5,
    disagreement_range_threshold: int = 2,
    arbitration_total_std_threshold: float = 2.0,
    arbitration_max_prob_threshold: float = 0.60,
    arbitration_entropy_threshold: float = 1.2,
    clinical_ambiguity_band: tuple[float, float] = (0.4, 0.6),
    insufficient_evidence_threshold: int = 2,
) -> StateGraph[ScoringState, None, ScoringState, ScoringState]:
    """Build the single-dialogue jury→aggregate→(optional)judge graph."""
    graph: StateGraph[ScoringState, None, ScoringState, ScoringState] = StateGraph(ScoringState)

    def make_juror_node(juror: Juror) -> Callable[[ScoringState], Any]:
        async def node(state: ScoringState) -> dict[str, Any]:
            report = await juror.ascore(state["scoring_text"])
            return {"jury_results": [report]}

        return node

    juror_node_names: list[str] = []
    for idx, juror in enumerate(jurors, start=1):
        node_name = f"juror_{idx}"
        graph.add_node(
            node_name,
            cast("Any", make_juror_node(juror)),
            input_schema=ScoringState,
        )
        graph.add_edge(START, node_name)
        juror_node_names.append(node_name)

    def aggregate_node(state: ScoringState) -> dict[str, Any]:
        reports = sorted(state["jury_results"], key=lambda r: (r.model_id, r.run_number))
        agg = aggregate_reports(
            reports,
            file_id=state["file_id"],
            condition=state["condition"],
            prompt_version=state["prompt_version"],
            dirichlet_alpha=dirichlet_alpha,
            disagreement_range_threshold=disagreement_range_threshold,
            arbitration_total_std_threshold=arbitration_total_std_threshold,
            arbitration_max_prob_threshold=arbitration_max_prob_threshold,
            arbitration_entropy_threshold=arbitration_entropy_threshold,
            clinical_ambiguity_band=clinical_ambiguity_band,
            insufficient_evidence_threshold=insufficient_evidence_threshold,
        )
        return {"final_output": agg, "needs_arbitration": agg.triggered_arbitration}

    graph.add_node("aggregate", aggregate_node, input_schema=ScoringState)
    if juror_node_names:
        for node_name in juror_node_names:
            graph.add_edge(node_name, "aggregate")
    else:
        graph.add_edge(START, "aggregate")

    def route_after_aggregate(state: ScoringState) -> str:
        return "arbitrate" if state["needs_arbitration"] else END

    def arbitrate_node(state: ScoringState) -> dict[str, Any]:
        agg = state["final_output"]
        if agg is None:
            raise RuntimeError("aggregate node did not produce final_output")

        contested = [item for item in agg.arbitration_items if item in PHQ8_ITEMS]
        if "__total__" in agg.arbitration_items:
            contested = list(PHQ8_ITEMS)

        if not contested:
            return {"final_output": agg, "needs_arbitration": False}

        resolutions: dict[str, JudgeItemReport] = {}
        for item in contested:
            resolutions[item] = judge_item(
                state["scoring_text"],
                item,
                agg.juror_reports,
                state["prompt_version"],
            )

        t_input = 0
        t_output = 0
        t_reasoning = 0
        t_total = 0
        for resolution in resolutions.values():
            if resolution.usage:
                t_input += resolution.usage.input_tokens or 0
                t_output += resolution.usage.output_tokens or 0
                t_reasoning += resolution.usage.reasoning_tokens or 0
                t_total += resolution.usage.total_tokens or 0
        judge_usage = (
            TokenUsage(
                input_tokens=t_input,
                output_tokens=t_output,
                reasoning_tokens=t_reasoning,
                total_tokens=t_total,
            )
            if (t_input or t_output or t_reasoning or t_total)
            else None
        )

        final_item_scores = dict(agg.final_item_scores)
        for item, resolution in resolutions.items():
            final_item_scores[item] = int(resolution.final_score)

        final_total_score = sum(final_item_scores.values())
        updated: AggregatedPHQ8 = agg.model_copy(
            update={
                "final_item_scores": final_item_scores,
                "final_total_score": final_total_score,
                "final_severity_bucket": get_severity_bucket(final_total_score),
                "final_source": "judge_override",
                "judge_resolution": {k: v.model_dump() for k, v in resolutions.items()},
                "judge_usage": judge_usage,
            }
        )
        return {"final_output": updated, "needs_arbitration": False}

    graph.add_node("arbitrate", arbitrate_node, input_schema=ScoringState)
    graph.add_conditional_edges("aggregate", route_after_aggregate)
    graph.add_edge("arbitrate", END)

    return graph


async def invoke_with_checkpoint_resume(
    app: Any,
    *,
    checkpointer: Any,
    initial_state: ScoringState,
    thread_id: str,
    graph_max_concurrency: int | None = None,
) -> ScoringState:
    """Invoke a compiled LangGraph app asynchronously, resuming from checkpoint when present."""
    config: dict[str, Any] = {"configurable": {"thread_id": thread_id}}
    if graph_max_concurrency is not None:
        config["max_concurrency"] = graph_max_concurrency
    has_checkpoint = await checkpointer.aget_tuple(config) is not None
    input_state: Any = None if has_checkpoint else initial_state
    out = await app.ainvoke(input_state, config=config)
    return cast("ScoringState", out)


def score_one_dialogue(
    *,
    file_id: str,
    corpus_dir: str | Path,
    prompt_version: str,
    checkpoint_db: str,
    jurors: Sequence[Juror],
    judge_item: JudgeItemFn,
    dialogue_view: DialogueViewName = "client_qa",
    graph_max_concurrency: int | None = None,
) -> AggregatedPHQ8:
    """Score one dialogue end-to-end with checkpoint/resume enabled."""
    return asyncio.run(
        score_one_dialogue_async(
            file_id=file_id,
            corpus_dir=corpus_dir,
            prompt_version=prompt_version,
            checkpoint_db=checkpoint_db,
            jurors=jurors,
            judge_item=judge_item,
            dialogue_view=dialogue_view,
            graph_max_concurrency=graph_max_concurrency,
        )
    )


async def score_one_dialogue_async(
    *,
    file_id: str,
    corpus_dir: str | Path,
    prompt_version: str,
    checkpoint_db: str,
    jurors: Sequence[Juror],
    judge_item: JudgeItemFn,
    dialogue_view: DialogueViewName = "client_qa",
    graph_max_concurrency: int | None = None,
) -> AggregatedPHQ8:
    """Async scoring for one dialogue with checkpoint/resume enabled."""
    corpus = load_corpus(corpus_dir)
    dialogue = next((d for d in corpus if d.file_id == file_id), None)
    if dialogue is None:
        raise KeyError(f"file_id not found in corpus: {file_id}")

    views = preprocess_dialogue(dialogue)
    scoring_text = views.client_qa_text if dialogue_view == "client_qa" else views.client_only_text

    initial_state: ScoringState = {
        "file_id": file_id,
        "condition": dialogue.condition,
        "dialogue": dialogue.dialogue,
        "scoring_text": scoring_text,
        "prompt_version": prompt_version,
        "jury_results": [],
        "needs_arbitration": False,
        "final_output": None,
    }

    graph = build_single_dialogue_graph(jurors=jurors, judge_item=judge_item)

    from vibe_check.sqlite import sqlite_path_from_conn_string

    checkpoint_path = sqlite_path_from_conn_string(checkpoint_db)
    if str(checkpoint_path) != ":memory:":
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)

    from vibe_check.sqlite import open_async_sqlite_saver

    effective_graph_max_concurrency = graph_max_concurrency
    if effective_graph_max_concurrency is None:
        effective_graph_max_concurrency = max(len(jurors), 1)

    async with open_async_sqlite_saver(checkpoint_path) as saver:
        app = graph.compile(checkpointer=saver)
        final_state = await invoke_with_checkpoint_resume(
            app,
            checkpointer=saver,
            initial_state=initial_state,
            thread_id=file_id,
            graph_max_concurrency=effective_graph_max_concurrency,
        )

    final = final_state["final_output"]
    if final is None:
        raise RuntimeError("graph completed without producing final_output")
    return final
