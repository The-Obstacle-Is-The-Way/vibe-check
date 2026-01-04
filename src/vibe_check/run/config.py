"""Run configuration models for batch execution (SPEC-06)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from vibe_check.graph.single_dialogue import DialogueViewName


@dataclass(frozen=True)
class RunConfig:
    input_path: Path
    output_dir: Path
    checkpoint_db: str
    prompt_version: str
    dialogue_view: DialogueViewName = "client_qa"
    limit: int | None = None
    max_concurrency: int = 1
    fail_fast: bool = False
    force: bool = False

    # LangGraph execution
    graph_recursion_limit: int = 25

    # Aggregation parameters
    dirichlet_alpha: float = 0.5
    disagreement_range_threshold: int = 2
    arbitration_total_std_threshold: float = 2.0
    arbitration_max_prob_threshold: float = 0.60
    arbitration_entropy_threshold: float = 1.2
    clinical_ambiguity_band_low: float = 0.4
    clinical_ambiguity_band_high: float = 0.6
    insufficient_evidence_threshold: int = 2

    # LLM inference settings (for audit trail; applied when building live agents)
    llm_temperature: float | None = None
    llm_top_p: float | None = None
    llm_max_tokens: int | None = None
    llm_timeout: float | None = None
    llm_seed: int | None = None
