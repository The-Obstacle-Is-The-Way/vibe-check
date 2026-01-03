"""Factory for creating scoring actors (real or fake).

Wires up rate limiting and retry configuration (ADR-001) when building real jurors.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from vibe_check.resilience import ProviderRateLimiters
from vibe_check.scoring.agent import build_juror_agent
from vibe_check.scoring.fakes import DeterministicFakeJuror, deterministic_fake_judge_item
from vibe_check.scoring.juror import JurorScorer
from vibe_check.scoring.usage import token_usage_from_run_usage

if TYPE_CHECKING:
    from collections.abc import Sequence

    from vibe_check.judge.schema import JudgeItemReport, JudgeItemResolution
    from vibe_check.schemas.scoring import PHQ8Report
    from vibe_check.settings import Settings


class Juror(Protocol):
    """Protocol for PHQ-8 scoring agents."""

    def score(self, scoring_text: str) -> PHQ8Report:
        """Synchronous scoring (for simple use cases)."""
        ...

    async def ascore(self, scoring_text: str) -> PHQ8Report:
        """Async scoring with full resilience (for production)."""
        ...


class JudgeItemFn(Protocol):
    """Protocol for judge arbitration functions."""

    def __call__(
        self,
        scoring_text: str,
        item: str,
        juror_reports: list[PHQ8Report],
        prompt_version: str,
    ) -> JudgeItemReport:
        """Resolve a single contested item."""
        ...


def build_fake_jury(
    models: list[str] | None = None,
    runs_per_model: int = 2,
) -> Sequence[Juror]:
    """Build a list of deterministic fake jurors."""
    if models is None:
        models = ["gpt-5.2", "claude-sonnet-4-5-20250929", "gemini-3-pro-preview"]
    jurors: list[Juror] = []
    for model_id in models:
        for run_no in range(1, runs_per_model + 1):
            jurors.append(DeterministicFakeJuror(model_id, run_no))
    return jurors


def build_fake_judge_item() -> JudgeItemFn:
    """Return the deterministic fake judge function."""
    return deterministic_fake_judge_item


def build_real_jury(
    settings: Settings,
    *,
    prompt_version: str,
    dialogue_view: str,
) -> Sequence[Juror]:
    """Build a list of real PydanticAI-backed jurors.

    Args:
        settings: Configuration for models, rate limits, and retry behavior.
        prompt_version: Prompt version to embed in agent system prompts (from CLI).
        dialogue_view: Dialogue view name for scoring context (from CLI).

    Wires up ADR-001's three-layer resilience strategy:
    - Layer 1: PydanticAI validation retries (via settings.validation_retries)
    - Layer 2: Tenacity transient retry (via settings.max_retries, etc.)
    - Layer 3: Aiolimiter rate limiting (via per-provider RPM settings)

    Note (BUG-027 fix): prompt_version and dialogue_view are now explicit params
    to ensure CLI args flow through to agent prompts, not Settings defaults.
    """
    # PydanticAI provider prefixes: openai, anthropic, google-gla (not "google")
    configs = [
        ("openai", settings.juror_gpt_model),
        ("anthropic", settings.juror_claude_model),
        ("google-gla", settings.juror_gemini_model),
    ]

    # Create rate limiters for all providers
    rate_limiters = ProviderRateLimiters(settings)

    jurors: list[Juror] = []

    for provider, model_id in configs:
        # PydanticAI model identifier e.g. "openai:gpt-5.2"
        full_model_name = f"{provider}:{model_id}"

        # Get the rate limiter for this provider
        limiter = rate_limiters.get_limiter(full_model_name)

        for run_no in range(1, settings.runs_per_model + 1):
            agent = build_juror_agent(
                model=full_model_name,
                prompt_version=prompt_version,
                view_name=dialogue_view,
                retries=settings.validation_retries,
            )
            scorer = JurorScorer(
                agent=agent,
                model_id=model_id,
                run_number=run_no,
                prompt_version=prompt_version,
                rate_limiter=limiter,
                max_retries=settings.max_retries,
                retry_initial_wait=settings.retry_initial_wait,
                retry_max_wait=settings.retry_max_wait,
                retry_jitter=settings.retry_jitter,
            )
            jurors.append(scorer)

    return jurors


def build_real_judge_item(
    settings: Settings,
    *,
    prompt_version: str,
) -> JudgeItemFn:
    """Build a real judge function backed by an Agent.

    Args:
        settings: Configuration for model, retry behavior.
        prompt_version: Prompt version to embed in agent system prompt (from CLI).

    Wires up ADR-001's resilience strategy:
    - Layer 1: PydanticAI validation retries (via settings.validation_retries)
    - Layer 2: Tenacity transient retry (via settings.max_retries, etc.)

    Note: Layer 3 (rate limiting) is omitted for the judge because:
    - Judge calls are infrequent relative to juror calls (only on arbitration)
    - The judge is called synchronously, making async rate limiting complex
    - Transient retry (Layer 2) handles 429s when they occur

    Note (BUG-027 fix): prompt_version is now an explicit param to ensure CLI args
    flow through to agent prompts, not Settings defaults.
    """
    from typing import cast

    from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential_jitter

    from vibe_check.judge.agent import build_judge_agent
    from vibe_check.judge.prompting import build_judge_item_prompt
    from vibe_check.judge.schema import JudgeItemReport
    from vibe_check.resilience import _is_transient_error

    full_model_name = f"anthropic:{settings.judge_model}"

    # Layer 1: PydanticAI validation retries
    agent = build_judge_agent(
        model=full_model_name,
        prompt_version=prompt_version,
        retries=settings.validation_retries,
    )

    # Capture retry settings at build time
    max_retries = settings.max_retries
    retry_initial_wait = settings.retry_initial_wait
    retry_max_wait = settings.retry_max_wait
    retry_jitter = settings.retry_jitter

    def judge_fn(
        scoring_text: str,
        item: str,
        juror_reports: list[PHQ8Report],
        prompt_version: str,
    ) -> JudgeItemReport:
        _ = prompt_version
        evidence_pool: list[str] = []
        votes: list[int] = []
        for r in juror_reports:
            item_score = getattr(r, item)
            votes.append(int(item_score.score))
            evidence_pool.extend(item_score.evidence)

        prompt = build_judge_item_prompt(
            scoring_text=scoring_text,
            item=item,
            juror_votes=votes,
            juror_evidence=evidence_pool,
        )

        # Layer 2: Tenacity transient retry with exponential backoff
        @retry(
            stop=stop_after_attempt(max_retries),
            wait=wait_exponential_jitter(
                initial=retry_initial_wait,
                max=retry_max_wait,
                jitter=retry_jitter,
            ),
            retry=retry_if_exception(_is_transient_error),
            reraise=True,
        )
        def _call_with_retry() -> JudgeItemReport:
            result = agent.run_sync(prompt)
            # PydanticAI v1+ puts structured output in .data
            output = getattr(result, "data", getattr(result, "output", None))
            resolution = cast("JudgeItemResolution", output)
            usage = token_usage_from_run_usage(result.usage())
            return JudgeItemReport(**resolution.model_dump(), usage=usage)

        return _call_with_retry()

    return judge_fn
