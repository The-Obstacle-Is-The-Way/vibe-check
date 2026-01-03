"""High-level aggregation APIs."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal, cast

import numpy as np

from vibe_check.aggregation.disagreement import should_arbitrate_item
from vibe_check.aggregation.entropy import shannon_entropy
from vibe_check.aggregation.posterior import (
    compute_credible_interval,
    compute_item_posterior,
    convolve_posteriors,
)
from vibe_check.constants import PHQ8_ITEMS, SEVERITY_BUCKETS, SeverityBucket
from vibe_check.schemas.output import AggregatedPHQ8, ItemAggregation

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from vibe_check.schemas.scoring import PHQ8Report


def aggregate_votes(
    votes_by_item: Mapping[str, Sequence[int]],
    *,
    dirichlet_alpha: float = 0.5,
    range_threshold: int = 2,
    insufficient_evidence_counts: dict[str, int] | None = None,
    arbitration_max_prob_threshold: float = 0.60,
    arbitration_entropy_threshold: float = 1.2,
) -> tuple[dict[str, ItemAggregation], np.ndarray, list[str], dict[str, str]]:
    """Aggregate per-item vote arrays into posteriors and arbitration flags."""
    missing = [item for item in PHQ8_ITEMS if item not in votes_by_item]
    if missing:
        raise ValueError(f"Missing PHQ-8 items: {missing}")

    insufficient_evidence_counts = insufficient_evidence_counts or {}

    item_posteriors: list[np.ndarray] = []
    item_aggregations: dict[str, ItemAggregation] = {}
    arbitration_items: list[str] = []
    arbitration_reasons: dict[str, str] = {}

    for item in PHQ8_ITEMS:
        votes = list(votes_by_item[item])
        posterior = compute_item_posterior(votes, alpha=dirichlet_alpha)
        item_posteriors.append(posterior)

        mode = int(np.argmax(posterior))
        expected = float(np.dot(posterior, np.arange(4)))
        entropy = shannon_entropy(posterior)
        clinical_prob = float(posterior[2] + posterior[3])
        vote_range = (max(votes) - min(votes)) if votes else 0

        insufficient_count = int(insufficient_evidence_counts.get(item, 0))
        needs_arb, reason = should_arbitrate_item(
            posterior,
            votes,
            insufficient_evidence_count=insufficient_count,
            range_threshold=range_threshold,
            max_prob_threshold=arbitration_max_prob_threshold,
            entropy_threshold=arbitration_entropy_threshold,
        )
        if needs_arb and reason is not None:
            arbitration_items.append(item)
            arbitration_reasons[item] = reason

        item_aggregations[item] = ItemAggregation(
            votes=votes,
            vote_counts={str(k): votes.count(k) for k in range(4)},
            posterior={str(k): float(posterior[k]) for k in range(4)},
            mode=mode,
            expected=expected,
            entropy=entropy,
            vote_range=vote_range,
            clinical_prob=clinical_prob,
            needs_arbitration=needs_arb,
            arbitration_reason=reason,
        )

    total_posterior = convolve_posteriors(item_posteriors)
    return item_aggregations, total_posterior, arbitration_items, arbitration_reasons


def _severity_bucket_probs(total_posterior: np.ndarray) -> dict[str, float]:
    probs: dict[str, float] = {}
    for bucket, (lo, hi) in SEVERITY_BUCKETS.items():
        probs[bucket] = float(total_posterior[lo : hi + 1].sum())
    return probs


def _select_bucket(severity_probs: dict[str, float]) -> SeverityBucket:
    bucket = max(severity_probs, key=severity_probs.__getitem__)
    return cast("SeverityBucket", bucket)


def get_severity_bucket(total_score: int) -> SeverityBucket:
    """Get the severity bucket for a given total score."""
    for bucket, (lo, hi) in SEVERITY_BUCKETS.items():
        if lo <= total_score <= hi:
            return bucket
    raise ValueError(f"Invalid total_score for severity bucket: {total_score}")


def aggregate_reports(
    reports: list[PHQ8Report],
    *,
    file_id: str,
    condition: Literal["mdd", "control"],
    prompt_version: str,
    dirichlet_alpha: float = 0.5,
    disagreement_range_threshold: int = 2,
    arbitration_total_std_threshold: float = 2.0,
    arbitration_max_prob_threshold: float = 0.60,
    arbitration_entropy_threshold: float = 1.2,
) -> AggregatedPHQ8:
    """Aggregate multiple juror reports into a final consensus result."""
    if not reports:
        raise ValueError("reports must be non-empty")

    votes_by_item: dict[str, list[int]] = {item: [] for item in PHQ8_ITEMS}
    insufficient_counts: dict[str, int] = dict.fromkeys(PHQ8_ITEMS, 0)

    for report in reports:
        for item in PHQ8_ITEMS:
            item_score = getattr(report, item)
            votes_by_item[item].append(int(item_score.score))
            if item_score.insufficient_evidence:
                insufficient_counts[item] += 1

    items, total_posterior, arbitration_items, arbitration_reasons = aggregate_votes(
        votes_by_item,
        dirichlet_alpha=dirichlet_alpha,
        range_threshold=disagreement_range_threshold,
        insufficient_evidence_counts=insufficient_counts,
        arbitration_max_prob_threshold=arbitration_max_prob_threshold,
        arbitration_entropy_threshold=arbitration_entropy_threshold,
    )

    total_mode = int(np.argmax(total_posterior))
    total_expected = float(np.dot(total_posterior, np.arange(25)))
    total_std = float(np.sqrt(np.dot(total_posterior, (np.arange(25) - total_expected) ** 2)))
    total_ci_90 = compute_credible_interval(total_posterior, alpha=0.10)

    severity_probs = _severity_bucket_probs(total_posterior)
    severity_bucket = _select_bucket(severity_probs)

    juror_totals = np.array([r.total_score for r in reports], dtype=float)
    juror_total_std = float(np.std(juror_totals))
    if juror_total_std >= arbitration_total_std_threshold:
        arbitration_items.append("__total__")
        arbitration_reasons["__total__"] = f"total_score_std={juror_total_std:.2f}"

    any_self_harm = any(r.mentions_self_harm for r in reports)
    all_evidence = [e for r in reports for e in r.self_harm_evidence]

    final_item_scores = {item: int(items[item].mode) for item in PHQ8_ITEMS}
    final_total_score = sum(final_item_scores.values())

    return AggregatedPHQ8(
        file_id=file_id,
        condition=condition,
        items=items,
        total_mode=total_mode,
        total_expected=total_expected,
        total_std=total_std,
        total_posterior={k: float(total_posterior[k]) for k in range(25)},
        total_ci_90=total_ci_90,
        severity_bucket=severity_bucket,
        severity_bucket_probs=severity_probs,
        final_item_scores=final_item_scores,
        final_total_score=final_total_score,
        final_severity_bucket=get_severity_bucket(final_total_score),
        final_source="jury_mode",
        triggered_arbitration=bool(arbitration_items),
        arbitration_items=arbitration_items,
        arbitration_reasons=arbitration_reasons,
        mentions_self_harm=any_self_harm,
        self_harm_evidence=all_evidence,
        juror_reports=reports,
        judge_resolution=None,
        prompt_version=prompt_version,
        scored_at=datetime.now(UTC),
    )
