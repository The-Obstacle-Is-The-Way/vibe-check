"""Report schemas for diagnostics (SPEC-07)."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field

from vibe_check.diagnostics.arbitration import ArbitrationMetrics  # noqa: TC001
from vibe_check.diagnostics.separation import SeparationMetrics  # noqa: TC001


class ReliabilityMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Krippendorff's alpha can be negative when agreement is worse than chance
    krippendorff_alpha: float = Field(ge=-1.0, le=1.0)
    krippendorff_alpha_per_item: dict[str, float]
    icc_consistency: float
    icc_agreement: float
    icc_ci_95: tuple[float, float]


class ConsistencyMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Cronbach's alpha can be negative when items are negatively correlated
    cronbach_alpha: float = Field(ge=-1.0, le=1.0)
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
    separation: SeparationMetrics
    arbitration: ArbitrationMetrics

    passes_reliability_gate: bool
    passes_consistency_gate: bool
    passes_separation_gate: bool
    passes_arbitration_gate: bool

    @property
    def passes_all_gates(self) -> bool:
        return all(
            [
                self.passes_reliability_gate,
                self.passes_consistency_gate,
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
        return self.separation.mdd_mean_total

    @property
    def control_mean_total(self) -> float:
        return self.separation.control_mean_total

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
        f"- Reliability (Krippendorff alpha >= 0.67): "
        f"{'PASS' if report.passes_reliability_gate else 'FAIL'} "
        f"(alpha={report.reliability.krippendorff_alpha:.3f})"
    )
    lines.append(
        f"- Consistency (Cronbach alpha >= 0.70): "
        f"{'PASS' if report.passes_consistency_gate else 'FAIL'} "
        f"(alpha={report.consistency.cronbach_alpha:.3f})"
    )
    lines.append(
        f"- Separation (MDD > control, p<0.01, d>=0.5): "
        f"{'PASS' if report.passes_separation_gate else 'FAIL'} "
        f"(mdd_mean={report.separation.mdd_mean:.2f}, "
        f"control_mean={report.separation.control_mean:.2f}, "
        f"d={report.separation.cohens_d:.2f}, "
        f"p={report.separation.p_value:.3g})"
    )
    lines.append(
        f"- Arbitration (rate < 0.30): "
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
    lines.append("## Separation")
    lines.append(
        f"- MDD mean total: {report.separation.mdd_mean:.2f} (std={report.separation.mdd_std:.2f})"
    )
    lines.append(
        f"- Control mean total: {report.separation.control_mean:.2f} (std={report.separation.control_std:.2f})"
    )
    lines.append("")
    lines.append("## Arbitration")
    lines.append(f"- Overall rate: {report.arbitration.overall_rate:.3f}")
    lines.append(f"- Judge agreement with mode: {report.arbitration.judge_agreement_with_mode:.3f}")
    lines.append("")
    return "\n".join(lines) + "\n"
