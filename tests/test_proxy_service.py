from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services import proxy_service as ps


class _FakeLinkCache:
    def __init__(self) -> None:
        self.cache: dict[str, str] = {}
        self.set_calls: list[tuple[str, str, dict]] = []
        self.cleared = False
        self.stats = {"items": 0}

    async def get(self, file_id: str):
        value = self.cache.get(file_id)
        if value is None:
            return None
        return SimpleNamespace(value=value)

    async def set(self, file_id: str, value: str, headers: dict):
        self.cache[file_id] = value
        self.set_calls.append((file_id, value, headers))

    async def clear(self):
        self.cleared = True
        self.cache.clear()

    def get_stats(self):
        return self.stats


class _FakeQuarkService:
    def __init__(self, cookie: str) -> None:
        self.cookie = cookie
        self.closed = 0
        self.calls: list[str] = []
        self.fail = False

    async def get_download_link(self, file_id: str):
        self.calls.append(file_id)
        if self.fail:
            raise RuntimeError("quark error")
        return SimpleNamespace(url=f"https://download/{file_id}", headers={"h": "v"})

    async def close(self):
        self.closed += 1


@pytest.fixture
def proxy(monkeypatch: pytest.MonkeyPatch) -> tuple[ps.ProxyService, _FakeLinkCache, _FakeQuarkService]:
    cache = _FakeLinkCache()
    quark_box: dict[str, _FakeQuarkService] = {}

    def _make_quark(cookie: str):
        service = _FakeQuarkService(cookie)
        quark_box["service"] = service
        return service

    monkeypatch.setattr(ps, "QuarkService", _make_quark)
    monkeypatch.setattr(ps, "get_link_cache_service", lambda default_ttl, max_size: cache)
    if hasattr(ps.ProxyService, "_global_semaphore"):
        delattr(ps.ProxyService, "_global_semaphore")

    service = ps.ProxyService(cookie="cookie")
    return service, cache, quark_box["service"]


@pytest.mark.asyncio
async def test_redirect_uses_cache_hit(proxy: tuple[ps.ProxyService, _FakeLinkCache, _FakeQuarkService]) -> None:
    service, cache, quark = proxy
    cache.cache["fid1"] = "https://cached/fid1"

    url = await service.redirect_302("fid1")

    assert url == "https://cached/fid1"
    assert quark.calls == []


@pytest.mark.asyncio
async def test_redirect_fetches_and_caches_on_miss(proxy: tuple[ps.ProxyService, _FakeLinkCache, _FakeQuarkService]) -> None:
    service, cache, quark = proxy

    url = await service.redirect_302("fid2")

    assert url == "https://download/fid2"
    assert quark.calls == ["fid2"]
    assert cache.set_calls[0][0] == "fid2"
    assert cache.set_calls[0][1] == "https://download/fid2"


@pytest.mark.asyncio
async def test_redirect_raises_when_quark_fails(proxy: tuple[ps.ProxyService, _FakeLinkCache, _FakeQuarkService]) -> None:
    service, _cache, quark = proxy
    quark.fail = True

    with pytest.raises(RuntimeError, match="quark error"):
        await service.redirect_302("fid3")


@pytest.mark.asyncio
async def test_get_download_url_delegates_to_redirect(proxy: tuple[ps.ProxyService, _FakeLinkCache, _FakeQuarkService]) -> None:
    service, _cache, _quark = proxy

    url = await service.get_download_url("fid4")

    assert url == "https://download/fid4"


@pytest.mark.asyncio
async def test_context_manager_closes_service(proxy: tuple[ps.ProxyService, _FakeLinkCache, _FakeQuarkService]) -> None:
    service, _cache, quark = proxy

    async with service as entered:
        assert entered is service

    assert quark.closed == 1


@pytest.mark.asyncio
async def test_clear_cache_get_stats_and_close(proxy: tuple[ps.ProxyService, _FakeLinkCache, _FakeQuarkService]) -> None:
    service, cache, quark = proxy

    await service.clear_cache()
    stats = await service.get_cache_stats()
    await service.close()

    assert cache.cleared is True
    assert stats == {"items": 0}
    assert quark.closed == 1
