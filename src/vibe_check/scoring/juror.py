"""Juror scoring orchestration for a single model run.

Implements Layer 2 (transient retry) and Layer 3 (rate limiting) of ADR-001's
three-layer resilience strategy. Layer 1 (validation retry) is handled by
PydanticAI's built-in `retries` parameter in the Agent.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from vibe_check.resilience import NO_OP_LIMITER, with_retry
from vibe_check.schemas.scoring import PHQ8Assessment, PHQ8Report, TokenUsage
from vibe_check.scoring.usage import token_usage_from_run_usage

if TYPE_CHECKING:
    from aiolimiter import AsyncLimiter
    from pydantic_ai import Agent

logger = logging.getLogger(__name__)


class JurorScorer:
    """Score PHQ-8 for a single dialogue view with one model run.

    Implements ADR-001's three-layer resilience strategy:
    - Layer 1: PydanticAI validation retries (configured in Agent)
    - Layer 2: Tenacity transient retry (for 429, 5xx, network errors)
    - Layer 3: Aiolimiter rate limiting (proactive throttling)
    """

    def __init__(
        self,
        *,
        agent: Agent[Any, PHQ8Assessment],
        model_id: str,
        run_number: int,
        prompt_version: str,
        rate_limiter: AsyncLimiter | None = None,
        max_retries: int = 5,
        retry_initial_wait: float = 1.0,
        retry_max_wait: float = 60.0,
        retry_jitter: float = 5.0,
    ) -> None:
        self._agent = agent
        self._model_id = model_id
        self._run_number = run_number
        self._prompt_version = prompt_version
        self._rate_limiter: AsyncLimiter | Any = rate_limiter or NO_OP_LIMITER
        self._max_retries = max_retries
        self._retry_initial_wait = retry_initial_wait
        self._retry_max_wait = retry_max_wait
        self._retry_jitter = retry_jitter

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

        usage = token_usage_from_run_usage(result.usage())
        report = self._to_report(output_data, usage)

        logger.debug(
            "Juror scoring done model_id=%s run=%s total=%s",
            self._model_id,
            self._run_number,
            report.total_score,
        )
        return report

    async def ascore(self, scoring_text: str) -> PHQ8Report:
        """Run the juror model asynchronously and return a validated `PHQ8Report`.

        This method implements ADR-001's three-layer resilience:
        - Layer 3: Rate limiting via aiolimiter (proactive)
        - Layer 2: Transient retry via tenacity (reactive)
        - Layer 1: Validation retry via PydanticAI (internal to agent)
        """
        logger.debug(
            "Juror scoring start (async) model_id=%s run=%s text_len=%s",
            self._model_id,
            self._run_number,
            len(scoring_text),
        )

        # Layer 2: Create retry-wrapped call function
        @with_retry(
            max_attempts=self._max_retries,
            initial_wait=self._retry_initial_wait,
            max_wait=self._retry_max_wait,
            jitter=self._retry_jitter,
        )
        async def _call_with_retry() -> Any:
            return await self._agent.run(scoring_text)

        # Layer 3: Rate limiting (proactive throttling)
        async with self._rate_limiter:
            result = await _call_with_retry()

        output_data = result.data if hasattr(result, "data") else result.output

        usage = token_usage_from_run_usage(result.usage())
        report = self._to_report(output_data, usage)

        logger.debug(
            "Juror scoring done (async) model_id=%s run=%s total=%s",
            self._model_id,
            self._run_number,
            report.total_score,
        )
        return report
