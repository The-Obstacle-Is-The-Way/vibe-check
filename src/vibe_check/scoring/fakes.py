"""Deterministic fake scoring agents for testing/dry-runs."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, cast

from vibe_check.constants import PHQ8_ITEMS
from vibe_check.judge.schema import JudgeItemReport
from vibe_check.schemas.scoring import PHQ8ItemScore, PHQ8Report, TokenUsage

if TYPE_CHECKING:
    from vibe_check.scoring.juror import JurorScorer  # noqa: F401


def _stable_int(text: str) -> int:
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16)


Score = Literal[0, 1, 2, 3]


@dataclass(frozen=True)
class DeterministicFakeJuror:
    """A fake juror that returns deterministic scores based on hash of input."""

    model_id: str
    run_number: int

    def score(self, scoring_text: str) -> PHQ8Report:
        def make_item(item: str) -> PHQ8ItemScore:
            seed = f"{self.model_id}|{self.run_number}|{item}|{scoring_text}"
            score = cast("Score", _stable_int(seed) % 4)
            snippet = " ".join(scoring_text.strip().split()[:20]).strip()
            evidence = [snippet] if snippet else []
            return PHQ8ItemScore(
                score=score,
                confidence=0.7,
                evidence=evidence,
                insufficient_evidence=False,
            )

        items = {item: make_item(item) for item in PHQ8_ITEMS}
        total = sum(int(items[item].score) for item in PHQ8_ITEMS)

        return PHQ8Report(
            model_id=self.model_id,
            run_number=self.run_number,
            anhedonia=items["anhedonia"],
            depressed_mood=items["depressed_mood"],
            sleep=items["sleep"],
            fatigue=items["fatigue"],
            appetite=items["appetite"],
            guilt=items["guilt"],
            concentration=items["concentration"],
            psychomotor=items["psychomotor"],
            total_score=total,
            mentions_self_harm=False,
            self_harm_evidence=[],
            usage=TokenUsage(
                input_tokens=100,
                output_tokens=50,
                reasoning_tokens=10,
                total_tokens=160,
            ),
        )

    async def ascore(self, scoring_text: str) -> PHQ8Report:
        return self.score(scoring_text)


def deterministic_fake_judge_item(
    scoring_text: str,
    item: str,
    juror_reports: list[PHQ8Report],
    prompt_version: str,
) -> JudgeItemReport:
    del scoring_text, prompt_version
    votes = [int(getattr(r, item).score) for r in juror_reports]
    avg = sum(votes) / float(len(votes))
    final = cast("Score", max(0, min(3, round(avg))))
    return JudgeItemReport(
        item=item,
        final_score=final,
        confidence=0.7,
        rationale="Deterministic fake judge (mean of juror votes).",
        usage=TokenUsage(
            input_tokens=50,
            output_tokens=25,
            reasoning_tokens=5,
            total_tokens=80,
        ),
    )
