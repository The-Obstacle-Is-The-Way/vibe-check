from __future__ import annotations

import numpy as np
import pytest

from vibe_check.constants import PHQ8_ITEMS
from vibe_check.diagnostics.consistency import (
    compute_cronbach_alpha,
    compute_item_total_correlations,
)


def test_cronbach_alpha_is_one_for_perfectly_correlated_items() -> None:
    scores = np.array(
        [
            [0] * len(PHQ8_ITEMS),
            [1] * len(PHQ8_ITEMS),
            [2] * len(PHQ8_ITEMS),
        ],
        dtype=float,
    )
    alpha = compute_cronbach_alpha(scores)
    assert alpha == pytest.approx(1.0)


def test_item_total_correlations_has_all_items() -> None:
    scores = np.array(
        [
            [0] * len(PHQ8_ITEMS),
            [1] * len(PHQ8_ITEMS),
            [2] * len(PHQ8_ITEMS),
        ],
        dtype=float,
    )
    corr = compute_item_total_correlations(scores, item_names=list(PHQ8_ITEMS))
    assert set(corr.keys()) == set(PHQ8_ITEMS)
