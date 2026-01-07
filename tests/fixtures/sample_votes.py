"""Synthetic juror reports and vote scenarios for aggregation tests."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from vibe_check.constants import PHQ8_ITEMS
from vibe_check.schemas.scoring import Assertion, PHQ8ItemScore, PHQ8Report

Score = Literal[0, 1, 2, 3]


def make_item(
    score: int | None,
    assertion: Assertion,
    confidence: float = 0.8,
    evidence: list[str] | None = None,
) -> PHQ8ItemScore:
    """Factory for creating PHQ8ItemScore with NA-aware schema (SPEC-13)."""
    if assertion == "not_mentioned":
        return PHQ8ItemScore(
            discussed=False,
            score=None,
            assertion="not_mentioned",
            confidence=None,
            evidence=[],
        )
    elif assertion == "denied":
        return PHQ8ItemScore(
            discussed=True,
            score=0,
            assertion="denied",
            confidence=confidence,
            evidence=evidence if evidence else ["Patient denies symptoms"],
        )
    elif assertion == "possible":
        return PHQ8ItemScore(
            discussed=True,
            score=1,  # possible requires score=1 per SSOT Q4
            assertion="possible",
            confidence=confidence,
            evidence=evidence if evidence else ["Maybe some symptoms"],
        )
    else:  # present
        return PHQ8ItemScore(
            discussed=True,
            score=score,  # type: ignore[arg-type]
            assertion="present",
            confidence=confidence,
            evidence=evidence if evidence else ["Test evidence"],
        )


def create_mock_report(
    run_index: int,
    *,
    force_disagreement: str | None = None,
    force_disagreement_items: list[str] | None = None,
    self_harm: bool = False,
    na_item: str | None = None,
) -> PHQ8Report:
    """Create a mock PHQ8Report for testing.

    Args:
        run_index: Index (0-5) to determine model_id and run_number
        force_disagreement: Item name to force disagreement on
        force_disagreement_items: List of item names to force disagreement on
        self_harm: Whether to include self-harm mention
        na_item: Item name to mark as not_mentioned (NA)
    """
    model_ids = [
        "gpt-5.2",
        "gpt-5.2",
        "claude-sonnet-4-5-20250929",
        "claude-sonnet-4-5-20250929",
        "gemini-3-pro-preview",
        "gemini-3-pro-preview",
    ]
    run_numbers = [1, 2, 1, 2, 1, 2]

    base_scores: dict[str, Score] = {
        "anhedonia": 2,
        "depressed_mood": 1,
        "sleep": 2,
        "fatigue": 2,
        "appetite": 1,
        "guilt": 1,
        "concentration": 2,
        "psychomotor": 1,
    }

    items_to_force = []
    if force_disagreement_items is not None:
        items_to_force.extend(force_disagreement_items)
    if force_disagreement is not None:
        items_to_force.append(force_disagreement)
    for item in items_to_force:
        base_scores[item] = 0 if run_index < 3 else 3

    def make_report_item(name: str, score: Score) -> PHQ8ItemScore:
        if name == na_item:
            return make_item(None, "not_mentioned")
        # Use "denied" for score=0, "present" for 1-3
        assertion: Assertion = "denied" if score == 0 else "present"
        return make_item(score, assertion)

    report_items = {item: make_report_item(item, base_scores[item]) for item in PHQ8_ITEMS}
    total_score = sum(int(report_items[item].score or 0) for item in PHQ8_ITEMS)
    discussed_count = sum(1 for item in PHQ8_ITEMS if report_items[item].discussed)

    return PHQ8Report(
        model_id=model_ids[run_index],
        run_number=run_numbers[run_index],
        anhedonia=report_items["anhedonia"],
        depressed_mood=report_items["depressed_mood"],
        sleep=report_items["sleep"],
        fatigue=report_items["fatigue"],
        appetite=report_items["appetite"],
        guilt=report_items["guilt"],
        concentration=report_items["concentration"],
        psychomotor=report_items["psychomotor"],
        total_score=total_score,
        discussed_count=discussed_count,
        mentions_self_harm=self_harm,
        self_harm_evidence=["Test self-harm evidence"] if self_harm else [],
        scored_at=datetime.now(UTC),
    )


VoteDict = dict[str, list[int]]

UNANIMOUS_VOTES: VoteDict = {
    "anhedonia": [2, 2, 2, 2, 2, 2],
    "depressed_mood": [1, 1, 1, 1, 1, 1],
    "sleep": [2, 2, 2, 2, 2, 2],
    "fatigue": [2, 2, 2, 2, 2, 2],
    "appetite": [1, 1, 1, 1, 1, 1],
    "guilt": [1, 1, 1, 1, 1, 1],
    "concentration": [2, 2, 2, 2, 2, 2],
    "psychomotor": [1, 1, 1, 1, 1, 1],
}

HIGH_DISAGREEMENT_VOTES: VoteDict = {
    "anhedonia": [0, 0, 0, 3, 3, 3],
    "depressed_mood": [1, 1, 1, 1, 1, 1],
    "sleep": [2, 2, 2, 2, 2, 2],
    "fatigue": [2, 2, 2, 2, 2, 2],
    "appetite": [1, 1, 1, 1, 1, 1],
    "guilt": [1, 1, 1, 1, 1, 1],
    "concentration": [2, 2, 2, 2, 2, 2],
    "psychomotor": [1, 1, 1, 1, 1, 1],
}
