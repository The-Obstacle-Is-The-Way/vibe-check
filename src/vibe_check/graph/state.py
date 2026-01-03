"""LangGraph state definitions for the scoring pipeline."""

from __future__ import annotations

import operator
from typing import Annotated, Literal, TypedDict

from vibe_check.schemas.output import AggregatedPHQ8  # noqa: TC001
from vibe_check.schemas.scoring import PHQ8Report  # noqa: TC001


class ScoringState(TypedDict):
    """State for a single-dialogue scoring workflow."""

    # Identity
    file_id: str
    condition: Literal["mdd", "control"]
    prompt_version: str

    # Data (Safe to checkpoint for synthetic data)
    dialogue: str
    scoring_text: str  # The specific view used for scoring (e.g. client_qa)

    # Accumulated results
    # operator.add allows multiple parallel jury nodes to append to this list
    jury_results: Annotated[list[PHQ8Report], operator.add]

    # Control flow
    needs_arbitration: bool

    # Final output
    final_output: AggregatedPHQ8 | None


class BatchState(TypedDict):
    """State for the batch map-reduce workflow."""

    file_ids: list[str]
    completed: Annotated[list[AggregatedPHQ8], operator.add]
