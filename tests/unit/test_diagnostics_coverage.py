from __future__ import annotations

import pytest

from vibe_check.diagnostics.coverage import compute_coverage_metrics


def test_coverage_full() -> None:
    from tests.unit.utils import make_minimal_aggregated_phq8_na

    rows = [make_minimal_aggregated_phq8_na(file_id=f"d{i}", na_items=set()) for i in range(10)]
    m = compute_coverage_metrics(rows)
    assert m.total_cells == 80
    assert m.na_cells == 0
    assert m.corpus_na_rate == 0.0
    assert m.min_item_coverage == 1.0
    assert m.dialogues_with_proration_valid == 10


def test_coverage_partial() -> None:
    from tests.unit.utils import make_minimal_aggregated_phq8_na

    rows = [
        make_minimal_aggregated_phq8_na(file_id="d1", na_items={"fatigue", "appetite"}),
        make_minimal_aggregated_phq8_na(file_id="d2", na_items={"fatigue"}),
        make_minimal_aggregated_phq8_na(file_id="d3", na_items=set()),
        make_minimal_aggregated_phq8_na(
            file_id="d4", na_items={"fatigue", "appetite", "psychomotor"}
        ),
    ]
    m = compute_coverage_metrics(rows)
    assert m.total_cells == 32
    assert m.na_cells == 6
    assert m.corpus_na_rate == pytest.approx(6 / 32)
    assert m.item_coverage["fatigue"] == pytest.approx(0.25)
    assert m.coverage_histogram[8] == 1
    assert m.coverage_histogram[7] == 1
    assert m.coverage_histogram[6] == 1
    assert m.coverage_histogram[5] == 1
