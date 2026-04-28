from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any

import pytest

from app.services import cache_warmer


class FakeCacheService:
    def __init__(self) -> None:
        self.get_calls: list[str] = []
        self.get_or_set_calls: list[tuple[str, int | None]] = []
        self.fail_get: set[str] = set()
        self.fail_get_or_set: set[str] = set()

    async def get(self, key: str) -> Any:
        self.get_calls.append(key)
        if key in self.fail_get:
            raise RuntimeError(f"get failed: {key}")
        return {"key": key}

    async def get_or_set(self, key: str, factory: Any, ttl: int | None = None) -> Any:
        self.get_or_set_calls.append((key, ttl))
        if key in self.fail_get_or_set:
            raise RuntimeError(f"get_or_set failed: {key}")

        value = factory()
        if asyncio.iscoroutine(value):
            return await value
        return value


@pytest.fixture(autouse=True)
def reset_global_warmer() -> None:
    cache_warmer._global_cache_warmer = None
    yield
    cache_warmer._global_cache_warmer = None


def test_pattern_sorting_access_dependency_and_stats(monkeypatch: pytest.MonkeyPatch) -> None:
    service = FakeCacheService()
    warmer = cache_warmer.CacheWarmer(service, max_history=2)

    warmer.add_warmup_pattern(cache_warmer.WarmupPattern(name="p2", pattern="movie:*", priority=2))
    warmer.add_warmup_pattern(cache_warmer.WarmupPattern(name="p1", pattern="user:*", priority=1))
    assert [pattern.name for pattern in warmer.warmup_patterns] == ["p1", "p2"]

    ticks = iter([1000.0, 1001.0, 1002.0])
    monkeypatch.setattr(cache_warmer.time, "time", lambda: next(ticks))

    warmer.record_access("key-a")
    warmer.record_access("key-b")
    warmer.record_access("key-c")
    assert [record.key for record in warmer.access_history] == ["key-b", "key-c"]

    warmer.add_dependency("video:1", "meta:1")
    warmer.add_dependency("video:1", "subtitle:1")
    assert warmer.dependencies["video:1"] == {"meta:1", "subtitle:1"}

    stats = warmer.get_stats()
    assert stats["active_patterns"] == 2
    assert stats["access_history_size"] == 2
    assert stats["dependencies_count"] == 1
    assert stats["running"] is False


@pytest.mark.asyncio
async def test_start_and_stop_automatic_warming(monkeypatch: pytest.MonkeyPatch) -> None:
    service = FakeCacheService()
    warmer = cache_warmer.CacheWarmer(service)
    warnings: list[str] = []

    async def fake_loop(_interval: int) -> None:
        while True:
            await asyncio.sleep(3600)

    monkeypatch.setattr(warmer, "_automatic_warming_loop", fake_loop)
    monkeypatch.setattr(cache_warmer.logger, "warning", lambda message: warnings.append(message))

    await warmer.start_automatic_warming(interval=1)
    assert warmer._running is True
    assert warmer._warmup_task is not None

    await warmer.start_automatic_warming(interval=1)
    assert any("already running" in message for message in warnings)

    await warmer.stop_automatic_warming()
    assert warmer._running is False


@pytest.mark.asyncio
async def test_automatic_warming_loop_error_path(monkeypatch: pytest.MonkeyPatch) -> None:
    service = FakeCacheService()
    warmer = cache_warmer.CacheWarmer(service)
    warmer._running = True

    errors: list[str] = []
    sleep_calls: list[int] = []

    async def fake_perform() -> None:
        raise RuntimeError("boom")

    async def fake_sleep(seconds: int) -> None:
        sleep_calls.append(seconds)
        warmer._running = False

    monkeypatch.setattr(warmer, "perform_comprehensive_warming", fake_perform)
    monkeypatch.setattr(cache_warmer.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(cache_warmer.logger, "error", lambda message: errors.append(message))

    await warmer._automatic_warming_loop(interval=5)
    assert sleep_calls == [60]
    assert any("automatic warming loop" in message for message in errors)


@pytest.mark.asyncio
async def test_perform_comprehensive_warming_calls_all_stages(monkeypatch: pytest.MonkeyPatch) -> None:
    service = FakeCacheService()
    warmer = cache_warmer.CacheWarmer(service)
    calls: list[str] = []

    monkeypatch.setattr(warmer, "_warmup_by_patterns", lambda: calls.append("pattern") or asyncio.sleep(0))
    monkeypatch.setattr(warmer, "_warmup_by_access_patterns", lambda: calls.append("access") or asyncio.sleep(0))
    monkeypatch.setattr(warmer, "_warmup_by_dependencies", lambda: calls.append("dep") or asyncio.sleep(0))
    monkeypatch.setattr(warmer, "_log_warming_stats", lambda: calls.append("log"))

    ticks = iter([10.0, 10.4])
    monkeypatch.setattr(cache_warmer.time, "time", lambda: next(ticks))

    await warmer.perform_comprehensive_warming()
    assert calls == ["pattern", "access", "dep", "log"]


@pytest.mark.asyncio
async def test_warmup_by_patterns_and_pattern_branches(monkeypatch: pytest.MonkeyPatch) -> None:
    service = FakeCacheService()
    warmer = cache_warmer.CacheWarmer(service)
    errors: list[str] = []

    warmer.add_warmup_pattern(cache_warmer.WarmupPattern(name="good", pattern="user:*", priority=1))
    warmer.add_warmup_pattern(
        cache_warmer.WarmupPattern(
            name="skip",
            pattern="hot:*",
            priority=1,
            strategy=cache_warmer.WarmupStrategy.ACCESS_PATTERN,
        )
    )
    warmer.add_warmup_pattern(cache_warmer.WarmupPattern(name="bad", pattern="movie:*", priority=2))

    original_warmup_pattern = warmer._warmup_pattern

    async def fake_warmup_pattern(pattern: cache_warmer.WarmupPattern) -> int:
        if pattern.name == "bad":
            raise RuntimeError("bad pattern")
        return 2

    monkeypatch.setattr(warmer, "_warmup_pattern", fake_warmup_pattern)
    monkeypatch.setattr(cache_warmer.logger, "error", lambda message: errors.append(message))

    await warmer._warmup_by_patterns()
    assert warmer.stats["patterns_used"]["good"] == 2
    assert "skip" not in warmer.stats["patterns_used"]
    assert any("Failed to warm pattern bad" in message for message in errors)
    monkeypatch.setattr(warmer, "_warmup_pattern", original_warmup_pattern)

    # user pattern
    user_pattern = cache_warmer.WarmupPattern(name="user", pattern="user:*", ttl=123)
    monkeypatch.setattr(warmer, "_discover_user_keys", lambda: asyncio.sleep(0, result=["u1", "u2"]))
    monkeypatch.setattr(warmer, "_load_user_data", lambda uid: asyncio.sleep(0, result={"id": uid}))
    service.fail_get_or_set = {"user:u2"}
    user_warmed = await warmer._warmup_pattern(user_pattern)
    assert user_warmed == 1

    # movie pattern
    movie_pattern = cache_warmer.WarmupPattern(name="movie", pattern="movie:*", ttl=456)
    monkeypatch.setattr(warmer, "_discover_movie_keys", lambda: asyncio.sleep(0, result=["m1", "m2"]))
    monkeypatch.setattr(warmer, "_load_movie_data", lambda mid: asyncio.sleep(0, result={"id": mid}))
    service.fail_get_or_set = {"user:u2", "movie:m2"}
    movie_warmed = await warmer._warmup_pattern(movie_pattern)
    assert movie_warmed == 1

    # unmatched pattern
    unmatched = cache_warmer.WarmupPattern(name="other", pattern="other:*")
    unmatched_warmed = await warmer._warmup_pattern(unmatched)
    assert unmatched_warmed == 0

    assert warmer.stats["total_warmed"] == 2
    assert any("Failed to warm user u2" in message for message in errors)
    assert any("Failed to warm movie m2" in message for message in errors)


@pytest.mark.asyncio
async def test_warmup_by_access_patterns(monkeypatch: pytest.MonkeyPatch) -> None:
    service = FakeCacheService()
    warmer = cache_warmer.CacheWarmer(service)
    errors: list[str] = []

    await warmer._warmup_by_access_patterns()  # empty history branch
    assert service.get_calls == []

    for index in range(60):
        freq = 2 if index < 30 else 1
        for _ in range(freq):
            warmer.access_history.append(cache_warmer.AccessRecord(key=f"k{index}", timestamp=float(index)))

    service.fail_get = {"k0"}
    monkeypatch.setattr(cache_warmer.logger, "error", lambda message: errors.append(message))

    await warmer._warmup_by_access_patterns()
    assert len(service.get_calls) == 50
    assert "k0" in service.get_calls
    assert any("Failed to warm key k0" in message for message in errors)


@pytest.mark.asyncio
async def test_warmup_by_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    service = FakeCacheService()
    warmer = cache_warmer.CacheWarmer(service)
    errors: list[str] = []

    warmer.dependencies = defaultdict(set, {"dep_ok": {"a", "b"}, "dep_fail": {"c"}})
    service.fail_get = {"c"}
    monkeypatch.setattr(cache_warmer.logger, "error", lambda message: errors.append(message))

    await warmer._warmup_by_dependencies()

    assert set(service.get_calls[:2]) == {"a", "b"}
    assert service.get_calls[2] == "dep_ok"
    assert "c" in service.get_calls
    assert "dep_fail" not in service.get_calls
    assert any("Failed to warm dependency chain for dep_fail" in message for message in errors)


@pytest.mark.asyncio
async def test_schedule_warming_and_default_helpers(monkeypatch: pytest.MonkeyPatch) -> None:
    service = FakeCacheService()
    warmer = cache_warmer.CacheWarmer(service)
    errors: list[str] = []
    debug_logs: list[str] = []
    sleep_calls: list[float] = []
    created_tasks: list[asyncio.Task[Any]] = []

    service.fail_get = {"k2"}

    async def fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)

    original_create_task = asyncio.create_task

    def tracking_create_task(coro: Any) -> asyncio.Task[Any]:
        task = original_create_task(coro)
        created_tasks.append(task)
        return task

    monkeypatch.setattr(cache_warmer.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(cache_warmer.asyncio, "create_task", tracking_create_task)
    monkeypatch.setattr(cache_warmer.logger, "error", lambda message: errors.append(message))
    monkeypatch.setattr(cache_warmer.logger, "debug", lambda message: debug_logs.append(message))

    await warmer.schedule_warming(["k1", "k2"], delay=0.5)
    await asyncio.gather(*created_tasks)

    assert sleep_calls == [0.5]
    assert service.get_calls == ["k1", "k2"]
    assert any("Scheduled warmup completed for key: k1" in message for message in debug_logs)
    assert any("Failed scheduled warmup for key k2" in message for message in errors)

    # global singleton helpers
    cache_warmer._global_cache_warmer = None
    global_warmer = cache_warmer.get_cache_warmer(service)
    assert global_warmer is cache_warmer.get_cache_warmer(service)
    cache_warmer.setup_default_warming_patterns(global_warmer)
    assert [pattern.name for pattern in global_warmer.warmup_patterns] == [
        "user_data",
        "hot_data",
        "movie_data",
    ]


@pytest.mark.asyncio
async def test_internal_discovery_and_load_helpers(monkeypatch: pytest.MonkeyPatch) -> None:
    service = FakeCacheService()
    warmer = cache_warmer.CacheWarmer(service)

    users = await warmer._discover_user_keys()
    movies = await warmer._discover_movie_keys()
    assert len(users) == 10
    assert len(movies) == 20
    assert users[0] == "user_1"
    assert movies[-1] == "movie_20"

    async def fake_sleep(_delay: float) -> None:
        return None

    monkeypatch.setattr(cache_warmer.asyncio, "sleep", fake_sleep)
    user_data = await warmer._load_user_data("u1")
    movie_data = await warmer._load_movie_data("m1")
    assert user_data["id"] == "u1"
    assert movie_data["id"] == "m1"
    assert movie_data["rating"] == 8.5
