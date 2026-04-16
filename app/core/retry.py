"""
Unified retry policy
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import aiohttp
import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.constants import (
    RETRY_MAX_ATTEMPTS,
    RETRY_MAX_SECONDS,
    RETRY_MIN_SECONDS,
    RETRY_MULTIPLIER,
)


class TransientError(Exception):
    """Retryable transient error"""


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    max_attempts: int
    multiplier: float
    min_seconds: float
    max_seconds: float
    retry_exceptions: tuple[type[BaseException], ...]


_RETRY_POLICIES: dict[str, RetryPolicy] = {
    "default": RetryPolicy(
        max_attempts=RETRY_MAX_ATTEMPTS,
        multiplier=RETRY_MULTIPLIER,
        min_seconds=RETRY_MIN_SECONDS,
        max_seconds=RETRY_MAX_SECONDS,
        retry_exceptions=(aiohttp.ClientError, asyncio.TimeoutError, TransientError),
    ),
    "tmdb": RetryPolicy(
        max_attempts=3,
        multiplier=1.0,
        min_seconds=2.0,
        max_seconds=10.0,
        retry_exceptions=(httpx.HTTPStatusError, httpx.RequestError, asyncio.TimeoutError, TransientError),
    ),
}


def get_retry_policy(name: str = "default") -> RetryPolicy:
    key = (name or "default").strip().lower()
    if key not in _RETRY_POLICIES:
        raise ValueError(f"Unknown retry policy: {name}")
    return _RETRY_POLICIES[key]


def build_retry_decorator(policy: RetryPolicy):
    return retry(
        stop=stop_after_attempt(policy.max_attempts),
        wait=wait_exponential(
            multiplier=policy.multiplier,
            min=policy.min_seconds,
            max=policy.max_seconds,
        ),
        retry=retry_if_exception_type(policy.retry_exceptions),
        reraise=True,
    )


def retry_with_policy(name: str = "default"):
    return build_retry_decorator(get_retry_policy(name))


def retry_on_transient():
    """Return retry decorator for default transient failures."""
    return retry_with_policy("default")


def retry_on_tmdb():
    """Return retry decorator for TMDB HTTP failures."""
    return retry_with_policy("tmdb")
