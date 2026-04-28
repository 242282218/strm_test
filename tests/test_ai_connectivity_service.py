from __future__ import annotations

import asyncio
import os
from typing import Any
from unittest.mock import AsyncMock

import aiohttp
import pytest

from app.services import ai_connectivity_service as acs


class _FakeResponse:
    def __init__(self, status: int, body: str = "") -> None:
        self.status = status
        self._body = body

    async def text(self) -> str:
        return self._body


class _FakePostContext:
    def __init__(self, response: _FakeResponse) -> None:
        self.response = response

    async def __aenter__(self) -> _FakeResponse:
        return self.response

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False


class _FakeSession:
    def __init__(
        self,
        response: _FakeResponse | None = None,
        error: Exception | None = None,
        capture: dict[str, Any] | None = None,
    ) -> None:
        self.response = response or _FakeResponse(status=200)
        self.error = error
        self.capture = {} if capture is None else capture

    async def __aenter__(self) -> _FakeSession:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False

    def post(self, url: str, headers: dict[str, str], json: dict[str, Any]):
        self.capture["url"] = url
        self.capture["headers"] = dict(headers)
        self.capture["json"] = dict(json)
        if self.error is not None:
            raise self.error
        return _FakePostContext(self.response)


def _build_service(config_data: dict[str, Any]) -> acs.AIConnectivityService:
    service = acs.AIConnectivityService()
    providers = config_data.get("ai", {}).get("providers", [])
    service._provider_configs_getter = lambda: providers
    return service


def test_test_providers_returns_empty_when_unified_providers_missing() -> None:
    service = _build_service({})
    result = asyncio.run(service.test_providers())
    assert result == []


def test_get_provider_config_uses_unified_provider_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SMART_MEDIA_DEEPSEEK_API_KEY", "legacy-env-key")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "legacy-provider-key")
    service = _build_service(
        {
            "ai": {
                "providers": [
                    {
                        "name": "deepseek",
                        "api_key": "unified-key",
                        "base_url": "https://api.deepseek.com/v1",
                        "model": "deepseek-chat",
                        "timeout": 12,
                    }
                ]
            }
        }
    )

    config = service._get_provider_config("deepseek")

    assert config.api_key == "unified-key"
    assert config.base_url == "https://api.deepseek.com/v1"
    assert config.model == "deepseek-chat"
    assert config.timeout_seconds == 12
    assert os.getenv("SMART_MEDIA_DEEPSEEK_API_KEY") == "legacy-env-key"
    assert os.getenv("DEEPSEEK_API_KEY") == "legacy-provider-key"


def test_helper_methods_cover_timeout_and_error_formatting() -> None:
    assert acs.AIConnectivityService._first_non_empty([None, " ", "x"], fallback="z") == "x"
    assert acs.AIConnectivityService._first_non_empty([None, " "], fallback="z") == "z"
    assert acs.AIConnectivityService._normalize_base_url("https://api.test.com/") == "https://api.test.com"
    assert acs.AIConnectivityService._coerce_timeout("0") == 8
    assert acs.AIConnectivityService._coerce_timeout("999") == 60
    assert acs.AIConnectivityService._coerce_timeout("abc") == 8
    assert acs.AIConnectivityService._format_exception_message(Exception(" boom ")) == "boom"
    assert acs.AIConnectivityService._format_exception_message(TimeoutError()) == "request timeout"
    assert acs.AIConnectivityService._format_exception_message(aiohttp.ClientConnectionError()) == "connection error"
    assert acs.AIConnectivityService._format_exception_message(aiohttp.ClientPayloadError()) == "ClientPayloadError"


def test_get_provider_config_fallback_when_provider_missing() -> None:
    service = _build_service({"ai": {"providers": "not-a-list"}})

    config = service._get_provider_config("deepseek")

    assert config.provider == "deepseek"
    assert config.api_key == ""
    assert config.base_url == "https://api.deepseek.com/v1"
    assert config.timeout_seconds == 8


@pytest.mark.asyncio
async def test_test_provider_returns_not_configured_without_api_key() -> None:
    service = _build_service({"ai": {"providers": [{"name": "deepseek", "api_key": ""}]}})

    result = await service.test_provider("deepseek")

    assert result["configured"] is False
    assert result["connected"] is False
    assert result["message"] == "API key not configured"


@pytest.mark.asyncio
async def test_test_provider_success_response(monkeypatch: pytest.MonkeyPatch) -> None:
    capture: dict[str, Any] = {}
    service = _build_service(
        {
            "ai": {
                "providers": [
                    {
                        "name": "deepseek",
                        "api_key": "k",
                        "base_url": "https://api.deepseek.com/v1/",
                        "model": "deepseek-chat",
                        "timeout": 9,
                    }
                ]
            }
        }
    )
    monkeypatch.setattr(
        acs.aiohttp,
        "ClientSession",
        lambda timeout: _FakeSession(response=_FakeResponse(status=200), capture=capture),
    )

    result = await service.test_provider("deepseek")

    assert result["configured"] is True
    assert result["connected"] is True
    assert result["message"] == "ok"
    assert capture["url"] == "https://api.deepseek.com/v1/chat/completions"
    assert capture["headers"]["Authorization"] == "Bearer k"
    assert capture["json"]["messages"][0]["content"] == "ping"


@pytest.mark.asyncio
async def test_test_provider_http_failure_returns_status_text(monkeypatch: pytest.MonkeyPatch) -> None:
    service = _build_service(
        {
            "ai": {
                "providers": [
                    {
                        "name": "deepseek",
                        "api_key": "k",
                        "base_url": "https://api.deepseek.com/v1",
                        "model": "deepseek-chat",
                    }
                ]
            }
        }
    )
    monkeypatch.setattr(
        acs.aiohttp,
        "ClientSession",
        lambda timeout: _FakeSession(response=_FakeResponse(status=503, body="bad gateway")),
    )

    result = await service.test_provider("deepseek")

    assert result["connected"] is False
    assert result["message"] == "HTTP 503: bad gateway"


@pytest.mark.asyncio
async def test_test_provider_handles_exception_and_logs(monkeypatch: pytest.MonkeyPatch) -> None:
    service = _build_service(
        {
            "ai": {
                "providers": [
                    {
                        "name": "deepseek",
                        "api_key": "k",
                        "base_url": "https://api.deepseek.com/v1",
                        "model": "deepseek-chat",
                    }
                ]
            }
        }
    )
    monkeypatch.setattr(
        acs.aiohttp,
        "ClientSession",
        lambda timeout: _FakeSession(error=TimeoutError()),
    )
    warning_calls: list[tuple[Any, ...]] = []
    monkeypatch.setattr(acs.logger, "warning", lambda *args: warning_calls.append(args))

    result = await service.test_provider("deepseek")

    assert result["connected"] is False
    assert result["message"] == "request timeout"
    assert warning_calls


@pytest.mark.asyncio
async def test_test_providers_normalizes_and_deduplicates_names() -> None:
    service = _build_service({})
    service.test_provider = AsyncMock(  # type: ignore[method-assign]
        side_effect=lambda provider, timeout_seconds=None: {"provider": provider, "timeout": timeout_seconds}
    )

    result = await service.test_providers([" deepseek ", "", "deepseek", "kimi"], timeout_seconds=5)

    assert [item["provider"] for item in result] == ["deepseek", "kimi"]
    assert service.test_provider.await_count == 2  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_test_providers_uses_default_provider_names_when_not_passed() -> None:
    service = _build_service({"ai": {"providers": [{"name": "deepseek"}, {"name": "kimi"}]}})
    service.test_provider = AsyncMock(  # type: ignore[method-assign]
        side_effect=lambda provider, timeout_seconds=None: {"provider": provider}
    )

    result = await service.test_providers()

    assert [item["provider"] for item in result] == ["deepseek", "kimi"]


def test_get_ai_connectivity_service_returns_singleton(monkeypatch: pytest.MonkeyPatch) -> None:
    acs.AIConnectivityService._instance = None
    first = acs.get_ai_connectivity_service()
    second = acs.get_ai_connectivity_service()

    assert first is second
