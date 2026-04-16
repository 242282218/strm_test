from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.core import rate_limiter


class DummyRequest:
    def __init__(
        self,
        headers: dict[str, str] | None = None,
        client_host: str | None = None,
        cookies: dict[str, str] | None = None,
        method: str = "GET",
    ) -> None:
        self.headers = headers or {}
        self.client = SimpleNamespace(host=client_host) if client_host else None
        self.cookies = cookies or {}
        self.method = method


@pytest.fixture(autouse=True)
def reset_rate_limiter_singleton() -> None:
    rate_limiter._default_limiter = None
    yield
    rate_limiter._default_limiter = None


@pytest.mark.asyncio
async def test_check_rate_limit_blocks_and_recovers_after_window(monkeypatch: pytest.MonkeyPatch) -> None:
    limiter = rate_limiter.RateLimiter(default_requests=2, default_seconds=10, default_block_duration=5)
    request = DummyRequest(headers={"X-Real-IP": "1.2.3.4"})
    config = rate_limiter.RateLimitConfig(requests=2, seconds=10, block_duration=5)

    monkeypatch.setattr(limiter, "_cleanup_if_needed", lambda: None)
    now_values = iter([100.0, 100.1, 100.2, 102.2, 111.0])
    monkeypatch.setattr(rate_limiter.time, "time", lambda: next(now_values))

    assert await limiter._check_rate_limit(request, config) == (True, 0, None)
    assert await limiter._check_rate_limit(request, config) == (True, 0, None)

    is_allowed, retry_after, reason = await limiter._check_rate_limit(request, config)
    assert is_allowed is False
    assert retry_after == 5
    assert "请求频率超限" in (reason or "")

    blocked = await limiter._check_rate_limit(request, config)
    assert blocked == (False, 3, "客户端已被封禁，请3秒后重试")

    assert await limiter._check_rate_limit(request, config) == (True, 0, None)


def test_get_client_id_priority_paths() -> None:
    limiter = rate_limiter.RateLimiter()

    assert limiter._get_client_id(DummyRequest(headers={"X-API-Key": "k-1"})) == "api:k-1"

    user_id = limiter._get_client_id(DummyRequest(headers={"Authorization": "Bearer token-value"}))
    assert user_id.startswith("user:")

    cookie_user_id = limiter._get_client_id(DummyRequest(cookies={"auth_token": "cookie-token"}))
    assert cookie_user_id.startswith("user:")

    forwarded = limiter._get_client_id(DummyRequest(headers={"X-Forwarded-For": "10.0.0.1, 8.8.8.8"}))
    assert forwarded == "ip:10.0.0.1"

    assert limiter._get_client_id(DummyRequest(headers={"X-Real-IP": "8.8.4.4"})) == "ip:8.8.4.4"
    assert limiter._get_client_id(DummyRequest(client_host="127.0.0.1")) == "ip:127.0.0.1"
    assert limiter._get_client_id(DummyRequest()) == "ip:unknown"


def test_cleanup_and_status_and_reset(monkeypatch: pytest.MonkeyPatch) -> None:
    limiter = rate_limiter.RateLimiter()
    limiter._client_states["expired"] = rate_limiter.ClientState(requests=[], blocked_until=0)
    limiter._client_states["active"] = rate_limiter.ClientState(requests=[10.0], blocked_until=50.0, total_requests=7)
    limiter._last_cleanup = 0

    monkeypatch.setattr(rate_limiter.time, "time", lambda: 500.0)
    limiter._cleanup_if_needed()

    assert "expired" not in limiter._client_states
    assert "active" in limiter._client_states

    status = limiter.get_client_status("active")
    assert status["requests_made"] == 1
    assert status["total_requests"] == 7
    assert status["blocked"] is False
    assert status["blocked_until"] is None
    assert status["blocked_count"] == 0

    assert limiter.get_client_status("missing") == {"requests_made": 0, "blocked": False}
    assert limiter.reset_client("active") is True
    assert limiter.reset_client("active") is False


@pytest.mark.asyncio
async def test_read_and_write_requests_use_separate_buckets(monkeypatch: pytest.MonkeyPatch) -> None:
    limiter = rate_limiter.RateLimiter(default_requests=1, default_seconds=10, default_block_duration=5)
    config = rate_limiter.RateLimitConfig(requests=1, seconds=10, block_duration=5)
    read_request = DummyRequest(cookies={"auth_token": "token"}, method="GET")
    write_request = DummyRequest(cookies={"auth_token": "token"}, method="POST")

    monkeypatch.setattr(limiter, "_cleanup_if_needed", lambda: None)
    monkeypatch.setattr(rate_limiter.time, "time", lambda: 100.0)

    assert await limiter._check_rate_limit(read_request, config) == (True, 0, None)
    assert await limiter._check_rate_limit(write_request, config) == (True, 0, None)
    assert await limiter._check_rate_limit(read_request, config) == (False, 5, "请求频率超限，已被封禁5秒")


def test_create_rate_limit_response_contract() -> None:
    limiter = rate_limiter.RateLimiter()
    response = limiter._create_rate_limit_response(12, None)

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "12"
    assert response.body


@pytest.mark.asyncio
async def test_limit_decorator_uses_custom_config(monkeypatch: pytest.MonkeyPatch) -> None:
    limiter = rate_limiter.RateLimiter(default_requests=5, default_seconds=10, default_block_duration=20)
    captured: dict[str, int] = {}

    async def fake_check(_request: Request, config: rate_limiter.RateLimitConfig):
        captured["requests"] = config.requests
        captured["seconds"] = config.seconds
        captured["block_duration"] = config.block_duration
        return False, 9, "blocked"

    monkeypatch.setattr(limiter, "_check_rate_limit", fake_check)

    @limiter.limit(requests=3, seconds=4, block_duration=8)
    async def endpoint(_request: Request):
        return {"ok": True}

    response = await endpoint(DummyRequest(headers={"X-Real-IP": "2.2.2.2"}))
    assert response.status_code == 429
    assert captured == {"requests": 3, "seconds": 4, "block_duration": 8}


@pytest.mark.asyncio
async def test_limit_decorator_allows_when_check_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    limiter = rate_limiter.RateLimiter()

    async def fake_check(_request: Request, _config: rate_limiter.RateLimitConfig):
        return True, 0, None

    monkeypatch.setattr(limiter, "_check_rate_limit", fake_check)

    @limiter.limit()
    async def endpoint(_request: Request, value: int):
        return {"value": value}

    result = await endpoint(DummyRequest(headers={"X-Real-IP": "3.3.3.3"}), value=7)
    assert result == {"value": 7}


def test_get_rate_limiter_singleton_configuration() -> None:
    limiter_a = rate_limiter.get_rate_limiter(requests=9, seconds=8, block_duration=7)
    limiter_b = rate_limiter.get_rate_limiter(requests=1, seconds=1, block_duration=1)

    assert limiter_a is limiter_b
    assert limiter_a.default_config.requests == 9
    assert limiter_a.default_config.seconds == 8
    assert limiter_a.default_config.block_duration == 7
    assert limiter_a.read_config.requests == 9
    assert limiter_a.read_config.seconds == 8
    assert limiter_a.read_config.block_duration == 7


def test_setup_rate_limiting_middleware_enforces_and_skips() -> None:
    app = FastAPI()

    @app.get("/health")
    async def health():
        return {"ok": True}

    @app.get("/ready")
    async def ready():
        return {"ok": True}

    @app.get("/limited")
    async def limited():
        return {"ok": True}

    @app.get("/api/auth/me")
    async def auth_me():
        return {"ok": True}

    limiter = rate_limiter.setup_rate_limiting(app, requests=1, seconds=60, block_duration=3)
    assert app.state.rate_limiter is limiter

    client = TestClient(app)
    first = client.get("/limited", headers={"X-Real-IP": "9.9.9.9"})
    second = client.get("/limited", headers={"X-Real-IP": "9.9.9.9"})
    skipped = client.get("/health", headers={"X-Real-IP": "9.9.9.9"})
    ready_skipped = client.get("/ready", headers={"X-Real-IP": "9.9.9.9"})
    auth_skipped = client.get("/api/auth/me", headers={"X-Real-IP": "9.9.9.9"})

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.headers["Retry-After"] == "3"
    assert skipped.status_code == 200
    assert ready_skipped.status_code == 200
    assert auth_skipped.status_code == 200


def test_setup_rate_limiting_middleware_uses_read_bucket_config() -> None:
    app = FastAPI()

    @app.get("/read")
    async def read():
        return {"ok": True}

    @app.post("/write")
    async def write():
        return {"ok": True}

    limiter = rate_limiter.setup_rate_limiting(
        app,
        requests=1,
        seconds=60,
        block_duration=3,
        read_requests=2,
        read_seconds=60,
        read_block_duration=4,
    )
    assert app.state.rate_limiter is limiter

    client = TestClient(app)
    first_read = client.get("/read", headers={"X-Real-IP": "7.7.7.7"})
    second_read = client.get("/read", headers={"X-Real-IP": "7.7.7.7"})
    third_read = client.get("/read", headers={"X-Real-IP": "7.7.7.7"})
    first_write = client.post("/write", headers={"X-Real-IP": "8.8.8.8"})
    second_write = client.post("/write", headers={"X-Real-IP": "8.8.8.8"})

    assert first_read.status_code == 200
    assert second_read.status_code == 200
    assert third_read.status_code == 429
    assert third_read.headers["Retry-After"] == "4"
    assert first_write.status_code == 200
    assert second_write.status_code == 429
    assert second_write.headers["Retry-After"] == "3"
