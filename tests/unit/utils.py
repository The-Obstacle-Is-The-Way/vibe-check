from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from vibe_check.aggregation.aggregate import get_severity_bucket
from vibe_check.constants import PHQ8_ITEMS, SEVERITY_BUCKETS, SeverityBucket
from vibe_check.schemas.output import AggregatedPHQ8, ItemAggregationNA
from vibe_check.schemas.scoring import Assertion, PHQ8Report, PHQ8TotalScore


def make_minimal_aggregated_phq8_na(
    *,
    file_id: str = "active001",
    condition: Literal["mdd", "control"] = "mdd",
    prompt_version: str = "v2.0.0",
    base_score: int = 2,
    na_items: set[str] | None = None,
    discussed_assertion: Assertion | None = None,
) -> AggregatedPHQ8:
    """Build a deterministic minimal AggregatedPHQ8 (NA-aware) for tests.

    This helper is intentionally simple (point-mass posteriors) and is used to
    feed export/diagnostics tests without depending on live scoring.
    """
    if na_items is None:
        na_items = set()
    if base_score not in (0, 1, 2, 3):
        raise ValueError("base_score must be in {0,1,2,3}")

    if discussed_assertion is None:
        discussed_assertion = "denied" if base_score == 0 else "present"

    if discussed_assertion == "denied" and base_score != 0:
        raise ValueError("discussed_assertion='denied' requires base_score=0")
    if discussed_assertion == "possible" and base_score != 1:
        raise ValueError("discussed_assertion='possible' requires base_score=1")
    if discussed_assertion == "present" and base_score not in (1, 2, 3):
        raise ValueError("discussed_assertion='present' requires base_score in {1,2,3}")

    scored_at = datetime(2020, 1, 1, tzinfo=UTC)

    juror_reports: list[PHQ8Report] = []
    for run_number in (1, 2):
        payload: dict[str, object] = {
            "model_id": "test-model",
            "run_number": run_number,
            "mentions_self_harm": False,
            "self_harm_evidence": [],
            "scored_at": scored_at,
        }

        total_score = 0
        discussed_count = 0
        for item in PHQ8_ITEMS:
            if item in na_items:
                payload[item] = {
                    "discussed": False,
                    "score": None,
                    "assertion": "not_mentioned",
                    "confidence": None,
                    "evidence": [],
                }
            else:
                payload[item] = {
                    "discussed": True,
                    "score": base_score,
                    "assertion": discussed_assertion,
                    "confidence": 0.8,
                    "evidence": [f"Client: evidence for {item}."],
                }
                total_score += int(base_score)
                discussed_count += 1

        payload["total_score"] = total_score
        payload["discussed_count"] = discussed_count

        juror_reports.append(PHQ8Report.model_validate(payload))

    items: dict[str, ItemAggregationNA] = {}
    for item in PHQ8_ITEMS:
        if item in na_items:
            items[item] = ItemAggregationNA(
                votes=[None, None],
                assertions=["not_mentioned", "not_mentioned"],
                numeric_votes=[],
                vote_counts={str(i): 0 for i in range(4)},
                posterior=None,
                mode=None,
                expected=None,
                entropy=None,
                vote_range=None,
                clinical_prob=None,
                na_count=2,
                p_not_mentioned=1.0,
                consensus_score=None,
                consensus_assertion="not_mentioned",
                needs_arbitration=False,
                arbitration_reason=None,
            )
        else:
            vote_counts = {str(i): 0 for i in range(4)}
            vote_counts[str(base_score)] = 2
            posterior = {str(i): 0.0 for i in range(4)}
            posterior[str(base_score)] = 1.0
            items[item] = ItemAggregationNA(
                votes=[base_score, base_score],
                assertions=[discussed_assertion, discussed_assertion],
                numeric_votes=[base_score, base_score],
                vote_counts=vote_counts,
                posterior=posterior,
                mode=base_score,
                expected=float(base_score),
                entropy=0.0,
                vote_range=0,
                clinical_prob=(1.0 if base_score >= 2 else 0.0),
                na_count=0,
                p_not_mentioned=0.0,
                consensus_score=base_score,
                consensus_assertion=discussed_assertion,
                needs_arbitration=False,
                arbitration_reason=None,
            )

    totals = PHQ8TotalScore.from_item_scores(
        {item: (None if item in na_items else base_score) for item in PHQ8_ITEMS}
    )

    final_item_scores = {item: (0 if item in na_items else int(base_score)) for item in PHQ8_ITEMS}
    final_total_score = sum(final_item_scores.values())

    severity_bucket: SeverityBucket = get_severity_bucket(final_total_score)
    severity_bucket_probs: dict[str, float] = {
        str(k): (1.0 if k == severity_bucket else 0.0) for k in SEVERITY_BUCKETS
    }

    severity_bucket_phq_like: SeverityBucket | None = None
    if totals.is_proration_valid and totals.prorated_total_rounded is not None:
        severity_bucket_phq_like = get_severity_bucket(int(totals.prorated_total_rounded))

    total_posterior = dict.fromkeys(range(25), 0.0)
    total_posterior[final_total_score] = 1.0

    return AggregatedPHQ8(
        file_id=file_id,
        condition=condition,
        items=items,
        totals=totals,
        total_mode=final_total_score,
        total_expected=float(final_total_score),
        total_std=0.0,
        total_posterior=total_posterior,
        total_ci_90=(final_total_score, final_total_score),
        severity_bucket=severity_bucket,
        severity_bucket_phq_like=severity_bucket_phq_like,
        severity_bucket_probs=severity_bucket_probs,
        final_item_scores=final_item_scores,
        final_total_score=final_total_score,
        final_severity_bucket=severity_bucket,
        final_source="jury_mode",
        triggered_arbitration=False,
        arbitration_items=[],
        arbitration_reasons={},
        mentions_self_harm=False,
        self_harm_evidence=[],
        juror_reports=juror_reports,
        judge_resolution=None,
        judge_usage=None,
        prompt_version=prompt_version,
        scored_at=scored_at,
    )
