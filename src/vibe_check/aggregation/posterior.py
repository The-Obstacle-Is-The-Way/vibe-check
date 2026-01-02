"""Posterior math: Dirichlet smoothing and total-score convolution."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from collections.abc import Sequence


def compute_item_posterior(votes: Sequence[int], *, alpha: float = 0.5) -> np.ndarray:
    """Compute posterior distribution for a single PHQ-8 item (scores 0..3)."""
    if alpha < 0:
        raise ValueError("alpha must be non-negative")
    if not votes:
        raise ValueError("votes must be non-empty")

    for v in votes:
        if v not in (0, 1, 2, 3):
            raise ValueError(f"Invalid vote value: {v!r}")

    counts = np.bincount(np.array(votes, dtype=int), minlength=4).astype(float)[:4]
    posterior = (counts + alpha) / (float(len(votes)) + 4.0 * alpha)
    return posterior


def convolve_posteriors(item_posteriors: list[np.ndarray]) -> np.ndarray:
    """Compute total score distribution via convolution."""
    if not item_posteriors:
        raise ValueError("item_posteriors must be non-empty")

    from scipy.signal import convolve

    total_dist = item_posteriors[0].astype(float)
    for item_post in item_posteriors[1:]:
        total_dist = convolve(total_dist, item_post.astype(float))

    total = float(total_dist.sum())
    if total > 0:
        total_dist = total_dist / total
    return total_dist


def compute_credible_interval(posterior: np.ndarray, *, alpha: float = 0.10) -> tuple[int, int]:
    """Compute (1-alpha) credible interval for a discrete distribution."""
    if posterior.size == 0:
        raise ValueError("posterior must be non-empty")
    if not (0 < alpha < 1):
        raise ValueError("alpha must be in (0, 1)")

    p = posterior.astype(float)
    total = float(p.sum())
    if total <= 0:
        raise ValueError("posterior must have positive mass")
    p = p / total

    cdf = np.cumsum(p)
    lower = int(np.searchsorted(cdf, alpha / 2, side="left"))
    upper = int(np.searchsorted(cdf, 1 - alpha / 2, side="left"))
    lower = max(0, min(lower, int(posterior.size) - 1))
    upper = max(0, min(upper, int(posterior.size) - 1))
    return (lower, upper)
