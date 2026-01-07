"""Arbitration profiling for scored runs (SPEC-07)."""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

from vibe_check.constants import PHQ8_ITEMS

if TYPE_CHECKING:
    from vibe_check.schemas.output import AggregatedPHQ8


class ArbitrationMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    overall_rate: float
    per_item_rates: dict[str, float]
    trigger_reasons: dict[str, int]
    judge_agreement_with_mode: float


def compute_arbitration_metrics(rows: list[AggregatedPHQ8]) -> ArbitrationMetrics:
    if not rows:
        return ArbitrationMetrics(
            overall_rate=0.0,
            per_item_rates=dict.fromkeys(PHQ8_ITEMS, 0.0),
            trigger_reasons={},
            judge_agreement_with_mode=1.0,
        )

    total = len(rows)
    arbitrated_dialogues = sum(1 for r in rows if r.triggered_arbitration)
    overall_rate = arbitrated_dialogues / float(total)

    per_item_counts: Counter[str] = Counter()
    reason_counts: Counter[str] = Counter()
    judge_mode_agree = 0
    judge_total = 0

    for row in rows:
        items_arbitrated = set(row.arbitration_items)
        if "__total__" in items_arbitrated:
            items_arbitrated = set(PHQ8_ITEMS)

        for item in items_arbitrated:
            if item in PHQ8_ITEMS:
                per_item_counts[item] += 1

        for reason_blob in row.arbitration_reasons.values():
            for part in str(reason_blob).split(";"):
                key = part.strip().split("=", 1)[0].strip()
                if key:
                    reason_counts[key] += 1

        if row.judge_resolution:
            for item, payload in row.judge_resolution.items():
                if item not in row.items:
                    continue
                mode = row.items[item].mode
                if mode is None:
                    continue
                final_score = payload.get("final_score") if isinstance(payload, dict) else None
                if final_score is None:
                    continue
                judge_total += 1
                if int(final_score) == int(mode):
                    judge_mode_agree += 1

    per_item_rates = {item: per_item_counts[item] / float(total) for item in PHQ8_ITEMS}
    judge_agreement = (judge_mode_agree / float(judge_total)) if judge_total else 1.0

    return ArbitrationMetrics(
        overall_rate=overall_rate,
        per_item_rates=per_item_rates,
        trigger_reasons=dict(reason_counts),
        judge_agreement_with_mode=judge_agreement,
    )
