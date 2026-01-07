from __future__ import annotations

import pytest
from tests.fixtures.sample_votes import create_mock_report

from vibe_check.aggregation.aggregate import aggregate_reports
from vibe_check.constants import PHQ8_ITEMS
from vibe_check.diagnostics.arbitration import ArbitrationMetrics, compute_arbitration_metrics
from vibe_check.diagnostics.assertions import AssertionDistribution
from vibe_check.diagnostics.coverage import CoverageMetrics
from vibe_check.diagnostics.report import (
    ConsistencyMetrics,
    DiagnosticReport,
    ReliabilityMetrics,
    render_diagnostic_report_markdown,
)
from vibe_check.diagnostics.separation import SeparationMetricsNA


def test_compute_arbitration_metrics_handles_empty_rows() -> None:
    metrics = compute_arbitration_metrics([])
    assert metrics.overall_rate == 0.0
    assert metrics.judge_agreement_with_mode == 1.0
    assert set(metrics.per_item_rates.keys()) == set(PHQ8_ITEMS)


def test_compute_arbitration_metrics_counts_rates_and_judge_agreement() -> None:
    reports_disagree = [create_mock_report(i, force_disagreement="sleep") for i in range(6)]
    row_a = aggregate_reports(
        reports_disagree,
        file_id="dialogue_a",
        condition="control",
        prompt_version="v1",
    )
    assert row_a.triggered_arbitration is True
    assert "sleep" in row_a.arbitration_items

    sleep_mode = row_a.items["sleep"].mode
    assert sleep_mode is not None
    row_a = row_a.model_copy(
        update={"judge_resolution": {"sleep": {"final_score": int(sleep_mode)}}}
    )

    reports_ok = [create_mock_report(i) for i in range(6)]
    row_b = aggregate_reports(
        reports_ok,
        file_id="dialogue_b",
        condition="control",
        prompt_version="v1",
    )
    assert row_b.triggered_arbitration is False

    metrics = compute_arbitration_metrics([row_a, row_b])
    assert metrics.overall_rate == pytest.approx(0.5)
    assert set(metrics.per_item_rates.keys()) == set(PHQ8_ITEMS)
    assert metrics.per_item_rates["sleep"] == pytest.approx(0.5)
    assert metrics.trigger_reasons.get("vote_range", 0) >= 1
    assert metrics.judge_agreement_with_mode == pytest.approx(1.0)


def test_render_diagnostic_report_markdown_includes_gate_statuses() -> None:
    reliability = ReliabilityMetrics(
        krippendorff_alpha=0.75,
        krippendorff_alpha_per_item=dict.fromkeys(PHQ8_ITEMS, 0.75),
        icc_consistency=0.8,
        icc_agreement=0.8,
        icc_ci_95=(0.7, 0.9),
    )
    consistency = ConsistencyMetrics(
        cronbach_alpha=0.8,
        item_total_correlations=dict.fromkeys(PHQ8_ITEMS, 0.5),
    )
    separation = SeparationMetricsNA(
        mdd_mean_imputed=12.0,
        mdd_std_imputed=2.0,
        control_mean_imputed=6.0,
        control_std_imputed=2.0,
        cohens_d_imputed=1.0,
        p_value_imputed=0.001,
        is_imputed_valid=True,
        n_mdd_prorated=0,
        n_control_prorated=0,
        mdd_mean_prorated=None,
        mdd_std_prorated=None,
        control_mean_prorated=None,
        control_std_prorated=None,
        cohens_d_prorated=None,
        p_value_prorated=None,
        is_prorated_valid=False,
        gate_basis="imputed",
    )
    arbitration = ArbitrationMetrics(
        overall_rate=0.1,
        per_item_rates=dict.fromkeys(PHQ8_ITEMS, 0.0),
        trigger_reasons={"vote_range": 3},
        judge_agreement_with_mode=0.9,
    )

    coverage = CoverageMetrics(
        n_dialogues=10,
        total_cells=80,
        na_cells=0,
        corpus_na_rate=0.0,
        item_coverage=dict.fromkeys(PHQ8_ITEMS, 1.0),
        min_item_coverage=1.0,
        max_item_coverage=1.0,
        dialogues_with_min_coverage=10,
        dialogues_with_proration_valid=10,
        dialogue_coverage_mean=1.0,
        dialogue_coverage_std=0.0,
        coverage_histogram={i: (10 if i == 8 else 0) for i in range(9)},
    )
    assertion_distribution = AssertionDistribution(
        by_item={
            item: {"present": 10, "denied": 0, "possible": 0, "not_mentioned": 0}
            for item in PHQ8_ITEMS
        },
        totals={"present": 80, "denied": 0, "possible": 0, "not_mentioned": 0},
    )

    report = DiagnosticReport(
        run_id="run",
        n_dialogues=10,
        n_mdd=5,
        n_control=5,
        reliability=reliability,
        consistency=consistency,
        coverage=coverage,
        assertion_distribution=assertion_distribution,
        separation=separation,
        arbitration=arbitration,
        passes_reliability_gate=True,
        passes_consistency_gate=True,
        passes_coverage_gate=True,
        passes_separation_gate=True,
        passes_arbitration_gate=True,
    )

    md = render_diagnostic_report_markdown(report)
    assert "# Run Diagnostics: run" in md
    assert "Krippendorff alpha >= 0.67" in md
    assert "Cronbach alpha >= 0.70" in md
    assert "Coverage (min_item_coverage" in md
    assert "Arbitration (rate < 0.30)" in md
    assert "PASS" in md
