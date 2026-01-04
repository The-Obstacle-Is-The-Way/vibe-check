"""Condition separation metrics (MDD vs control) for scored runs (SPEC-07)."""

from __future__ import annotations

import numpy as np
from pydantic import BaseModel, ConfigDict
from scipy import stats

from vibe_check.constants import COHENS_D_MIN, P_VALUE_MAX


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
