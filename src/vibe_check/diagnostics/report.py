"""Report schemas for diagnostics (SPEC-07)."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field

from vibe_check.constants import (
    ARBITRATION_RATE_MAX,
    COHENS_D_MIN,
    CRONBACH_ALPHA_MIN,
    KRIPPENDORFF_ALPHA_MIN,
    MAX_CORPUS_NA_RATE,
    MIN_DIALOGUE_MIN_COVERAGE_RATE,
    MIN_ITEM_COVERAGE,
    P_VALUE_MAX,
)
from vibe_check.diagnostics.arbitration import ArbitrationMetrics  # noqa: TC001
from vibe_check.diagnostics.assertions import AssertionDistribution  # noqa: TC001
from vibe_check.diagnostics.coverage import CoverageMetrics  # noqa: TC001
from vibe_check.diagnostics.separation import SeparationMetricsNA  # noqa: TC001


class ReliabilityMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Krippendorff's alpha can be negative when agreement is worse than chance.
    # Some formulations can produce values less than -1.0; do not over-constrain.
    krippendorff_alpha: float
    krippendorff_alpha_per_item: dict[str, float]
    icc_consistency: float
    icc_agreement: float
    icc_ci_95: tuple[float, float]


class ConsistencyMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Cronbach's alpha can be arbitrarily negative for poorly-correlated items.
    # Do not enforce a lower bound.
    cronbach_alpha: float
    item_total_correlations: dict[str, float]


class DiagnosticReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    computed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    n_dialogues: int = Field(ge=0)
    n_mdd: int = Field(ge=0)
    n_control: int = Field(ge=0)

    reliability: ReliabilityMetrics
    consistency: ConsistencyMetrics
    coverage: CoverageMetrics
    assertion_distribution: AssertionDistribution
    separation: SeparationMetricsNA
    arbitration: ArbitrationMetrics

    passes_reliability_gate: bool
    passes_consistency_gate: bool
    passes_coverage_gate: bool
    passes_separation_gate: bool
    passes_arbitration_gate: bool

    @property
    def passes_all_gates(self) -> bool:
        return all(
            [
                self.passes_reliability_gate,
                self.passes_consistency_gate,
                self.passes_coverage_gate,
                self.passes_separation_gate,
                self.passes_arbitration_gate,
            ]
        )

    # Convenience aliases matching SPEC-07 example
    @property
    def krippendorff_alpha(self) -> float:
        return self.reliability.krippendorff_alpha

    @property
    def cronbach_alpha(self) -> float:
        return self.consistency.cronbach_alpha

    @property
    def mdd_mean_total(self) -> float:
        if (
            self.separation.gate_basis == "prorated"
            and self.separation.mdd_mean_prorated is not None
        ):
            return float(self.separation.mdd_mean_prorated)
        return float(self.separation.mdd_mean_imputed)

    @property
    def control_mean_total(self) -> float:
        if (
            self.separation.gate_basis == "prorated"
            and self.separation.control_mean_prorated is not None
        ):
            return float(self.separation.control_mean_prorated)
        return float(self.separation.control_mean_imputed)

    @property
    def arbitration_rate(self) -> float:
        return self.arbitration.overall_rate


def render_diagnostic_report_markdown(report: DiagnosticReport) -> str:
    """Render a human-readable Markdown summary of a DiagnosticReport."""
    lines: list[str] = []
    lines.append(f"# Run Diagnostics: {report.run_id}")
    lines.append("")
    lines.append(f"- Computed at: {report.computed_at.isoformat()}")
    lines.append(
        f"- Dialogues: {report.n_dialogues} (mdd={report.n_mdd}, control={report.n_control})"
    )
    lines.append("")
    lines.append("## Gates")
    lines.append(
        f"- Reliability (Krippendorff alpha >= {KRIPPENDORFF_ALPHA_MIN:.2f}): "
        f"{'PASS' if report.passes_reliability_gate else 'FAIL'} "
        f"(alpha={report.reliability.krippendorff_alpha:.3f})"
    )
    lines.append(
        f"- Consistency (Cronbach alpha >= {CRONBACH_ALPHA_MIN:.2f}): "
        f"{'PASS' if report.passes_consistency_gate else 'FAIL'} "
        f"(alpha={report.consistency.cronbach_alpha:.3f})"
    )
    min_cov_rate = (
        (report.coverage.dialogues_with_min_coverage / report.n_dialogues)
        if report.n_dialogues
        else 0.0
    )
    lines.append(
        f"- Coverage (min_item_coverage>={MIN_ITEM_COVERAGE:.2f}, "
        f"corpus_na_rate<={MAX_CORPUS_NA_RATE:.2f}, "
        f"min_coverage_rate>={MIN_DIALOGUE_MIN_COVERAGE_RATE:.2f}): "
        f"{'PASS' if report.passes_coverage_gate else 'FAIL'} "
        f"(min_item_coverage={report.coverage.min_item_coverage:.3f}, "
        f"corpus_na_rate={report.coverage.corpus_na_rate:.3f}, "
        f"min_coverage_rate={min_cov_rate:.3f})"
    )

    if report.separation.gate_basis == "prorated":
        mdd_mean = report.separation.mdd_mean_prorated or 0.0
        mdd_std = report.separation.mdd_std_prorated or 0.0
        control_mean = report.separation.control_mean_prorated or 0.0
        control_std = report.separation.control_std_prorated or 0.0
        cohens_d = report.separation.cohens_d_prorated or 0.0
        p_value = report.separation.p_value_prorated or 1.0
    else:
        mdd_mean = report.separation.mdd_mean_imputed
        mdd_std = report.separation.mdd_std_imputed
        control_mean = report.separation.control_mean_imputed
        control_std = report.separation.control_std_imputed
        cohens_d = report.separation.cohens_d_imputed
        p_value = report.separation.p_value_imputed

    lines.append(
        f"- Separation (MDD > control, p<{P_VALUE_MAX:g}, d>={COHENS_D_MIN:g}): "
        f"{'PASS' if report.passes_separation_gate else 'FAIL'} "
        f"(basis={report.separation.gate_basis}, "
        f"mdd_mean={mdd_mean:.2f}, "
        f"control_mean={control_mean:.2f}, "
        f"d={cohens_d:.2f}, "
        f"p={p_value:.3g})"
    )
    lines.append(
        f"- Arbitration (rate < {ARBITRATION_RATE_MAX:.2f}): "
        f"{'PASS' if report.passes_arbitration_gate else 'FAIL'} "
        f"(rate={report.arbitration.overall_rate:.3f})"
    )
    lines.append("")
    lines.append("## Reliability")
    lines.append(f"- Krippendorff alpha: {report.reliability.krippendorff_alpha:.3f}")
    lines.append(
        f"- ICC consistency: {report.reliability.icc_consistency:.3f} "
        f"(95% CI {report.reliability.icc_ci_95[0]:.3f} - {report.reliability.icc_ci_95[1]:.3f})"
    )
    lines.append(f"- ICC agreement: {report.reliability.icc_agreement:.3f}")
    lines.append("")
    lines.append("## Consistency")
    lines.append(f"- Cronbach alpha: {report.consistency.cronbach_alpha:.3f}")
    lines.append("")
    lines.append("## Coverage")
    lines.append(f"- Corpus NA rate: {report.coverage.corpus_na_rate:.3f}")
    lines.append(f"- Min item coverage: {report.coverage.min_item_coverage:.3f}")
    lines.append(
        f"- Dialogues proration-valid: {report.coverage.dialogues_with_proration_valid}/{report.n_dialogues}"
    )
    lines.append("")
    lines.append("## Separation")
    lines.append(
        f"- MDD mean total ({report.separation.gate_basis}): {mdd_mean:.2f} (std={mdd_std:.2f})"
    )
    lines.append(
        f"- Control mean total ({report.separation.gate_basis}): {control_mean:.2f} (std={control_std:.2f})"
    )
    lines.append("")
    lines.append("## Arbitration")
    lines.append(f"- Overall rate: {report.arbitration.overall_rate:.3f}")
    lines.append(f"- Judge agreement with mode: {report.arbitration.judge_agreement_with_mode:.3f}")
    lines.append("")
    return "\n".join(lines) + "\n"
