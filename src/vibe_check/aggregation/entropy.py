"""Uncertainty metrics for discrete posteriors."""

from __future__ import annotations

import numpy as np


def shannon_entropy(posterior: np.ndarray) -> float:
    """Compute Shannon entropy (nats) of a discrete distribution."""
    if posterior.size == 0:
        raise ValueError("posterior must be non-empty")
    p = posterior.astype(float)
    total = float(p.sum())
    if total <= 0:
        raise ValueError("posterior must have positive mass")
    p = p / total
    p = p[p > 0]
    return -float(np.sum(p * np.log(p)))


def max_entropy_for_k_outcomes(k: int) -> float:
    if k <= 0:
        return 0.0
    return float(np.log(k))


def normalized_entropy(posterior: np.ndarray) -> float:
    """Entropy normalized to [0, 1]."""
    max_ent = max_entropy_for_k_outcomes(int(posterior.size))
    if max_ent == 0:
        return 0.0
    return shannon_entropy(posterior) / max_ent
