"""Diagnostics runner for scored corpora (SPEC-07)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from vibe_check.constants import (
    ARBITRATION_RATE_MAX,
    CRONBACH_ALPHA_MIN,
    KRIPPENDORFF_ALPHA_MIN,
    MAX_CORPUS_NA_RATE,
    MIN_DIALOGUE_MIN_COVERAGE_RATE,
    MIN_ITEM_COVERAGE,
    PHQ8_ITEMS,
)
from vibe_check.diagnostics.arbitration import compute_arbitration_metrics
from vibe_check.diagnostics.assertions import compute_assertion_distribution
from vibe_check.diagnostics.consistency import (
    compute_cronbach_alpha,
    compute_item_total_correlations,
)
from vibe_check.diagnostics.coverage import compute_coverage_metrics
from vibe_check.diagnostics.reliability import (
    compute_krippendorff_alpha,
    compute_krippendorff_alpha_per_item,
)
from vibe_check.diagnostics.report import ConsistencyMetrics, DiagnosticReport, ReliabilityMetrics
from vibe_check.diagnostics.separation import compute_separation_metrics_na
from vibe_check.schemas.output import AggregatedPHQ8


class RunDiagnostics:
    """Compute diagnostics and quality gates for a scored run."""

    def __init__(
        self,
        *,
        scored_jsonl: str | Path,
        run_manifest: str | Path | None = None,
    ) -> None:
        self._scored_jsonl = Path(scored_jsonl)
        self._run_manifest = Path(run_manifest) if run_manifest is not None else None

    def _load_rows(self) -> list[AggregatedPHQ8]:
        rows: list[AggregatedPHQ8] = []
        for line in self._scored_jsonl.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            raw: dict[str, Any] = json.loads(line)
            filtered = {k: raw[k] for k in AggregatedPHQ8.model_fields if k in raw}
            rows.append(AggregatedPHQ8.model_validate(filtered))
        return rows

    def compute(self) -> DiagnosticReport:
        rows = self._load_rows()
        run_id = self._scored_jsonl.parent.name or "run"

        if not rows:
            raise ValueError("scored_jsonl contains no rows")

        n_dialogues = len(rows)
        n_mdd = sum(1 for r in rows if r.condition == "mdd")
        n_control = sum(1 for r in rows if r.condition == "control")

        # Reliability (juror vote tensor)
        n_items = len(PHQ8_ITEMS)
        n_jurors = len(rows[0].juror_reports)
        votes = np.full((n_dialogues, n_items, n_jurors), np.nan, dtype=float)
        for i, row in enumerate(rows):
            if len(row.juror_reports) != n_jurors:
                raise ValueError("inconsistent juror count across rows")
            for j, item in enumerate(PHQ8_ITEMS):
                for k, report in enumerate(row.juror_reports):
                    score = getattr(report, item).score
                    votes[i, j, k] = float(score) if score is not None else np.nan

        kripp = compute_krippendorff_alpha(votes)
        kripp_per_item = compute_krippendorff_alpha_per_item(votes, item_names=list(PHQ8_ITEMS))

        # ICC on flattened units (dialogues x items) with 6 raters
        icc_votes = np.nan_to_num(votes, nan=0.0)
        flat = icc_votes.reshape(n_dialogues * n_items, n_jurors)
        icc_consistency, icc_agreement, icc_ci = _compute_icc_metrics(flat)

        reliability = ReliabilityMetrics(
            krippendorff_alpha=kripp,
            krippendorff_alpha_per_item=kripp_per_item,
            icc_consistency=icc_consistency,
            icc_agreement=icc_agreement,
            icc_ci_95=icc_ci,
        )

        # Consistency (final item scores)
        final_scores = np.array(
            [[float(r.final_item_scores[item]) for item in PHQ8_ITEMS] for r in rows], dtype=float
        )
        cronbach = compute_cronbach_alpha(final_scores)
        item_corr = compute_item_total_correlations(final_scores, item_names=list(PHQ8_ITEMS))
        consistency = ConsistencyMetrics(cronbach_alpha=cronbach, item_total_correlations=item_corr)

        # Coverage + assertion distributions
        coverage = compute_coverage_metrics(rows)
        assertion_distribution = compute_assertion_distribution(rows)

        # Separation (imputed + prorated; explicit gate basis)
        separation = compute_separation_metrics_na(rows)

        # Arbitration
        arbitration = compute_arbitration_metrics(rows)

        passes_reliability = reliability.krippendorff_alpha >= KRIPPENDORFF_ALPHA_MIN
        passes_consistency = consistency.cronbach_alpha >= CRONBACH_ALPHA_MIN

        min_cov_rate = (coverage.dialogues_with_min_coverage / n_dialogues) if n_dialogues else 0.0
        passes_coverage = (
            coverage.min_item_coverage >= MIN_ITEM_COVERAGE
            and coverage.corpus_na_rate <= MAX_CORPUS_NA_RATE
            and min_cov_rate >= MIN_DIALOGUE_MIN_COVERAGE_RATE
        )

        if separation.gate_basis == "prorated":
            passes_separation = bool(separation.is_prorated_valid)
        else:
            passes_separation = bool(separation.is_imputed_valid)
        passes_arbitration = arbitration.overall_rate < ARBITRATION_RATE_MAX

        return DiagnosticReport(
            run_id=run_id,
            n_dialogues=n_dialogues,
            n_mdd=n_mdd,
            n_control=n_control,
            reliability=reliability,
            consistency=consistency,
            coverage=coverage,
            assertion_distribution=assertion_distribution,
            separation=separation,
            arbitration=arbitration,
            passes_reliability_gate=passes_reliability,
            passes_consistency_gate=passes_consistency,
            passes_coverage_gate=passes_coverage,
            passes_separation_gate=passes_separation,
            passes_arbitration_gate=passes_arbitration,
        )


def _compute_icc_metrics(votes: np.ndarray) -> tuple[float, float, tuple[float, float]]:
    """Compute (consistency ICC, agreement ICC, 95% CI for consistency ICC)."""
    if votes.ndim != 2:
        raise ValueError("votes must be a 2D array (n_units, n_raters)")
    n, k = votes.shape
    if n < 2 or k < 2:
        raise ValueError("Need at least 2 units and 2 raters for ICC")

    grand_mean = float(np.mean(votes))
    row_means = np.mean(votes, axis=1)
    col_means = np.mean(votes, axis=0)

    ssr = float(k * np.sum((row_means - grand_mean) ** 2))
    ssc = float(n * np.sum((col_means - grand_mean) ** 2))
    sse = float(np.sum((votes - row_means[:, None] - col_means[None, :] + grand_mean) ** 2))

    df_r = n - 1
    df_c = k - 1
    df_e = (n - 1) * (k - 1)

    msr = ssr / float(df_r)
    msc = ssc / float(df_c) if df_c else 0.0
    mse = sse / float(df_e)

    if mse == 0.0:
        if msr == 0.0:
            return 0.0, 0.0, (0.0, 0.0)
        return 1.0, 1.0, (1.0, 1.0)

    # ICC(3,1) consistency
    icc_c = (msr - mse) / (msr + (k - 1) * mse) if (msr + (k - 1) * mse) else 0.0

    # ICC(2,1) absolute agreement
    denom = msr + (k - 1) * mse + (k * (msc - mse) / float(n))
    icc_a = (msr - mse) / denom if denom else 0.0

    # 95% CI for ICC(3,1)
    from scipy.stats import f as f_dist

    f_value = msr / mse
    lower_f = f_value / float(f_dist.ppf(0.975, df_r, df_e))
    upper_f = f_value / float(f_dist.ppf(0.025, df_r, df_e))
    ci_lower = (lower_f - 1) / (lower_f + (k - 1))
    ci_upper = (upper_f - 1) / (upper_f + (k - 1))

    return float(icc_c), float(icc_a), (float(ci_lower), float(ci_upper))
