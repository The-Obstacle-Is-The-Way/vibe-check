"""Assertion distribution metrics for NA-aware runs (SPEC-18)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict

from vibe_check.constants import PHQ8_ITEMS

if TYPE_CHECKING:
    from vibe_check.schemas.output import AggregatedPHQ8

Assertion = Literal["present", "denied", "possible", "not_mentioned"]


class AssertionDistribution(BaseModel):
    """Consensus assertion distribution across the run."""

    model_config = ConfigDict(extra="forbid")

    by_item: dict[str, dict[Assertion, int]]
    totals: dict[Assertion, int]


def compute_assertion_distribution(rows: list[AggregatedPHQ8]) -> AssertionDistribution:
    by_item: dict[str, dict[Assertion, int]] = {
        item: {"present": 0, "denied": 0, "possible": 0, "not_mentioned": 0} for item in PHQ8_ITEMS
    }
    totals: dict[Assertion, int] = {"present": 0, "denied": 0, "possible": 0, "not_mentioned": 0}

    for row in rows:
        for item in PHQ8_ITEMS:
            a = row.items[item].consensus_assertion
            by_item[item][a] += 1
            totals[a] += 1

    return AssertionDistribution(by_item=by_item, totals=totals)
