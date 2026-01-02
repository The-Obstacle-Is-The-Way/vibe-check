from __future__ import annotations

import numpy as np
import pytest

from vibe_check.aggregation.posterior import (
    compute_credible_interval,
    compute_item_posterior,
    convolve_posteriors,
)


def test_smoothed_posterior_sums_to_one() -> None:
    votes = [0, 1, 2, 3, 0, 1]
    posterior = compute_item_posterior(votes, alpha=0.5)
    assert float(posterior.sum()) == pytest.approx(1.0)


def test_unanimous_votes_give_peaked_posterior() -> None:
    votes = [2, 2, 2, 2, 2, 2]
    posterior = compute_item_posterior(votes, alpha=0.5)
    assert posterior[2] > 0.8


def test_convolution_produces_correct_range() -> None:
    item_posteriors = [np.array([0.0, 1.0, 0.0, 0.0]) for _ in range(8)]
    total = convolve_posteriors(item_posteriors)
    assert len(total) == 25
    assert int(np.argmax(total)) == 8
    assert float(total[8]) == pytest.approx(1.0)


def test_convolution_with_uncertainty_expected_value() -> None:
    item_posteriors = [np.array([0.5, 0.5, 0.0, 0.0]) for _ in range(8)]
    total = convolve_posteriors(item_posteriors)
    expected_value = float(np.dot(total, np.arange(25)))
    assert expected_value == pytest.approx(4.0)


def test_credible_interval_covers_mode() -> None:
    posterior = np.zeros(25)
    posterior[10] = 0.8
    posterior[9] = 0.1
    posterior[11] = 0.1
    lower, upper = compute_credible_interval(posterior, alpha=0.10)
    assert lower <= 10 <= upper


def test_compute_item_posterior_raises_on_empty_votes() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        compute_item_posterior([], alpha=0.5)


def test_compute_item_posterior_raises_on_negative_alpha() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        compute_item_posterior([0], alpha=-0.1)


def test_compute_item_posterior_raises_on_invalid_vote() -> None:
    with pytest.raises(ValueError, match="Invalid vote"):
        compute_item_posterior([4], alpha=0.5)


def test_convolve_posteriors_raises_on_empty() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        convolve_posteriors([])


def test_convolve_posteriors_skips_normalization_for_zero_mass() -> None:
    total = convolve_posteriors([np.zeros(4), np.zeros(4)])
    assert float(total.sum()) == 0.0


def test_compute_credible_interval_raises_on_empty_posterior() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        compute_credible_interval(np.array([]), alpha=0.10)


def test_compute_credible_interval_raises_on_invalid_alpha() -> None:
    with pytest.raises(ValueError, match="alpha must be in"):
        compute_credible_interval(np.array([1.0]), alpha=1.0)


def test_compute_credible_interval_raises_on_zero_mass() -> None:
    with pytest.raises(ValueError, match="positive mass"):
        compute_credible_interval(np.zeros(3), alpha=0.10)
