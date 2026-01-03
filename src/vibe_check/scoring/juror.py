"""Juror scoring orchestration for a single model run."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from vibe_check.schemas.scoring import PHQ8Assessment, PHQ8Report, TokenUsage

if TYPE_CHECKING:
    from pydantic_ai import Agent
    from pydantic_ai.usage import RunUsage

logger = logging.getLogger(__name__)


def _token_usage_from_run_usage(usage: RunUsage | None) -> TokenUsage | None:
    if usage is None:
        return None
    input_tokens = getattr(usage, "input_tokens", None)
    output_tokens = getattr(usage, "output_tokens", None)
    reasoning_tokens = getattr(usage, "reasoning_tokens", None)
    total_tokens = getattr(usage, "total_tokens", None)
    if total_tokens is None and (input_tokens is not None or output_tokens is not None):
        total_tokens = (input_tokens or 0) + (output_tokens or 0)
    return TokenUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        reasoning_tokens=reasoning_tokens,
        total_tokens=total_tokens,
    )


class JurorScorer:
    """Score PHQ-8 for a single dialogue view with one model run."""

    def __init__(
        self,
        *,
        agent: Agent[Any, PHQ8Assessment],
        model_id: str,
        run_number: int,
        prompt_version: str,
    ) -> None:
        self._agent = agent
        self._model_id = model_id
        self._run_number = run_number
        self._prompt_version = prompt_version

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def run_number(self) -> int:
        return self._run_number

    @property
    def prompt_version(self) -> str:
        return self._prompt_version

    def _to_report(self, assessment: PHQ8Assessment, usage: TokenUsage | None) -> PHQ8Report:
        """Convert raw assessment to full report with provenance."""
        # Convert PHQ8Assessment fields to dict
        data = assessment.model_dump()

        # Add metadata
        data.update(
            {
                "model_id": self._model_id,
                "run_number": self._run_number,
                "usage": usage,
                "scored_at": datetime.now(UTC),
            }
        )

        return PHQ8Report(**data)

    def score(self, scoring_text: str) -> PHQ8Report:
        """Run the juror model synchronously and return a validated `PHQ8Report`."""
        logger.debug(
            "Juror scoring start model_id=%s run=%s text_len=%s",
            self._model_id,
            self._run_number,
            len(scoring_text),
        )
        result = self._agent.run_sync(scoring_text)

        output_data = result.data if hasattr(result, "data") else result.output

        usage = _token_usage_from_run_usage(result.usage())
        report = self._to_report(output_data, usage)

        logger.debug(
            "Juror scoring done model_id=%s run=%s total=%s",
            self._model_id,
            self._run_number,
            report.total_score,
        )
        return report

    async def ascore(self, scoring_text: str) -> PHQ8Report:
        """Run the juror model asynchronously and return a validated `PHQ8Report`."""
        logger.debug(
            "Juror scoring start (async) model_id=%s run=%s text_len=%s",
            self._model_id,
            self._run_number,
            len(scoring_text),
        )
        result = await self._agent.run(scoring_text)

        output_data = result.data if hasattr(result, "data") else result.output

        usage = _token_usage_from_run_usage(result.usage())
        report = self._to_report(output_data, usage)

        logger.debug(
            "Juror scoring done (async) model_id=%s run=%s total=%s",
            self._model_id,
            self._run_number,
            report.total_score,
        )
        return report
