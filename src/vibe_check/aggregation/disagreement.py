"""Arbitration triggers based on posterior uncertainty."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from vibe_check.aggregation.entropy import shannon_entropy

if TYPE_CHECKING:
    from collections.abc import Sequence


def should_arbitrate_item(
    posterior: np.ndarray,
    votes: Sequence[int],
    *,
    max_prob_threshold: float = 0.60,
    entropy_threshold: float = 1.2,
    clinical_ambiguity_band: tuple[float, float] = (0.4, 0.6),
    range_threshold: int = 2,
    insufficient_evidence_count: int = 0,
    insufficient_evidence_threshold: int = 2,
) -> tuple[bool, str | None]:
    """Determine if an item needs judge arbitration."""
    reasons: list[str] = []

    max_prob = float(np.max(posterior))
    if max_prob < max_prob_threshold:
        reasons.append(f"low_max_prob={max_prob:.2f}")

    entropy = shannon_entropy(posterior)
    if entropy > entropy_threshold:
        reasons.append(f"high_entropy={entropy:.2f}")

    clinical_prob = float(posterior[2] + posterior[3])
    if clinical_ambiguity_band[0] <= clinical_prob <= clinical_ambiguity_band[1]:
        reasons.append(f"clinical_ambiguity={clinical_prob:.2f}")

    vote_range = (max(votes) - min(votes)) if votes else 0
    if vote_range >= range_threshold:
        reasons.append(f"vote_range={vote_range}")

    if insufficient_evidence_count >= insufficient_evidence_threshold:
        reasons.append(f"insufficient_evidence={insufficient_evidence_count}")

    if reasons:
        return True, "; ".join(reasons)
    return False, None
