from __future__ import annotations

import pytest

from vibe_check.aggregation.disagreement import should_arbitrate_item
from vibe_check.aggregation.posterior import compute_item_posterior


def test_no_arbitration_for_unanimous() -> None:
    votes = [2, 2, 2, 2, 2, 2]
    posterior = compute_item_posterior(votes)
    needs_arb, reason = should_arbitrate_item(posterior, votes)
    assert needs_arb is False
    assert reason is None


def test_arbitration_for_high_range() -> None:
    votes = [0, 0, 2, 2, 2, 2]
    posterior = compute_item_posterior(votes)
    needs_arb, reason = should_arbitrate_item(posterior, votes)
    assert needs_arb is True
    assert reason is not None
    assert "vote_range" in reason


def test_arbitration_for_low_max_prob() -> None:
    votes = [0, 1, 2, 0, 1, 2]
    posterior = compute_item_posterior(votes)
    needs_arb, reason = should_arbitrate_item(posterior, votes)
    assert needs_arb is True
    assert reason is not None
    assert "low_max_prob" in reason


def test_clinical_ambiguity_triggers() -> None:
    votes = [1, 1, 1, 2, 2, 2]
    posterior = compute_item_posterior(votes)
    clinical_prob = float(posterior[2] + posterior[3])
    assert clinical_prob == pytest.approx(0.50)
    needs_arb, reason = should_arbitrate_item(posterior, votes)
    assert needs_arb is True
    assert reason is not None
    assert "clinical_ambiguity" in reason


def test_insufficient_evidence_triggers() -> None:
    votes = [2, 2, 2, 2, 2, 2]
    posterior = compute_item_posterior(votes)
    needs_arb, reason = should_arbitrate_item(
        posterior,
        votes,
        insufficient_evidence_count=2,
    )
    assert needs_arb is True
    assert reason is not None
    assert "insufficient_evidence" in reason
