from __future__ import annotations

from vibe_check.diagnostics.separation import compute_separation_metrics_na


def test_separation_gate_prefers_prorated_when_enough_proration_valid() -> None:
    from tests.unit.utils import make_minimal_aggregated_phq8_na

    rows = [
        make_minimal_aggregated_phq8_na(
            file_id="m1", condition="mdd", na_items=set(), base_score=2
        ),
        make_minimal_aggregated_phq8_na(
            file_id="m2", condition="mdd", na_items={"fatigue"}, base_score=2
        ),
        make_minimal_aggregated_phq8_na(
            file_id="c1", condition="control", na_items=set(), base_score=0
        ),
        make_minimal_aggregated_phq8_na(
            file_id="c2", condition="control", na_items={"sleep"}, base_score=0
        ),
    ]
    metrics = compute_separation_metrics_na(rows)
    assert metrics.n_mdd_prorated == 2
    assert metrics.n_control_prorated == 2
    assert metrics.gate_basis == "prorated"


def test_separation_gate_falls_back_to_imputed_when_prorated_insufficient() -> None:
    from tests.unit.utils import make_minimal_aggregated_phq8_na

    rows = [
        make_minimal_aggregated_phq8_na(
            file_id="m1", condition="mdd", na_items=set(), base_score=2
        ),
        make_minimal_aggregated_phq8_na(
            file_id="m2", condition="mdd", na_items={"fatigue", "appetite"}, base_score=2
        ),
        make_minimal_aggregated_phq8_na(
            file_id="c1", condition="control", na_items=set(), base_score=0
        ),
        make_minimal_aggregated_phq8_na(
            file_id="c2", condition="control", na_items={"sleep"}, base_score=0
        ),
    ]
    metrics = compute_separation_metrics_na(rows)
    assert metrics.n_mdd_prorated == 1
    assert metrics.gate_basis == "imputed"
