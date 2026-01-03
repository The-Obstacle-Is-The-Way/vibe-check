"""Internal consistency metrics for PHQ-8 (SPEC-07)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from collections.abc import Sequence


def compute_cronbach_alpha(item_scores: np.ndarray) -> float:
    """Compute Cronbach's alpha for internal consistency.

    Args:
        item_scores: Array of shape (n_dialogues, n_items).
    """
    if item_scores.ndim != 2:
        raise ValueError("item_scores must be a 2D array (n_dialogues, n_items)")
    n_dialogues, n_items = item_scores.shape
    if n_dialogues < 2 or n_items < 2:
        raise ValueError("item_scores must have at least 2 dialogues and 2 items")

    item_variances = item_scores.var(axis=0, ddof=1)
    total_scores = item_scores.sum(axis=1)
    total_variance = float(total_scores.var(ddof=1))
    if total_variance <= 0.0:
        return 0.0

    alpha = (n_items / (n_items - 1)) * (1 - float(item_variances.sum()) / total_variance)
    return float(alpha)


def compute_item_total_correlations(
    item_scores: np.ndarray,
    *,
    item_names: Sequence[str],
) -> dict[str, float]:
    """Compute per-item Pearson correlation with total score."""
    if item_scores.ndim != 2:
        raise ValueError("item_scores must be a 2D array (n_dialogues, n_items)")
    if item_scores.shape[1] != len(item_names):
        raise ValueError("item_names length must match item_scores.shape[1]")

    total = item_scores.sum(axis=1)
    out: dict[str, float] = {}
    for idx, name in enumerate(item_names):
        x = item_scores[:, idx]
        if float(np.std(x)) == 0.0 or float(np.std(total)) == 0.0:
            out[str(name)] = 0.0
            continue
        corr = float(np.corrcoef(x, total)[0, 1])
        out[str(name)] = corr
    return out
