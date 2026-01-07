"""Coverage and NA-rate metrics for NA-aware runs (SPEC-18)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from vibe_check.constants import PHQ8_ITEMS

if TYPE_CHECKING:
    from vibe_check.schemas.output import AggregatedPHQ8


class CoverageMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    n_dialogues: int = Field(ge=0)

    total_cells: int = Field(ge=0, description="n_dialogues * 8")
    na_cells: int = Field(
        ge=0, description="Count of cells where consensus_assertion == not_mentioned"
    )
    corpus_na_rate: float = Field(ge=0.0, le=1.0, description="na_cells / total_cells")

    item_coverage: dict[str, float] = Field(description="Per-item P(discussed) across dialogues")
    min_item_coverage: float = Field(ge=0.0, le=1.0)
    max_item_coverage: float = Field(ge=0.0, le=1.0)

    dialogues_with_min_coverage: int = Field(ge=0, description="count(totals.is_min_coverage)")
    dialogues_with_proration_valid: int = Field(
        ge=0, description="count(totals.is_proration_valid)"
    )
    dialogue_coverage_mean: float = Field(ge=0.0, le=1.0)
    dialogue_coverage_std: float = Field(ge=0.0)
    coverage_histogram: dict[int, int] = Field(description="counts by discussed_count (0..8)")


def compute_coverage_metrics(rows: list[AggregatedPHQ8]) -> CoverageMetrics:
    n_dialogues = len(rows)
    total_cells = n_dialogues * len(PHQ8_ITEMS)

    item_na_counts = dict.fromkeys(PHQ8_ITEMS, 0)
    coverage_hist = dict.fromkeys(range(9), 0)
    na_cells = 0
    dialogue_coverages: list[float] = []
    min_cov = 0
    proration_valid = 0

    for row in rows:
        discussed_count = int(row.totals.discussed_count)
        coverage_hist[discussed_count] += 1
        dialogue_coverages.append(discussed_count / 8.0)
        if row.totals.is_min_coverage:
            min_cov += 1
        if row.totals.is_proration_valid:
            proration_valid += 1

        for item in PHQ8_ITEMS:
            if row.items[item].consensus_assertion == "not_mentioned":
                item_na_counts[item] += 1
                na_cells += 1

    item_coverage = {
        item: ((n_dialogues - int(na_count)) / float(n_dialogues)) if n_dialogues else 0.0
        for item, na_count in item_na_counts.items()
    }
    cov_vals = list(item_coverage.values())
    cov_arr = (
        np.array(dialogue_coverages, dtype=float)
        if dialogue_coverages
        else np.array([], dtype=float)
    )

    return CoverageMetrics(
        n_dialogues=n_dialogues,
        total_cells=total_cells,
        na_cells=na_cells,
        corpus_na_rate=(na_cells / float(total_cells)) if total_cells else 0.0,
        item_coverage=item_coverage,
        min_item_coverage=min(cov_vals) if cov_vals else 0.0,
        max_item_coverage=max(cov_vals) if cov_vals else 0.0,
        dialogues_with_min_coverage=min_cov,
        dialogues_with_proration_valid=proration_valid,
        dialogue_coverage_mean=float(np.mean(cov_arr)) if cov_arr.size else 0.0,
        dialogue_coverage_std=float(np.std(cov_arr)) if cov_arr.size else 0.0,
        coverage_histogram=coverage_hist,
    )
