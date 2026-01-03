from __future__ import annotations

import pytest
from aiolimiter import AsyncLimiter

from vibe_check.resilience import ProviderRateLimiters, _is_transient_error, with_retry
from vibe_check.settings import Settings


def test_is_transient_error_true_for_timeout() -> None:
    assert _is_transient_error(TimeoutError("timeout")) is True


def test_is_transient_error_false_for_value_error() -> None:
    assert _is_transient_error(ValueError("nope")) is False


def test_is_transient_error_true_for_ratelimit_name() -> None:
    class RateLimitError(Exception):
        pass

    assert _is_transient_error(RateLimitError("rate limit")) is True


def test_provider_rate_limiters_selects_correct_limiter_and_rpm() -> None:
    settings = Settings(openai_rpm=101, anthropic_rpm=61, google_rpm=99)
    limiters = ProviderRateLimiters(settings)

    openai = limiters.get_limiter("openai:gpt-5.2")
    openai2 = limiters.get_limiter("gpt-5.2")
    anthropic = limiters.get_limiter("anthropic:claude-sonnet-4-5-20250929")
    google = limiters.get_limiter("google-gla:gemini-3-pro-preview")

    assert isinstance(openai, AsyncLimiter)
    assert openai is openai2
    assert openai is not anthropic
    assert google is not anthropic

    assert limiters.get_rpm("gpt-5.2") == 101
    assert limiters.get_rpm("claude-sonnet-4-5-20250929") == 61
    assert limiters.get_rpm("gemini-3-pro-preview") == 99


@pytest.mark.asyncio
async def test_with_retry_retries_on_transient_error() -> None:
    calls = {"count": 0}

    @with_retry(max_attempts=3, initial_wait=0.0, max_wait=0.0, jitter=0.0)
    async def flaky() -> str:
        calls["count"] += 1
        if calls["count"] < 2:
            raise TimeoutError("transient")
        return "ok"

    assert await flaky() == "ok"
    assert calls["count"] == 2


@pytest.mark.asyncio
async def test_with_retry_does_not_retry_on_non_transient_error() -> None:
    calls = {"count": 0}

    @with_retry(max_attempts=3, initial_wait=0.0, max_wait=0.0, jitter=0.0)
    async def bad() -> str:
        calls["count"] += 1
        raise ValueError("non-transient")

    with pytest.raises(ValueError, match="non-transient"):
        await bad()
    assert calls["count"] == 1
