from __future__ import annotations

import asyncio
from typing import Any

import pytest

from app.services import tiered_cache


class FakeL1Cache:
    def __init__(self) -> None:
        self.store: dict[str, Any] = {}
        self.get_stats_value = {"kind": "l1"}
        self.fail_set: set[str] = set()

    async def get(self, key: str) -> Any:
        return self.store.get(key)

    async def set(self, key: str, value: Any, _ttl: int | None = None) -> None:
        if key in self.fail_set:
            raise RuntimeError(f"l1 set failed: {key}")
        self.store[key] = value

    async def delete(self, key: str) -> bool:
        return self.store.pop(key, None) is not None

    async def clear(self) -> bool:
        self.store.clear()
        return True

    def get_stats(self) -> dict[str, Any]:
        return self.get_stats_value


class FakeL2Cache:
    def __init__(self) -> None:
        self.store: dict[str, Any] = {}
        self.started = False
        self.stopped = False
        self.fail_set: set[str] = set()
        self.fail_get_many = False
        self.clear_result = True
        self.get_stats_value = {"kind": "l2"}

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.stopped = True

    async def get(self, key: str) -> Any:
        return self.store.get(key)

    async def set(self, key: str, value: Any, _ttl: int | None = None) -> bool:
        if key in self.fail_set:
            raise RuntimeError(f"l2 set failed: {key}")
        self.store[key] = value
        return True

    async def delete(self, key: str) -> bool:
        return self.store.pop(key, None) is not None

    async def clear(self) -> bool:
        self.store.clear()
        return self.clear_result

    async def get_stats(self) -> dict[str, Any]:
        return self.get_stats_value

    async def get_many(self, keys: list[str]) -> dict[str, Any]:
        if self.fail_get_many:
            raise RuntimeError("get_many failed")
        return {key: self.store[key] for key in keys if key in self.store}


class FakeL3Cache:
    def __init__(self) -> None:
        self.store: dict[str, Any] = {}
        self.fail_set: set[str] = set()
        self.fail_get_stats = False
        self.flush_result = True
        self.get_stats_value = {"kind": "l3"}

    async def get(self, key: str) -> Any:
        return self.store.get(key)

    async def set(self, key: str, value: Any, _ttl: int | None = None) -> bool:
        if key in self.fail_set:
            raise RuntimeError(f"l3 set failed: {key}")
        self.store[key] = value
        return True

    async def delete(self, key: str) -> bool:
        return self.store.pop(key, None) is not None

    async def flush_all(self) -> bool:
        self.store.clear()
        return self.flush_result

    async def get_stats(self) -> dict[str, Any]:
        if self.fail_get_stats:
            raise RuntimeError("stats failed")
        return self.get_stats_value


@pytest.fixture(autouse=True)
def reset_global_tiered_cache() -> None:
    tiered_cache._global_tiered_cache = None
    yield
    tiered_cache._global_tiered_cache = None


def build_tiered_cache(
    *,
    enable_l1: bool = True,
    enable_l2: bool = True,
    enable_l3: bool = False,
) -> tuple[tiered_cache.TieredCache, FakeL1Cache | None, FakeL2Cache | None, FakeL3Cache | None]:
    config = tiered_cache.CacheConfig(
        enable_l1=enable_l1,
        enable_l2=enable_l2,
        enable_l3=enable_l3,
    )
    cache = tiered_cache.TieredCache(config)

    l1 = FakeL1Cache() if enable_l1 else None
    l2 = FakeL2Cache() if enable_l2 else None
    l3 = FakeL3Cache() if enable_l3 else None

    cache._l1_cache = l1
    cache._l2_cache = l2
    cache._l3_cache = l3
    return cache, l1, l2, l3


def test_cache_level_enum_and_init_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    assert tiered_cache.CacheLevel.L1_MEMORY.value == "memory"
    assert tiered_cache.CacheLevel.L2_DISK.value == "disk"
    assert tiered_cache.CacheLevel.L3_REDIS.value == "redis"

    warnings: list[str] = []

    def raise_import(*_args: Any, **_kwargs: Any) -> Any:
        raise RuntimeError("redis unavailable")

    monkeypatch.setattr(cache := tiered_cache, "MemoryCache", lambda **kwargs: FakeL1Cache())
    monkeypatch.setattr(cache, "DiskCache", lambda **kwargs: FakeL2Cache())
    monkeypatch.setattr(cache.logger, "warning", lambda message: warnings.append(message))
    monkeypatch.setattr(
        __import__("builtins"),
        "__import__",
        lambda name, *args, **kwargs: (
            raise_import() if name == "app.services.redis_cache" else __import__(name, *args, **kwargs)
        ),
    )

    # build with L1/L2 only to avoid import override side effects on normal path
    instance = tiered_cache.TieredCache(tiered_cache.CacheConfig(enable_l3=False))
    assert isinstance(instance._l1_cache, FakeL1Cache)
    assert isinstance(instance._l2_cache, FakeL2Cache)


@pytest.mark.asyncio
async def test_start_stop_and_worker_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    cache, _l1, l2, l3 = build_tiered_cache(enable_l1=True, enable_l2=True, enable_l3=True)
    assert l2 is not None and l3 is not None

    original_create_task = asyncio.create_task
    created_tasks: list[asyncio.Task[Any]] = []

    def tracking_create_task(coro: Any) -> asyncio.Task[Any]:
        task = original_create_task(coro)
        created_tasks.append(task)
        return task

    monkeypatch.setattr(tiered_cache.asyncio, "create_task", tracking_create_task)

    await cache.start()
    assert l2.started is True
    assert cache._write_task is not None

    # normal write path
    await cache._write_queue.put(("k1", "v1", 5))
    await asyncio.sleep(0)
    assert l2.store["k1"] == "v1"
    assert l3.store["k1"] == "v1"

    # failure path in worker
    warnings: list[str] = []
    errors: list[str] = []
    l2.fail_set = {"k2"}
    l3.fail_set = {"k2"}
    monkeypatch.setattr(tiered_cache.logger, "warning", lambda message: warnings.append(message))
    monkeypatch.setattr(tiered_cache.logger, "error", lambda message: errors.append(message))
    await cache._write_queue.put(("k2", "v2", 5))
    await asyncio.sleep(0)
    assert any("L2 cache write failed" in message for message in warnings)
    assert any("L3 cache write failed" in message for message in warnings)

    await cache.stop()
    assert l2.stopped is True


@pytest.mark.asyncio
async def test_get_with_l1_l2_l3_fallback_and_backfill() -> None:
    cache, l1, l2, l3 = build_tiered_cache(enable_l1=True, enable_l2=True, enable_l3=True)
    assert l1 is not None and l2 is not None and l3 is not None

    l1.store["l1"] = "from-l1"
    assert await cache.get("l1") == "from-l1"

    l2.store["l2"] = "from-l2"
    assert await cache.get("l2") == "from-l2"
    assert l1.store["l2"] == "from-l2"

    l3.store["l3"] = "from-l3"
    assert await cache.get("l3") == "from-l3"
    assert l1.store["l3"] == "from-l3"
    assert l2.store["l3"] == "from-l3"

    assert await cache.get("missing") is None


@pytest.mark.asyncio
async def test_set_delete_clear_and_get_or_set(monkeypatch: pytest.MonkeyPatch) -> None:
    cache, l1, l2, l3 = build_tiered_cache(enable_l1=True, enable_l2=True, enable_l3=True)
    assert l1 is not None and l2 is not None and l3 is not None

    # async queue persist path
    assert await cache.set("k1", "v1", ttl=10, persist=True) is True
    queued = await cache._write_queue.get()
    assert queued == ("k1", "v1", 10)
    cache._write_queue.task_done()

    # persist disabled path
    queue_size_before = cache._write_queue.qsize()
    assert await cache.set("k2", "v2", ttl=None, persist=False) is True
    assert cache._write_queue.qsize() == queue_size_before

    # l1 failure path
    l1.fail_set = {"k3"}
    assert await cache.set("k3", "v3", persist=False) is False

    # queue full fallback sync write
    original_put_nowait = cache._write_queue.put_nowait

    def raise_queue_full(_item: Any) -> None:
        raise asyncio.QueueFull

    cache._write_queue.put_nowait = raise_queue_full  # type: ignore[assignment]
    assert await cache.set("k4", "v4", ttl=9, persist=True) is True
    assert l2.store["k4"] == "v4"
    assert l3.store["k4"] == "v4"
    cache._write_queue.put_nowait = original_put_nowait  # type: ignore[assignment]

    # delete and clear
    l1.store["d"] = "1"
    l2.store["d"] = "1"
    l3.store["d"] = "1"
    assert await cache.delete("d") is True
    assert await cache.delete("not-exists") is False

    l2.clear_result = True
    l3.flush_result = True
    assert await cache.clear() is True

    l2.clear_result = False
    assert await cache.clear() is False

    # get_or_set sync/async factory
    l1.store["existing"] = "v"
    assert await cache.get_or_set("existing", lambda: "new") == "v"

    value_sync = await cache.get_or_set("missing-sync", lambda: "sync")
    assert value_sync == "sync"

    async def async_factory() -> str:
        return "async"

    value_async = await cache.get_or_set("missing-async", async_factory)
    assert value_async == "async"


@pytest.mark.asyncio
async def test_get_stats_and_warmup_paths() -> None:
    cache, l1, l2, l3 = build_tiered_cache(enable_l1=True, enable_l2=True, enable_l3=True)
    assert l1 is not None and l2 is not None and l3 is not None

    stats = await cache.get_stats()
    assert stats["tiered_cache"]["l1_enabled"] is True
    assert stats["l1_memory"] == {"kind": "l1"}
    assert stats["l2_disk"] == {"kind": "l2"}
    assert stats["l3_redis"] == {"kind": "l3"}

    # warmup empty/no-l1 path
    cache_no_l1, _n1, _n2, _n3 = build_tiered_cache(enable_l1=False, enable_l2=True, enable_l3=True)
    assert await cache_no_l1.warmup(["a"]) == 0
    assert await cache.warmup([]) == 0

    # warmup from l2 + l3
    l2.store = {"a": "A"}
    l3.store = {"b": "B", "c": "C"}
    warmed = await cache.warmup(["a", "b", "z"])
    assert warmed == 2
    assert l1.store["a"] == "A"
    assert l1.store["b"] == "B"
    assert l2.store["b"] == "B"
    assert "z" not in l1.store


def test_get_tiered_cache_singleton() -> None:
    tiered_cache._global_tiered_cache = None
    first = tiered_cache.get_tiered_cache(tiered_cache.CacheConfig(enable_l1=False, enable_l2=False, enable_l3=False))
    second = tiered_cache.get_tiered_cache()
    assert first is second
