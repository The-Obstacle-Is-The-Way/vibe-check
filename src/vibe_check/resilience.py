"""Rate limiting and retry utilities for LLM API calls (ADR-001).

This module implements a three-layer resilience strategy:
1. PydanticAI validation retries (handled in agent.py)
2. Tenacity transient retry (for 429, 5xx, network errors)
3. Aiolimiter rate limiting (proactive throttling per provider)
"""

from __future__ import annotations

import logging
from functools import wraps
from typing import TYPE_CHECKING, ParamSpec, TypeVar

from aiolimiter import AsyncLimiter
from tenacity import (
    RetryCallState,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

from vibe_check.constants import DEFAULT_RPM_FALLBACK

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from vibe_check.settings import Settings

logger = logging.getLogger(__name__)

P = ParamSpec("P")
T = TypeVar("T")


def _is_transient_error(exc: BaseException) -> bool:
    """Check if an exception is a transient error worth retrying.

    Handles:
    - HTTP 429 (rate limit) and 5xx (server errors)
    - Network/connection errors
    - Timeouts
    """
    # httpx errors
    try:
        from httpx import HTTPStatusError, NetworkError, TimeoutException

        if isinstance(exc, NetworkError | TimeoutException):
            return True
        if isinstance(exc, HTTPStatusError):
            return exc.response.status_code in (429, 500, 502, 503, 504)
    except ImportError:
        pass

    # httpcore errors (underlying httpx)
    try:
        from httpcore import NetworkError as HCNetworkError
        from httpcore import TimeoutException as HCTimeoutException

        if isinstance(exc, HCNetworkError | HCTimeoutException):
            return True
    except ImportError:
        pass

    # Standard library
    if isinstance(exc, TimeoutError | ConnectionError | OSError):
        # OSError includes things like "Connection refused"
        return True

    # openai/anthropic SDK errors
    exc_name = type(exc).__name__.lower()
    transient_patterns = ("ratelimit", "timeout", "connection", "overload", "server")
    return any(pattern in exc_name for pattern in transient_patterns)


def _log_retry(retry_state: RetryCallState) -> None:
    """Log retry attempts for debugging."""
    exc = retry_state.outcome.exception() if retry_state.outcome else None
    logger.warning(
        "Retry attempt %d after error: %s",
        retry_state.attempt_number,
        exc,
    )


def with_retry(
    max_attempts: int = 5,
    initial_wait: float = 1.0,
    max_wait: float = 60.0,
    jitter: float = 5.0,
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    """Decorator for async functions with exponential backoff retry.

    Args:
        max_attempts: Maximum number of retry attempts (default: 5)
        initial_wait: Initial wait time in seconds (default: 1.0)
        max_wait: Maximum wait time in seconds (default: 60.0)
        jitter: Random jitter to add to wait time (default: 5.0)

    Returns:
        Decorated function with retry behavior.
    """

    def decorator(fn: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        @retry(
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential_jitter(initial=initial_wait, max=max_wait, jitter=jitter),
            retry=retry_if_exception(_is_transient_error),
            before_sleep=_log_retry,
            reraise=True,
        )
        @wraps(fn)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            return await fn(*args, **kwargs)

        return wrapper

    return decorator


class ProviderRateLimiters:
    """Per-provider rate limiters using aiolimiter.

    Uses a token bucket algorithm that continuously replenishes capacity
    up to the maximum RPM limit, matching Anthropic's rate limiting behavior.
    """

    def __init__(self, settings: Settings) -> None:
        """Initialize rate limiters from settings.

        Args:
            settings: Application settings with RPM values per provider.
        """
        # AsyncLimiter(max_rate, time_period) - requests per time_period seconds
        self._openai = AsyncLimiter(settings.openai_rpm, 60.0)
        self._anthropic = AsyncLimiter(settings.anthropic_rpm, 60.0)
        self._google = AsyncLimiter(settings.google_rpm, 60.0)

        # Store settings for logging
        self._rpm = {
            "openai": settings.openai_rpm,
            "anthropic": settings.anthropic_rpm,
            "google": settings.google_rpm,
        }

    def get_limiter(self, model_id: str) -> AsyncLimiter:
        """Get the appropriate rate limiter for a model.

        Args:
            model_id: The model identifier (e.g., "openai:gpt-5.2" or "gpt-5.2")

        Returns:
            The AsyncLimiter for the model's provider.

        Raises:
            ValueError: If the provider cannot be determined from model_id.
        """
        model_lower = model_id.lower()

        # Check for PydanticAI-style prefixes first
        if model_lower.startswith("openai:") or "gpt" in model_lower:
            return self._openai
        if model_lower.startswith("anthropic:") or "claude" in model_lower:
            return self._anthropic
        if model_lower.startswith("google") or "gemini" in model_lower:
            return self._google

        raise ValueError(f"Cannot determine provider for model: {model_id}")

    def get_rpm(self, model_id: str) -> int:
        """Get the RPM limit for a model's provider.

        Args:
            model_id: The model identifier.

        Returns:
            The requests per minute limit.
        """
        model_lower = model_id.lower()
        if "gpt" in model_lower or model_lower.startswith("openai:"):
            return self._rpm["openai"]
        if "claude" in model_lower or model_lower.startswith("anthropic:"):
            return self._rpm["anthropic"]
        if "gemini" in model_lower or model_lower.startswith("google"):
            return self._rpm["google"]
        return DEFAULT_RPM_FALLBACK  # Conservative default


# Singleton instance for fake mode (no-op limiter)
class _NoOpLimiter:
    """No-op rate limiter for fake/test mode."""

    async def __aenter__(self) -> _NoOpLimiter:
        return self

    async def __aexit__(self, *args: object) -> None:
        pass


NO_OP_LIMITER = _NoOpLimiter()
