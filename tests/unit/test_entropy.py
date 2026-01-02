from __future__ import annotations

import numpy as np
import pytest

from vibe_check.aggregation.entropy import (
    max_entropy_for_k_outcomes,
    normalized_entropy,
    shannon_entropy,
)


def test_entropy_zero_for_certainty() -> None:
    posterior = np.array([0.0, 0.0, 1.0, 0.0])
    assert shannon_entropy(posterior) == 0.0


def test_entropy_max_for_uniform() -> None:
    posterior = np.array([0.25, 0.25, 0.25, 0.25])
    max_ent = max_entropy_for_k_outcomes(4)
    assert shannon_entropy(posterior) == pytest.approx(max_ent)
    assert normalized_entropy(posterior) == pytest.approx(1.0)


def test_entropy_increases_with_spread() -> None:
    peaked = np.array([0.9, 0.05, 0.03, 0.02])
    spread = np.array([0.4, 0.3, 0.2, 0.1])
    assert shannon_entropy(peaked) < shannon_entropy(spread)


def test_entropy_raises_on_empty_distribution() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        shannon_entropy(np.array([]))


def test_entropy_raises_on_non_positive_mass() -> None:
    with pytest.raises(ValueError, match="positive mass"):
        shannon_entropy(np.array([0.0, 0.0, 0.0, 0.0]))


def test_max_entropy_zero_for_nonpositive_k() -> None:
    assert max_entropy_for_k_outcomes(0) == 0.0


def test_normalized_entropy_zero_when_k_is_zero() -> None:
    assert normalized_entropy(np.array([])) == 0.0
