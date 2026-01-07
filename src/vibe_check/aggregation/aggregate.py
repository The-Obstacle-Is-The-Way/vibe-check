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
    convolve_posteriors_with_na,
)
from vibe_check.constants import PHQ8_ITEMS, SEVERITY_BUCKETS, SeverityBucket
from vibe_check.schemas.output import AggregatedPHQ8, ItemAggregationNA
from vibe_check.schemas.scoring import Assertion, PHQ8TotalScore

if TYPE_CHECKING:
    from collections.abc import Mapping

    from vibe_check.schemas.scoring import PHQ8Report


def compute_item_aggregation_with_na(
    votes: list[int | None],
    assertions: list[Assertion],
    *,
    dirichlet_alpha: float = 0.5,
    range_threshold: int = 2,
    arbitration_max_prob_threshold: float = 0.60,
    arbitration_entropy_threshold: float = 1.2,
    clinical_ambiguity_band: tuple[float, float] = (0.4, 0.6),
    na_rate_arbitration_threshold: float | None = None,
    na_count_arbitration_threshold: int | None = None,
) -> ItemAggregationNA:
    """Aggregate one item's votes into an NA-aware ItemAggregationNA (SPEC-15)."""
    if not votes:
        raise ValueError("votes must be non-empty")
    if len(votes) != len(assertions):
        raise ValueError("votes and assertions must have the same length")

    numeric_votes = [int(v) for v in votes if v is not None]
    na_count = len(votes) - len(numeric_votes)
    p_not_mentioned = na_count / float(len(votes))

    # Defensive check: juror schema already enforces vote/assertion alignment.
    for v, a in zip(votes, assertions, strict=False):
        if v is None and a != "not_mentioned":
            raise ValueError("vote=None requires assertion='not_mentioned'")
        if v is not None and a == "not_mentioned":
            raise ValueError("assertion='not_mentioned' requires vote=None")

    vote_counts = {str(i): numeric_votes.count(i) for i in range(4)}

    posterior_dict: dict[str, float] | None = None
    mode: int | None = None
    expected: float | None = None
    entropy: float | None = None
    vote_range: int | None = None
    clinical_prob: float | None = None

    if numeric_votes:
        posterior = compute_item_posterior(numeric_votes, alpha=dirichlet_alpha)
        posterior_dict = {str(k): float(posterior[k]) for k in range(4)}
        mode = int(np.argmax(posterior))
        expected = float(np.dot(posterior, np.arange(4)))
        entropy = shannon_entropy(posterior)
        clinical_prob = float(posterior[2] + posterior[3])
        vote_range = (max(numeric_votes) - min(numeric_votes)) if numeric_votes else 0

    # Consensus assertion rules (SPEC-15 §2.3)
    consensus_score: int | None
    consensus_assertion: Assertion

    if na_count > (len(votes) / 2):
        consensus_score = None
        consensus_assertion = "not_mentioned"
    elif mode is None:
        # Unanimous NA.
        consensus_score = None
        consensus_assertion = "not_mentioned"
    else:
        consensus_score = int(mode)
        if mode == 0:
            consensus_assertion = "denied"
        elif mode == 1:
            numeric_assertions = [
                a for v, a in zip(votes, assertions, strict=False) if v is not None
            ]
            possible_votes = sum(1 for a in numeric_assertions if a == "possible")
            if possible_votes > (len(numeric_assertions) / 2):
                consensus_assertion = "possible"
            else:
                consensus_assertion = "present"
        else:
            consensus_assertion = "present"

    # Arbitration triggers (existing uncertainty + NA-specific gates)
    needs_arbitration = False
    reasons: list[str] = []

    if (
        numeric_votes
        and na_count_arbitration_threshold is not None
        and na_count >= na_count_arbitration_threshold
    ):
        needs_arbitration = True
        reasons.append(f"high_na_count={na_count}")

    if (
        numeric_votes
        and na_rate_arbitration_threshold is not None
        and p_not_mentioned > na_rate_arbitration_threshold
    ):
        needs_arbitration = True
        reasons.append(f"high_na_rate={p_not_mentioned:.2f}")

    if numeric_votes and posterior_dict is not None:
        posterior_arr = np.array([posterior_dict[str(i)] for i in range(4)], dtype=float)
        needs_arb, reason = should_arbitrate_item(
            posterior_arr,
            numeric_votes,
            range_threshold=range_threshold,
            max_prob_threshold=arbitration_max_prob_threshold,
            entropy_threshold=arbitration_entropy_threshold,
            clinical_ambiguity_band=clinical_ambiguity_band,
            insufficient_evidence_count=0,
            insufficient_evidence_threshold=999999,  # disabled for NA-aware schema
        )
        if needs_arb and reason:
            needs_arbitration = True
            reasons.append(reason)

    return ItemAggregationNA(
        votes=votes,
        assertions=assertions,
        numeric_votes=numeric_votes,
        vote_counts=vote_counts,
        posterior=posterior_dict,
        mode=mode,
        expected=expected,
        entropy=entropy,
        vote_range=vote_range,
        clinical_prob=clinical_prob,
        na_count=na_count,
        p_not_mentioned=p_not_mentioned,
        consensus_score=consensus_score,
        consensus_assertion=consensus_assertion,
        needs_arbitration=needs_arbitration,
        arbitration_reason="; ".join(reasons) if reasons else None,
    )


def compute_total_score_with_na(item_consensus: Mapping[str, int | None]) -> PHQ8TotalScore:
    """Compute totals/provenance for an NA-aware per-item consensus map (SPEC-15)."""
    missing = [item for item in PHQ8_ITEMS if item not in item_consensus]
    if missing:
        raise ValueError(f"Missing PHQ-8 items: {missing}")
    return PHQ8TotalScore.from_item_scores(item_consensus)


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


def get_severity_bucket_phq_like(total: PHQ8TotalScore) -> SeverityBucket | None:
    """PHQ-like severity bucket from prorated totals (only when proration valid)."""
    if not total.is_proration_valid or total.prorated_total_rounded is None:
        return None
    return get_severity_bucket(int(total.prorated_total_rounded))


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
    clinical_ambiguity_band: tuple[float, float] = (0.4, 0.6),
    insufficient_evidence_threshold: int = 2,
) -> AggregatedPHQ8:
    """Aggregate multiple juror reports into a final consensus result."""
    if not reports:
        raise ValueError("reports must be non-empty")

    votes_by_item: dict[str, list[int | None]] = {item: [] for item in PHQ8_ITEMS}
    assertions_by_item: dict[str, list[Assertion]] = {item: [] for item in PHQ8_ITEMS}

    for report in reports:
        for item in PHQ8_ITEMS:
            item_score = getattr(report, item)
            votes_by_item[item].append(item_score.score)
            assertions_by_item[item].append(item_score.assertion)

    arbitration_items: list[str] = []
    arbitration_reasons: dict[str, str] = {}

    items: dict[str, ItemAggregationNA] = {}
    item_posteriors: list[np.ndarray] = []
    na_indices: list[int] = []

    for idx, item in enumerate(PHQ8_ITEMS):
        item_agg = compute_item_aggregation_with_na(
            votes_by_item[item],
            assertions_by_item[item],
            dirichlet_alpha=dirichlet_alpha,
            range_threshold=disagreement_range_threshold,
            arbitration_max_prob_threshold=arbitration_max_prob_threshold,
            arbitration_entropy_threshold=arbitration_entropy_threshold,
            clinical_ambiguity_band=clinical_ambiguity_band,
            na_count_arbitration_threshold=insufficient_evidence_threshold,
        )
        items[item] = item_agg

        posterior_dict = item_agg.posterior
        if posterior_dict is None:
            item_posteriors.append(np.array([0.25, 0.25, 0.25, 0.25], dtype=float))
        else:
            item_posteriors.append(
                np.array([posterior_dict[str(i)] for i in range(4)], dtype=float)
            )

        if item_agg.consensus_assertion == "not_mentioned":
            na_indices.append(idx)

        if item_agg.needs_arbitration and item_agg.arbitration_reason is not None:
            arbitration_items.append(item)
            arbitration_reasons[item] = item_agg.arbitration_reason

    total_posterior = convolve_posteriors_with_na(item_posteriors, na_indices=na_indices)

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

    consensus_map: dict[str, int | None] = {
        item: items[item].consensus_score for item in PHQ8_ITEMS
    }
    totals = compute_total_score_with_na(consensus_map)

    final_item_scores: dict[str, int] = {}
    for item in PHQ8_ITEMS:
        consensus_score = items[item].consensus_score
        final_item_scores[item] = 0 if consensus_score is None else int(consensus_score)
    final_total_score = sum(final_item_scores.values())

    return AggregatedPHQ8(
        file_id=file_id,
        condition=condition,
        items=items,
        totals=totals,
        total_mode=total_mode,
        total_expected=total_expected,
        total_std=total_std,
        total_posterior={k: float(total_posterior[k]) for k in range(25)},
        total_ci_90=total_ci_90,
        severity_bucket=severity_bucket,
        severity_bucket_phq_like=get_severity_bucket_phq_like(totals),
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
        judge_usage=None,
        prompt_version=prompt_version,
        scored_at=datetime.now(UTC),
    )
