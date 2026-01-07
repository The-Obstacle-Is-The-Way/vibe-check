from __future__ import annotations

from vibe_check.diagnostics.assertions import compute_assertion_distribution


def test_assertion_distribution_counts() -> None:
    from tests.unit.utils import make_minimal_aggregated_phq8_na

    rows = [
        make_minimal_aggregated_phq8_na(file_id="d1", na_items={"fatigue"}),
        make_minimal_aggregated_phq8_na(file_id="d2", na_items=set()),
    ]
    dist = compute_assertion_distribution(rows)

    assert dist.by_item["fatigue"]["not_mentioned"] == 1
    assert dist.by_item["fatigue"]["present"] == 1
    assert sum(dist.totals.values()) == 16
