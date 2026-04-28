from __future__ import annotations

import time
from typing import Any

import pytest

from app.services import link_cache


class FakeCacheManager:
    def __init__(self) -> None:
        self.store: dict[tuple[Any, str], Any] = {}
        self.set_calls: list[tuple[Any, str, Any, int | None]] = []
        self.delete_calls: list[tuple[Any, str]] = []
        self.clear_calls: list[Any] = []
        self._stats = {"hits": 1}

    def get_namespace_config(self, _namespace: Any) -> dict[str, int]:
        return {"default_ttl": 33, "max_size": 77}

    async def get(self, namespace: Any, key: str) -> Any:
        return self.store.get((namespace, key))

    async def set(self, namespace: Any, key: str, value: Any, ttl: int | None = None) -> None:
        self.set_calls.append((namespace, key, value, ttl))
        self.store[(namespace, key)] = value

    async def delete(self, namespace: Any, key: str) -> bool:
        self.delete_calls.append((namespace, key))
        return self.store.pop((namespace, key), None) is not None

    async def clear_namespace(self, namespace: Any) -> None:
        self.clear_calls.append(namespace)
        keys = [item for item in self.store if item[0] == namespace]
        for key in keys:
            del self.store[key]

    def get_namespace_stats(self, _namespace: Any) -> dict[str, Any]:
        return dict(self._stats)


@pytest.fixture(autouse=True)
def reset_link_cache_globals() -> None:
    link_cache._global_link_cache = None
    original_mode = link_cache.CACHE_LEGACY_MODE
    yield
    link_cache._global_link_cache = None
    link_cache.CACHE_LEGACY_MODE = original_mode


def test_cache_entry_touch_expiry_and_to_dict() -> None:
    entry = link_cache.CacheEntry(key="k", value={"v": 1}, headers={"h": "x"}, ttl=60)
    assert entry.is_expired() is False

    entry.touch()
    data = entry.to_dict()
    assert data["key"] == "k"
    assert data["headers"] == {"h": "x"}
    assert data["access_count"] == 1
    assert "T" in data["created_at"]
    assert "T" in data["expires_at"]

    entry.expires_at = time.time() - 1
    assert entry.is_expired() is True


@pytest.mark.asyncio
async def test_legacy_get_set_delete_and_expired_path() -> None:
    cache = link_cache.LinkCacheLegacy(default_ttl=10, max_size=5)

    await cache.set("file-1", "value-1", headers={"x": "1"}, user="demo")
    key = cache._generate_cache_key("file-1", user="demo")
    assert key == "file-1:user=demo"

    hit = await cache.get("file-1", user="demo")
    assert hit is not None
    assert hit.value == "value-1"
    assert hit.headers == {"x": "1"}
    assert hit.access_count == 1

    await cache.set("file-expired", "value-expired", ttl=1)
    expired_key = cache._generate_cache_key("file-expired")
    cache._cache[expired_key].expires_at = time.time() - 1
    assert await cache.get("file-expired") is None

    assert await cache.delete("file-1", user="demo") is True
    assert await cache.delete("file-1", user="demo") is False


@pytest.mark.asyncio
async def test_legacy_evict_oldest_when_capacity_reached() -> None:
    cache = link_cache.LinkCacheLegacy(default_ttl=30, max_size=2)

    await cache.set("a", "A")
    await cache.set("b", "B")
    cache._cache["a"].last_accessed_at = 1.0
    cache._cache["b"].last_accessed_at = 2.0

    await cache.set("c", "C")

    assert len(cache._cache) == 2
    assert "a" not in cache._cache
    assert "b" in cache._cache
    assert "c" in cache._cache


@pytest.mark.asyncio
async def test_legacy_cleanup_stats_and_clear() -> None:
    cache = link_cache.LinkCacheLegacy(default_ttl=30, max_size=10)
    await cache.set("a", "A")
    await cache.set("b", "B")
    cache._cache["a"].expires_at = time.time() - 1
    cache._cache["b"].access_count = 3

    stats_before = cache.get_stats()
    assert stats_before["total_entries"] == 2
    assert stats_before["expired_entries"] == 1
    assert stats_before["total_access_count"] == 3
    assert stats_before["mode"] == "legacy"

    await cache._cleanup_expired()
    assert "a" not in cache._cache
    await cache.clear()
    assert cache.get_stats()["total_entries"] == 0


@pytest.mark.asyncio
async def test_legacy_cleanup_loop_and_start_stop(monkeypatch: pytest.MonkeyPatch) -> None:
    cache = link_cache.LinkCacheLegacy(default_ttl=30, max_size=1, cleanup_interval=0)
    cache._cache["k1"] = link_cache.CacheEntry(key="k1", value="v1")
    cache._cache["k2"] = link_cache.CacheEntry(key="k2", value="v2")

    calls: list[str] = []

    async def fake_sleep(_seconds: int) -> None:
        cache._running = False

    async def fake_cleanup() -> None:
        calls.append("cleanup")

    async def fake_evict() -> None:
        calls.append("evict")

    monkeypatch.setattr(link_cache.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(cache, "_cleanup_expired", fake_cleanup)
    monkeypatch.setattr(cache, "_evict_oldest", fake_evict)

    cache._running = True
    await cache._cleanup_loop()
    assert calls == ["cleanup", "evict"]

    await cache.start()
    await cache.start()
    assert cache._running is True
    assert cache._cleanup_task is not None

    await cache.stop()
    assert cache._running is False
    await cache.stop()


@pytest.mark.asyncio
async def test_unified_cache_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_manager = FakeCacheManager()
    monkeypatch.setattr("app.core.cache_manager.get_cache_manager", lambda: fake_manager)

    cache = link_cache.LinkCacheUnified(default_ttl=5, max_size=6)
    assert cache.default_ttl == 33
    assert cache.max_size == 77

    await cache.set("f1", "v1", headers={"h": "1"}, quality="hd")
    set_call = fake_manager.set_calls[-1]
    assert set_call[1] == "f1:quality=hd"
    assert isinstance(set_call[2], link_cache.CacheEntry)

    key = cache._generate_cache_key("f1", quality="hd")
    fake_manager.store[(cache._namespace, key)] = set_call[2]
    hit = await cache.get("f1", quality="hd")
    assert isinstance(hit, link_cache.CacheEntry)
    assert hit.access_count == 1

    await cache.set("f2", "v2")
    wrapped = await cache.get("f2")
    assert isinstance(wrapped, link_cache.CacheEntry)
    assert wrapped.value == "v2"
    assert wrapped.ttl == 33

    assert await cache.delete("f2") is True
    assert await cache.delete("f2") is False
    assert await cache.get("missing") is None

    await cache.start()
    await cache.start()
    assert cache._running is True
    await cache.stop()
    assert cache._running is False

    await cache.clear()
    stats = cache.get_stats()
    assert stats["mode"] == "unified"
    assert stats["default_ttl"] == 33
    assert stats["max_size"] == 77


def test_get_link_cache_service_factory_modes(monkeypatch: pytest.MonkeyPatch) -> None:
    link_cache.CACHE_LEGACY_MODE = True
    legacy = link_cache.get_link_cache_service(default_ttl=11, max_size=12, cleanup_interval=13)
    assert isinstance(legacy, link_cache.LinkCacheLegacy)
    assert link_cache.get_link_cache_service() is legacy

    link_cache._global_link_cache = None
    link_cache.CACHE_LEGACY_MODE = False
    fake_manager = FakeCacheManager()
    monkeypatch.setattr("app.core.cache_manager.get_cache_manager", lambda: fake_manager)
    unified = link_cache.get_link_cache_service(default_ttl=1, max_size=2, cleanup_interval=3)
    assert isinstance(unified, link_cache.LinkCacheUnified)
    assert link_cache.get_link_cache_service() is unified


def test_get_link_cache_returns_legacy_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_manager = object()
    monkeypatch.setattr(link_cache, "get_cache_manager", lambda: fake_manager)

    adapter = link_cache.get_link_cache()
    assert adapter.cache_manager is fake_manager
    assert adapter.cache_type == "link"
    assert adapter.namespace == link_cache.CacheNamespace.LINK
