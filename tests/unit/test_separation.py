from __future__ import annotations

import numpy as np

from vibe_check.diagnostics.separation import compute_condition_separation


def test_condition_separation_directional_validity() -> None:
    mdd_totals = np.array([18, 19, 20, 21, 22] * 10, dtype=float)
    control_totals = np.array([2, 3, 4, 5, 6] * 10, dtype=float)

    metrics = compute_condition_separation(mdd_totals=mdd_totals, control_totals=control_totals)
    assert metrics.mdd_mean > metrics.control_mean
    assert metrics.cohens_d > 0.5
    assert metrics.is_valid is True
