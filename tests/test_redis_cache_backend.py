import fnmatch
import pickle
import sys
import types
from unittest.mock import AsyncMock

import pytest

# aioredis has import-time incompatibility on some Python 3.11 builds.
# Inject a minimal stub so module logic can be tested deterministically.
if "aioredis" not in sys.modules:
    sys.modules["aioredis"] = types.SimpleNamespace(from_url=lambda *args, **kwargs: None, Redis=object)

from app.services import redis_cache as redis_cache_mod


class FakePipeline:
    def __init__(self, client):
        self.client = client
        self.commands: list[tuple[str, int, bytes]] = []

    def setex(self, key: str, ttl: int, data: bytes) -> None:
        self.commands.append((key, ttl, data))

    async def execute(self) -> list:
        if "pipeline_execute" in self.client.raise_on:
            raise self.client.raise_on["pipeline_execute"]

        results = []
        for index, (key, _ttl, data) in enumerate(self.commands):
            self.client.store[key] = data
            if self.client.pipeline_results is None:
                results.append(True)
            elif index < len(self.client.pipeline_results):
                results.append(self.client.pipeline_results[index])
            else:
                results.append(True)
        return results


class FakeRedisClient:
    def __init__(self):
        self.store: dict[str, bytes] = {}
        self.raise_on: dict[str, Exception] = {}
        self.pipeline_results: list | None = None
        self.closed = False
        self.set_result = True
        self.info_data = {
            "redis_version": "7.2.0",
            "used_memory_human": "1M",
            "connected_clients": 3,
            "total_commands_processed": 99,
        }

    async def ping(self) -> bool:
        if "ping" in self.raise_on:
            raise self.raise_on["ping"]
        return True

    async def close(self) -> None:
        self.closed = True

    async def get(self, key: str):
        if "get" in self.raise_on:
            raise self.raise_on["get"]
        return self.store.get(key)

    async def set(self, key: str, value: bytes, ex: int | None = None):
        if "set" in self.raise_on:
            raise self.raise_on["set"]
        self.store[key] = value
        return self.set_result

    async def delete(self, key: str) -> int:
        if "delete" in self.raise_on:
            raise self.raise_on["delete"]
        if key in self.store:
            del self.store[key]
            return 1
        return 0

    async def exists(self, key: str) -> int:
        if "exists" in self.raise_on:
            raise self.raise_on["exists"]
        return 1 if key in self.store else 0

    async def expire(self, key: str, ttl: int) -> bool:
        if "expire" in self.raise_on:
            raise self.raise_on["expire"]
        return key in self.store and ttl > 0

    async def info(self) -> dict:
        if "info" in self.raise_on:
            raise self.raise_on["info"]
        return self.info_data

    async def flushall(self) -> None:
        if "flushall" in self.raise_on:
            raise self.raise_on["flushall"]
        self.store.clear()

    async def keys(self, pattern: str = "*") -> list[str]:
        if "keys" in self.raise_on:
            raise self.raise_on["keys"]
        return sorted([key for key in self.store if fnmatch.fnmatch(key, pattern)])

    async def mget(self, keys: list[str]) -> list[bytes | None]:
        if "mget" in self.raise_on:
            raise self.raise_on["mget"]
        return [self.store.get(key) for key in keys]

    def pipeline(self) -> FakePipeline:
        if "pipeline" in self.raise_on:
            raise self.raise_on["pipeline"]
        return FakePipeline(self)


@pytest.fixture(autouse=True)
def reset_globals():
    redis_cache_mod._global_redis_backend = None
    redis_cache_mod._global_redis_service = None
    yield
    redis_cache_mod._global_redis_backend = None
    redis_cache_mod._global_redis_service = None


@pytest.mark.asyncio
async def test_backend_connect_disconnect_and_reuse(monkeypatch):
    fake_client = FakeRedisClient()
    from_url_calls: list[tuple] = []

    def fake_from_url(*args, **kwargs):
        from_url_calls.append((args, kwargs))
        return fake_client

    monkeypatch.setattr(redis_cache_mod.aioredis, "from_url", fake_from_url)

    backend = redis_cache_mod.RedisCacheBackend(redis_url="redis://unit-test", connection_pool_size=7)
    assert await backend.connect() is True
    assert await backend.connect() is True
    assert len(from_url_calls) == 1
    assert backend._connected is True
    assert backend.redis_client is fake_client

    await backend.disconnect()
    assert fake_client.closed is True
    assert backend._connected is False
    assert backend.redis_client is None


@pytest.mark.asyncio
async def test_backend_connect_failure_paths(monkeypatch):
    backend = redis_cache_mod.RedisCacheBackend()

    def fail_from_url(*_args, **_kwargs):
        raise RuntimeError("from_url failed")

    monkeypatch.setattr(redis_cache_mod.aioredis, "from_url", fail_from_url)
    assert await backend.connect() is False
    assert backend._connected is False

    fake_client = FakeRedisClient()
    fake_client.raise_on["ping"] = RuntimeError("ping failed")
    monkeypatch.setattr(redis_cache_mod.aioredis, "from_url", lambda *_args, **_kwargs: fake_client)
    assert await backend.connect() is False
    assert backend._connected is False


def test_backend_serialize_deserialize_fallbacks():
    backend = redis_cache_mod.RedisCacheBackend()
    json_data = backend._serialize({"name": "redis", "size": 1})
    assert backend._deserialize(json_data) == {"name": "redis", "size": 1}
    assert backend._deserialize(b"") is None

    pickled = backend._serialize({"unsupported"})
    assert backend._deserialize(pickled) == {"unsupported"}
    assert backend._deserialize(pickle.dumps({"a": 1})) == {"a": 1}


@pytest.mark.asyncio
async def test_backend_get_prefers_local_cache():
    backend = redis_cache_mod.RedisCacheBackend()
    backend.local_cache.set("local-key", "local-value")
    backend.connect = AsyncMock(return_value=True)

    assert await backend.get("local-key") == "local-value"
    backend.connect.assert_not_awaited()


@pytest.mark.asyncio
async def test_backend_get_from_redis_and_error_paths():
    backend = redis_cache_mod.RedisCacheBackend()
    backend.connect = AsyncMock(return_value=False)
    assert await backend.get("missing") is None

    fake_client = FakeRedisClient()
    backend.redis_client = fake_client
    backend.connect = AsyncMock(return_value=True)
    fake_client.store["redis-key"] = backend._serialize({"k": "v"})
    assert await backend.get("redis-key") == {"k": "v"}
    assert backend.local_cache.get("redis-key") == {"k": "v"}

    backend.local_cache.delete("redis-key")
    fake_client.raise_on["get"] = RuntimeError("get failed")
    assert await backend.get("redis-key") is None


@pytest.mark.asyncio
async def test_backend_set_delete_exists_expire_core_paths():
    backend = redis_cache_mod.RedisCacheBackend(default_ttl=60)
    fake_client = FakeRedisClient()
    backend.redis_client = fake_client
    backend.connect = AsyncMock(return_value=True)

    assert await backend.set("k1", {"ok": True}, ttl=10) is True
    assert fake_client.store["k1"] == backend._serialize({"ok": True})

    backend.local_cache.set("local-hit", 1)
    backend.connect = AsyncMock(return_value=False)
    assert await backend.exists("local-hit") is True
    backend.connect.assert_not_awaited()

    backend.connect = AsyncMock(return_value=True)
    assert await backend.exists("k1") is True
    assert await backend.expire("k1", 120) is True

    assert await backend.delete("k1") is True
    assert await backend.delete("k1") is False


@pytest.mark.asyncio
async def test_backend_set_delete_exists_expire_error_paths():
    backend = redis_cache_mod.RedisCacheBackend()
    fake_client = FakeRedisClient()
    backend.redis_client = fake_client

    backend.connect = AsyncMock(return_value=False)
    assert await backend.set("k", "v") is False
    assert backend.local_cache.get("k") == "v"
    assert await backend.delete("k") is False
    assert backend.local_cache.get("k") is None
    assert await backend.exists("k") is False
    assert await backend.expire("k", 1) is False

    backend.connect = AsyncMock(return_value=True)
    fake_client.raise_on["set"] = RuntimeError("set failed")
    assert await backend.set("k2", "v2") is False

    fake_client.raise_on.clear()
    fake_client.raise_on["delete"] = RuntimeError("delete failed")
    assert await backend.delete("k2") is False

    fake_client.raise_on.clear()
    fake_client.raise_on["exists"] = RuntimeError("exists failed")
    assert await backend.exists("k2") is False

    fake_client.raise_on.clear()
    fake_client.raise_on["expire"] = RuntimeError("expire failed")
    assert await backend.expire("k2", 1) is False


@pytest.mark.asyncio
async def test_backend_stats_flush_keys_paths():
    backend = redis_cache_mod.RedisCacheBackend()
    fake_client = FakeRedisClient()
    backend.redis_client = fake_client
    backend.connect = AsyncMock(return_value=True)

    fake_client.store["a:1"] = backend._serialize({"id": 1})
    fake_client.store["b:2"] = backend._serialize({"id": 2})

    stats = await backend.get_stats()
    assert stats["backend_type"] == "redis_with_local_cache"
    assert stats["redis"]["redis_version"] == "7.2.0"

    assert await backend.keys("a:*") == ["a:1"]
    assert await backend.flush_all() is True
    assert fake_client.store == {}

    backend.connect = AsyncMock(return_value=False)
    assert (await backend.get_stats())["redis"] == {}
    assert await backend.keys("*") == []
    assert await backend.flush_all() is False

    backend.connect = AsyncMock(return_value=True)
    fake_client.raise_on["info"] = RuntimeError("info failed")
    assert (await backend.get_stats())["redis"] == {}

    fake_client.raise_on.clear()
    fake_client.raise_on["keys"] = RuntimeError("keys failed")
    assert await backend.keys("*") == []

    fake_client.raise_on.clear()
    fake_client.raise_on["flushall"] = RuntimeError("flush failed")
    assert await backend.flush_all() is False


@pytest.mark.asyncio
async def test_service_get_or_set_sync_and_async_factory():
    backend = redis_cache_mod.RedisCacheBackend()
    service = redis_cache_mod.RedisCacheService(backend)
    backend.get = AsyncMock(side_effect=["hit", None, None])
    backend.set = AsyncMock(return_value=True)

    assert await service.get_or_set("k1", lambda: "new") == "hit"
    assert await service.get_or_set("k2", lambda: "sync") == "sync"

    async def async_factory():
        return "async"

    assert await service.get_or_set("k3", async_factory) == "async"
    assert backend.set.await_count == 2


@pytest.mark.asyncio
async def test_service_batch_get_and_batch_set_paths():
    backend = redis_cache_mod.RedisCacheBackend(default_ttl=99)
    fake_client = FakeRedisClient()
    backend.redis_client = fake_client
    backend.connect = AsyncMock(return_value=True)
    service = redis_cache_mod.RedisCacheService(backend)

    backend.local_cache.set("k1", "local")
    fake_client.store["k2"] = backend._serialize({"v": 2})
    result = await service.batch_get(["k1", "k2", "k3"])
    assert result == {"k1": "local", "k2": {"v": 2}}
    assert backend.local_cache.get("k2") == {"v": 2}

    fake_client.raise_on["mget"] = RuntimeError("mget failed")
    assert await service.batch_get(["k1", "k2"]) == {"k1": "local", "k2": {"v": 2}}
    fake_client.raise_on.clear()

    assert await service.batch_set({}, ttl=10) == 0

    fake_client.pipeline_results = [True, False, 1]
    count = await service.batch_set({"a": 1, "b": 2, "c": 3}, ttl=33)
    assert count == 2
    assert backend.local_cache.get("a") == 1

    fake_client.raise_on["pipeline_execute"] = RuntimeError("pipeline failed")
    assert await service.batch_set({"x": 1}) == 0


def test_global_singletons_and_exports():
    backend1 = redis_cache_mod.get_redis_cache_backend(redis_url="redis://first", local_cache_size=32, default_ttl=77)
    backend2 = redis_cache_mod.get_redis_cache_backend(redis_url="redis://second")
    assert backend1 is backend2
    assert backend1.redis_url == "redis://first"
    assert backend1.default_ttl == 77

    service1 = redis_cache_mod.get_redis_cache_service(redis_url="redis://first")
    service2 = redis_cache_mod.get_redis_cache_service(redis_url="redis://second")
    assert service1 is service2
    assert service1.backend is backend1

    assert "CacheProtocol" in redis_cache_mod.__all__
    assert "CacheStats" in redis_cache_mod.__all__
    assert "RedisCacheBackend" in redis_cache_mod.__all__
    assert "RedisCacheService" in redis_cache_mod.__all__
