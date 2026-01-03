"""Synthetic juror reports and vote scenarios for aggregation tests."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from vibe_check.schemas.scoring import PHQ8ItemScore, PHQ8Report

Score = Literal[0, 1, 2, 3]


def create_mock_report(
    run_index: int,
    *,
    force_disagreement: str | None = None,
    force_disagreement_items: list[str] | None = None,
    self_harm: bool = False,
    insufficient_evidence_item: str | None = None,
) -> PHQ8Report:
    model_ids = [
        "gpt-5.2",
        "gpt-5.2",
        "claude-sonnet",
        "claude-sonnet",
        "gemini-pro",
        "gemini-pro",
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

    def make_item(name: str, score: Score) -> PHQ8ItemScore:
        return PHQ8ItemScore(
            score=score,
            confidence=0.8,
            evidence=["Test evidence"],
            insufficient_evidence=(name == insufficient_evidence_item),
        )

    return PHQ8Report(
        model_id=model_ids[run_index],
        run_number=run_numbers[run_index],
        anhedonia=make_item("anhedonia", base_scores["anhedonia"]),
        depressed_mood=make_item("depressed_mood", base_scores["depressed_mood"]),
        sleep=make_item("sleep", base_scores["sleep"]),
        fatigue=make_item("fatigue", base_scores["fatigue"]),
        appetite=make_item("appetite", base_scores["appetite"]),
        guilt=make_item("guilt", base_scores["guilt"]),
        concentration=make_item("concentration", base_scores["concentration"]),
        psychomotor=make_item("psychomotor", base_scores["psychomotor"]),
        total_score=sum(base_scores.values()),
        mentions_self_harm=self_harm,
        self_harm_evidence=["Test self-harm evidence"] if self_harm else [],
        scored_at=datetime.utcnow(),
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
