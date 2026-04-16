import builtins
import json
import sys
import types
from unittest.mock import AsyncMock

import pytest

from app.core import redis_cache as redis_cache_mod


class FakeRedisClient:
    def __init__(self):
        self.store: dict[str, str] = {}
        self.raise_on: dict[str, Exception] = {}
        self.last_setex: tuple[str, int, str] | None = None
        self.closed = False
        self.delete_calls: list[tuple[str, ...]] = []

    async def ping(self) -> bool:
        if "ping" in self.raise_on:
            raise self.raise_on["ping"]
        return True

    async def close(self) -> None:
        self.closed = True

    async def get(self, key: str) -> str | None:
        if "get" in self.raise_on:
            raise self.raise_on["get"]
        return self.store.get(key)

    async def setex(self, key: str, ttl: int, value: str) -> None:
        if "setex" in self.raise_on:
            raise self.raise_on["setex"]
        self.last_setex = (key, ttl, value)
        self.store[key] = value

    async def delete(self, *keys: str) -> int:
        if "delete" in self.raise_on:
            raise self.raise_on["delete"]
        self.delete_calls.append(tuple(keys))
        deleted = 0
        for key in keys:
            if key in self.store:
                deleted += 1
                del self.store[key]
        return deleted

    async def exists(self, key: str) -> int:
        if "exists" in self.raise_on:
            raise self.raise_on["exists"]
        return 1 if key in self.store else 0

    async def scan_iter(self, match: str):
        if "scan_iter" in self.raise_on:
            raise self.raise_on["scan_iter"]

        for key in list(self.store.keys()):
            if match.endswith("*"):
                if key.startswith(match[:-1]):
                    yield key
            elif key == match:
                yield key


@pytest.fixture(autouse=True)
def reset_cache_singleton():
    redis_cache_mod._cache_instance = None
    yield
    redis_cache_mod._cache_instance = None


@pytest.mark.asyncio
async def test_connect_and_disconnect_success(monkeypatch):
    fake_client = FakeRedisClient()
    redis_calls: list[dict] = []

    class FakeRedisModule:
        def Redis(self, **kwargs):
            redis_calls.append(kwargs)
            return fake_client

    redis_asyncio = FakeRedisModule()
    redis_pkg = types.ModuleType("redis")
    redis_pkg.asyncio = redis_asyncio
    monkeypatch.setitem(sys.modules, "redis", redis_pkg)
    monkeypatch.setitem(sys.modules, "redis.asyncio", redis_asyncio)

    cache = redis_cache_mod.RedisCache(host="cache-host", port=6380, db=2, password="secret")
    await cache.connect()
    await cache.connect()

    assert cache._connected is True
    assert cache._client is fake_client
    assert len(redis_calls) == 1
    assert redis_calls[0]["decode_responses"] is True

    await cache.disconnect()
    assert cache._connected is False
    assert fake_client.closed is True


@pytest.mark.asyncio
async def test_connect_handles_import_error(monkeypatch):
    original_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "redis.asyncio":
            raise ImportError("redis missing")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    cache = redis_cache_mod.RedisCache()
    await cache.connect()

    assert cache._connected is False
    assert cache._client is None


@pytest.mark.asyncio
async def test_connect_handles_ping_error(monkeypatch):
    fake_client = FakeRedisClient()
    fake_client.raise_on["ping"] = RuntimeError("ping failed")

    class FakeRedisModule:
        def Redis(self, **_kwargs):
            return fake_client

    redis_asyncio = FakeRedisModule()
    redis_pkg = types.ModuleType("redis")
    redis_pkg.asyncio = redis_asyncio
    monkeypatch.setitem(sys.modules, "redis", redis_pkg)
    monkeypatch.setitem(sys.modules, "redis.asyncio", redis_asyncio)

    cache = redis_cache_mod.RedisCache()
    await cache.connect()

    assert cache._connected is False
    assert cache._client is None


def test_helpers_for_key_serialization_and_jitter(monkeypatch):
    cache = redis_cache_mod.RedisCache(key_prefix="unit:", snowball_jitter=0.2)

    assert cache._make_key("hello") == "unit:hello"

    payload = {"name": "测试", "size": 7}
    serialized = cache._serialize(payload)
    assert json.loads(serialized) == payload
    assert cache._deserialize(serialized) == payload
    assert cache._deserialize("{invalid") == "{invalid"
    assert cache._deserialize(None) is None

    monkeypatch.setattr("random.randint", lambda _low, high: high)
    assert cache._apply_jitter(100) == 120


@pytest.mark.asyncio
async def test_cache_operations_happy_path_and_no_client(monkeypatch):
    cache = redis_cache_mod.RedisCache(
        key_prefix="cache:",
        default_ttl=60,
        max_ttl=90,
        snowball_jitter=0.0,
    )

    assert await cache.get("k") is None
    assert await cache.set("k", "v") is False
    assert await cache.delete("k") is False
    assert await cache.exists("k") is False
    assert await cache.clear_pattern("group:*") == 0

    fake_client = FakeRedisClient()
    cache._client = fake_client

    assert await cache.set("k1", {"ok": True}, ttl=999, apply_jitter=False) is True
    assert fake_client.last_setex is not None
    full_key, ttl, data = fake_client.last_setex
    assert full_key == "cache:k1"
    assert ttl == 90
    assert json.loads(data) == {"ok": True}

    assert await cache.get("k1") == {"ok": True}
    assert await cache.exists("k1") is True
    assert await cache.delete("k1") is True
    assert await cache.exists("k1") is False

    monkeypatch.setattr(cache, "_apply_jitter", lambda value: value + 3)
    assert await cache.set("k2", "v2", ttl=None, apply_jitter=True) is True
    assert fake_client.last_setex is not None
    assert fake_client.last_setex[0] == "cache:k2"
    assert fake_client.last_setex[1] == 63

    fake_client.store["cache:group:1"] = "a"
    fake_client.store["cache:group:2"] = "b"
    fake_client.store["cache:other:1"] = "c"
    assert await cache.clear_pattern("group:*") == 2
    assert "cache:group:1" not in fake_client.store
    assert "cache:group:2" not in fake_client.store
    assert "cache:other:1" in fake_client.store
    assert await cache.clear_pattern("group:*") == 0


@pytest.mark.asyncio
async def test_cache_operations_handle_client_errors():
    cache = redis_cache_mod.RedisCache(key_prefix="error:")
    fake_client = FakeRedisClient()
    cache._client = fake_client

    fake_client.raise_on["get"] = RuntimeError("get failed")
    assert await cache.get("k") is None

    fake_client.raise_on.clear()
    fake_client.raise_on["setex"] = RuntimeError("set failed")
    assert await cache.set("k", "v") is False

    fake_client.raise_on.clear()
    fake_client.raise_on["delete"] = RuntimeError("delete failed")
    assert await cache.delete("k") is False

    fake_client.raise_on.clear()
    fake_client.raise_on["exists"] = RuntimeError("exists failed")
    assert await cache.exists("k") is False

    fake_client.raise_on.clear()
    fake_client.raise_on["scan_iter"] = RuntimeError("scan failed")
    assert await cache.clear_pattern("k*") == 0


@pytest.mark.asyncio
async def test_cached_decorator_uses_key_builder_and_cache_hit():
    cache = redis_cache_mod.RedisCache()
    cache.get = AsyncMock(return_value={"cached": True})
    cache.set = AsyncMock(return_value=True)
    call_count = 0

    async def load_user(user_id: int):
        nonlocal call_count
        call_count += 1
        return {"id": user_id}

    wrapped = cache.cached(
        "user",
        key_builder=lambda user_id: f"user:{user_id}",
    )(load_user)

    result = await wrapped(7)
    assert result == {"cached": True}
    assert call_count == 0
    cache.get.assert_awaited_once_with("user:7")
    cache.set.assert_not_awaited()


@pytest.mark.asyncio
async def test_cached_decorator_caches_none_result_on_miss():
    cache = redis_cache_mod.RedisCache()
    cache.get = AsyncMock(return_value=None)
    cache.set = AsyncMock(return_value=True)
    call_count = 0

    async def load_optional(value: int, *, flag: bool):
        nonlocal call_count
        call_count += 1
        return None if flag else value

    wrapped = cache.cached("optional", ttl=30)(load_optional)
    result = await wrapped(3, flag=True)

    assert result is None
    assert call_count == 1
    cache.get.assert_awaited_once()
    key = cache.get.await_args.args[0]
    assert key.startswith("optional:")
    cache.set.assert_awaited_once_with(key, None, 30)


@pytest.mark.asyncio
async def test_global_cache_helpers(monkeypatch):
    monkeypatch.setenv("REDIS_HOST", "redis-env")
    monkeypatch.setenv("REDIS_PORT", "6390")

    first = redis_cache_mod.get_cache()
    second = redis_cache_mod.get_cache(host="ignored", port=1)
    assert first is second
    assert first.host == "redis-env"
    assert first.port == 6390

    disabled_cache = await redis_cache_mod.init_cache(enabled=False)
    assert isinstance(disabled_cache, redis_cache_mod.RedisCache)
    assert disabled_cache._connected is False

    fake_cache = redis_cache_mod.RedisCache()
    fake_cache.connect = AsyncMock(return_value=None)
    monkeypatch.setattr(redis_cache_mod, "get_cache", lambda *args, **kwargs: fake_cache)

    enabled_cache = await redis_cache_mod.init_cache(host="x", port=9, enabled=True)
    assert enabled_cache is fake_cache
    fake_cache.connect.assert_awaited_once()

    shutdown_cache = redis_cache_mod.RedisCache()
    shutdown_cache.disconnect = AsyncMock(return_value=None)
    redis_cache_mod._cache_instance = shutdown_cache

    await redis_cache_mod.shutdown_cache()
    shutdown_cache.disconnect.assert_awaited_once()
    assert redis_cache_mod._cache_instance is None
