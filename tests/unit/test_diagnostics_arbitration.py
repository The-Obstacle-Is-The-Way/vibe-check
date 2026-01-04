from __future__ import annotations

import pytest
from tests.fixtures.sample_votes import create_mock_report

from vibe_check.aggregation.aggregate import aggregate_reports
from vibe_check.constants import PHQ8_ITEMS
from vibe_check.diagnostics.arbitration import ArbitrationMetrics, compute_arbitration_metrics
from vibe_check.diagnostics.report import (
    ConsistencyMetrics,
    DiagnosticReport,
    ReliabilityMetrics,
    render_diagnostic_report_markdown,
)
from vibe_check.diagnostics.separation import SeparationMetrics


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

    sleep_mode = int(row_a.items["sleep"].mode)
    row_a = row_a.model_copy(update={"judge_resolution": {"sleep": {"final_score": sleep_mode}}})

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
    separation = SeparationMetrics(
        mdd_mean=12.0,
        mdd_std=2.0,
        control_mean=6.0,
        control_std=2.0,
        cohens_d=1.0,
        t_statistic=4.0,
        p_value=0.001,
        is_valid=True,
    )
    arbitration = ArbitrationMetrics(
        overall_rate=0.1,
        per_item_rates=dict.fromkeys(PHQ8_ITEMS, 0.0),
        trigger_reasons={"vote_range": 3},
        judge_agreement_with_mode=0.9,
    )

    report = DiagnosticReport(
        run_id="run",
        n_dialogues=10,
        n_mdd=5,
        n_control=5,
        reliability=reliability,
        consistency=consistency,
        separation=separation,
        arbitration=arbitration,
        passes_reliability_gate=True,
        passes_consistency_gate=True,
        passes_separation_gate=True,
        passes_arbitration_gate=True,
    )

    md = render_diagnostic_report_markdown(report)
    assert "# Run Diagnostics: run" in md
    assert "Krippendorff alpha >= 0.67" in md
    assert "Cronbach alpha >= 0.70" in md
    assert "Arbitration (rate < 0.30)" in md
    assert "PASS" in md
