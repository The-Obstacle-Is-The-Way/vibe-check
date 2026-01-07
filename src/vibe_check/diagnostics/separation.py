"""Condition separation metrics (MDD vs control) for scored runs (SPEC-07)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from pydantic import BaseModel, ConfigDict, Field
from scipy import stats

from vibe_check.constants import COHENS_D_MIN, P_VALUE_MAX

if TYPE_CHECKING:
    from vibe_check.schemas.output import AggregatedPHQ8


class SeparationMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mdd_mean: float
    mdd_std: float
    control_mean: float
    control_std: float
    cohens_d: float
    t_statistic: float
    p_value: float
    is_valid: bool

    # Convenience aliases matching SPEC-07 example
    @property
    def mdd_mean_total(self) -> float:
        return self.mdd_mean

    @property
    def control_mean_total(self) -> float:
        return self.control_mean


class SeparationMetricsNA(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mdd_mean_imputed: float
    mdd_std_imputed: float
    control_mean_imputed: float
    control_std_imputed: float
    cohens_d_imputed: float
    p_value_imputed: float
    is_imputed_valid: bool

    n_mdd_prorated: int = Field(ge=0)
    n_control_prorated: int = Field(ge=0)
    mdd_mean_prorated: float | None
    mdd_std_prorated: float | None
    control_mean_prorated: float | None
    control_std_prorated: float | None
    cohens_d_prorated: float | None
    p_value_prorated: float | None
    is_prorated_valid: bool

    gate_basis: str = Field(description="'prorated' iff both n_*_prorated>=2 else 'imputed'")


def compute_condition_separation(
    *,
    mdd_totals: np.ndarray,
    control_totals: np.ndarray,
) -> SeparationMetrics:
    """Compute separation metrics between conditions."""
    if mdd_totals.ndim != 1 or control_totals.ndim != 1:
        raise ValueError("mdd_totals and control_totals must be 1D arrays")
    if len(mdd_totals) < 2 or len(control_totals) < 2:
        raise ValueError("Need at least 2 samples per condition")

    mdd_mean = float(np.mean(mdd_totals))
    control_mean = float(np.mean(control_totals))
    mdd_std = float(np.std(mdd_totals, ddof=1))
    control_std = float(np.std(control_totals, ddof=1))

    pooled_var = (
        ((len(mdd_totals) - 1) * (mdd_std**2)) + ((len(control_totals) - 1) * (control_std**2))
    ) / float(len(mdd_totals) + len(control_totals) - 2)
    pooled_std = float(np.sqrt(pooled_var)) if pooled_var > 0 else 0.0
    cohens_d = (mdd_mean - control_mean) / pooled_std if pooled_std > 0 else 0.0

    t_stat, p_value = stats.ttest_ind(mdd_totals, control_totals, equal_var=False)
    is_valid = (
        (mdd_mean > control_mean) and (float(p_value) < P_VALUE_MAX) and (cohens_d >= COHENS_D_MIN)
    )

    return SeparationMetrics(
        mdd_mean=mdd_mean,
        mdd_std=mdd_std,
        control_mean=control_mean,
        control_std=control_std,
        cohens_d=cohens_d,
        t_statistic=float(t_stat),
        p_value=float(p_value),
        is_valid=is_valid,
    )


def compute_separation_metrics_na(rows: list[AggregatedPHQ8]) -> SeparationMetricsNA:
    """Compute imputed + prorated separation with explicit gate basis (SPEC-18)."""
    mdd_rows = [r for r in rows if r.condition == "mdd"]
    control_rows = [r for r in rows if r.condition == "control"]

    mdd_imputed = np.array([float(r.totals.imputed_total) for r in mdd_rows], dtype=float)
    control_imputed = np.array([float(r.totals.imputed_total) for r in control_rows], dtype=float)
    imputed = compute_condition_separation(mdd_totals=mdd_imputed, control_totals=control_imputed)

    mdd_prorated = [
        float(r.totals.prorated_total_rounded)
        for r in mdd_rows
        if r.totals.is_proration_valid and r.totals.prorated_total_rounded is not None
    ]
    control_prorated = [
        float(r.totals.prorated_total_rounded)
        for r in control_rows
        if r.totals.is_proration_valid and r.totals.prorated_total_rounded is not None
    ]

    n_mdd_pr = len(mdd_prorated)
    n_control_pr = len(control_prorated)

    if n_mdd_pr >= 2 and n_control_pr >= 2:
        prorated = compute_condition_separation(
            mdd_totals=np.array(mdd_prorated, dtype=float),
            control_totals=np.array(control_prorated, dtype=float),
        )
        return SeparationMetricsNA(
            mdd_mean_imputed=imputed.mdd_mean,
            mdd_std_imputed=imputed.mdd_std,
            control_mean_imputed=imputed.control_mean,
            control_std_imputed=imputed.control_std,
            cohens_d_imputed=imputed.cohens_d,
            p_value_imputed=imputed.p_value,
            is_imputed_valid=imputed.is_valid,
            n_mdd_prorated=n_mdd_pr,
            n_control_prorated=n_control_pr,
            mdd_mean_prorated=prorated.mdd_mean,
            mdd_std_prorated=prorated.mdd_std,
            control_mean_prorated=prorated.control_mean,
            control_std_prorated=prorated.control_std,
            cohens_d_prorated=prorated.cohens_d,
            p_value_prorated=prorated.p_value,
            is_prorated_valid=prorated.is_valid,
            gate_basis="prorated",
        )

    return SeparationMetricsNA(
        mdd_mean_imputed=imputed.mdd_mean,
        mdd_std_imputed=imputed.mdd_std,
        control_mean_imputed=imputed.control_mean,
        control_std_imputed=imputed.control_std,
        cohens_d_imputed=imputed.cohens_d,
        p_value_imputed=imputed.p_value,
        is_imputed_valid=imputed.is_valid,
        n_mdd_prorated=n_mdd_pr,
        n_control_prorated=n_control_pr,
        mdd_mean_prorated=None,
        mdd_std_prorated=None,
        control_mean_prorated=None,
        control_std_prorated=None,
        cohens_d_prorated=None,
        p_value_prorated=None,
        is_prorated_valid=False,
        gate_basis="imputed",
    )
