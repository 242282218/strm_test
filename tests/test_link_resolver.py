from unittest.mock import AsyncMock

import pytest

from app.services import link_resolver as lr


class _FakeCache:
    async def get(self, file_id: str):
        return None

    async def set(self, file_id: str, value: str, ttl: int) -> None:
        return None


def test_link_resolver_reads_runtime_alist_config(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_cache = _FakeCache()
    runtime_config = {
        "enabled": True,
        "url": "http://alist.local",
        "token": "runtime-token",
        "mount_path": "/media",
    }

    monkeypatch.setattr(lr, "get_alist_runtime_config", lambda: runtime_config)
    monkeypatch.setattr(lr, "get_link_cache_service", lambda: fake_cache)

    resolver = lr.LinkResolver()

    assert resolver.alist_config == runtime_config
    assert resolver.link_cache is fake_cache


@pytest.mark.asyncio
async def test_resolve_via_alist_uses_runtime_config(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_cache = _FakeCache()
    calls: list[tuple[str, dict[str, str], dict[str, str], int]] = []

    class _FakeResponse:
        status = 200

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            return None

        async def json(self) -> dict[str, object]:
            return {"code": 200, "data": {"raw_url": "https://download.example/video.mkv"}}

    class _FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            return None

        def post(self, api_url: str, json: dict[str, str], headers: dict[str, str], timeout: int):
            calls.append((api_url, json, headers, timeout))
            return _FakeResponse()

    monkeypatch.setattr(
        lr,
        "get_alist_runtime_config",
        lambda: {
            "enabled": True,
            "url": "http://alist.local",
            "token": "runtime-token",
            "mount_path": "/media",
        },
    )
    monkeypatch.setattr(lr, "get_link_cache_service", lambda: fake_cache)
    monkeypatch.setattr(lr.aiohttp, "ClientSession", _FakeSession)

    resolver = lr.LinkResolver(quark_service=AsyncMock())

    result = await resolver._resolve_via_alist("movies/demo.mkv")

    assert result == "https://download.example/video.mkv"
    assert calls == [
        (
            "http://alist.local/api/fs/get",
            {"path": "/media/movies/demo.mkv", "password": ""},
            {"Authorization": "runtime-token", "Content-Type": "application/json"},
            10,
        )
    ]
