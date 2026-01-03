from __future__ import annotations

import numpy as np
import pytest

from vibe_check.constants import PHQ8_ITEMS
from vibe_check.diagnostics.reliability import (
    compute_krippendorff_alpha,
    compute_krippendorff_alpha_per_item,
)


def test_krippendorff_alpha_is_one_for_perfect_agreement() -> None:
    n_dialogues = 2
    n_items = len(PHQ8_ITEMS)
    n_jurors = 6

    votes = np.zeros((n_dialogues, n_items, n_jurors), dtype=float)
    votes[0, :, :] = 0
    votes[1, :, :] = 3

    alpha = compute_krippendorff_alpha(votes)
    assert alpha == pytest.approx(1.0)

    per_item = compute_krippendorff_alpha_per_item(votes, item_names=list(PHQ8_ITEMS))
    assert set(per_item.keys()) == set(PHQ8_ITEMS)
    assert all(v == pytest.approx(1.0) for v in per_item.values())
