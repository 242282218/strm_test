from __future__ import annotations

import asyncio

import httpx
import pytest

from app.core import retry as retry_module


def test_get_retry_policy_returns_expected_defaults() -> None:
    default_policy = retry_module.get_retry_policy("default")
    tmdb_policy = retry_module.get_retry_policy("tmdb")

    assert default_policy.max_attempts >= 1
    assert default_policy.retry_exceptions
    assert httpx.HTTPStatusError in tmdb_policy.retry_exceptions


def test_get_retry_policy_rejects_unknown_policy() -> None:
    with pytest.raises(ValueError, match="Unknown retry policy"):
        retry_module.get_retry_policy("missing-policy")


@pytest.mark.asyncio
async def test_build_retry_decorator_retries_until_success() -> None:
    attempts = {"count": 0}
    policy = retry_module.RetryPolicy(
        max_attempts=3,
        multiplier=0.0,
        min_seconds=0.0,
        max_seconds=0.0,
        retry_exceptions=(retry_module.TransientError,),
    )

    @retry_module.build_retry_decorator(policy)
    async def flaky_call() -> str:
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise retry_module.TransientError("temporary")
        return "ok"

    assert await flaky_call() == "ok"
    assert attempts["count"] == 3


@pytest.mark.asyncio
async def test_retry_with_policy_uses_registered_policy(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = {"count": 0}
    custom_policy = retry_module.RetryPolicy(
        max_attempts=2,
        multiplier=0.0,
        min_seconds=0.0,
        max_seconds=0.0,
        retry_exceptions=(asyncio.TimeoutError,),
    )
    monkeypatch.setitem(retry_module._RETRY_POLICIES, "unit", custom_policy)

    @retry_module.retry_with_policy("unit")
    async def flaky_timeout() -> str:
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise asyncio.TimeoutError("slow")
        return "done"

    assert await flaky_timeout() == "done"
    assert attempts["count"] == 2
