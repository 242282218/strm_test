from __future__ import annotations

from typing import Any

import pytest
from fastapi import HTTPException

from app.api import dashboard


@pytest.fixture(autouse=True)
def reset_dashboard_globals() -> None:
    dashboard._db = None
    dashboard._task_scheduler = None
    dashboard._link_cache = None
    yield
    dashboard._db = None
    dashboard._task_scheduler = None
    dashboard._link_cache = None


def test_get_db_returns_singleton(monkeypatch: pytest.MonkeyPatch) -> None:
    created_paths: list[str] = []

    class FakeDatabase:
        def __init__(self, path: str) -> None:
            created_paths.append(path)

    monkeypatch.setattr(dashboard, "resolve_db_path", lambda: "test.db")
    monkeypatch.setattr(dashboard, "Database", FakeDatabase)

    first = dashboard.get_db()
    second = dashboard.get_db()

    assert first is second
    assert created_paths == ["test.db"]


@pytest.mark.asyncio
async def test_get_task_scheduler_auto_start_and_singleton(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeScheduler:
        def __init__(self) -> None:
            self.start_calls = 0

        async def start(self) -> None:
            self.start_calls += 1

    monkeypatch.setattr(dashboard, "TaskScheduler", FakeScheduler)

    first = await dashboard.get_task_scheduler()
    second = await dashboard.get_task_scheduler()

    assert first is second
    assert first.start_calls == 1


@pytest.mark.asyncio
async def test_get_link_cache_auto_start_and_singleton(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeCache:
        def __init__(self) -> None:
            self.start_calls = 0

        async def start(self) -> None:
            self.start_calls += 1

    monkeypatch.setattr(dashboard, "LinkCache", FakeCache)

    first = await dashboard.get_link_cache()
    second = await dashboard.get_link_cache()

    assert first is second
    assert first.start_calls == 1


def test_calculate_hit_rate_handles_zero_total_access() -> None:
    assert dashboard.calculate_hit_rate({"total_access_count": 0, "valid_entries": 5, "total_entries": 10}) == 0.0


def test_calculate_hit_rate_handles_zero_total_entries() -> None:
    assert dashboard.calculate_hit_rate({"total_access_count": 12, "valid_entries": 5, "total_entries": 0}) == 0.0


def test_calculate_hit_rate_returns_rounded_ratio() -> None:
    assert dashboard.calculate_hit_rate({"total_access_count": 12, "valid_entries": 1, "total_entries": 3}) == 33.3


def test_get_recent_tasks_limits_and_maps_fields() -> None:
    class FakeScheduler:
        @staticmethod
        def list_tasks() -> list[dict[str, Any]]:
            return [
                {"name": f"task-{idx}", "mode": "scan", "enabled": idx % 2 == 0, "progress": idx * 10, "last_run": f"T{idx}"}
                for idx in range(7)
            ]

    tasks = dashboard.get_recent_tasks(FakeScheduler())

    assert len(tasks) == 5
    assert tasks[0]["name"] == "task-0"
    assert tasks[0]["status"] == "running"
    assert tasks[1]["status"] == "stopped"
    assert tasks[4]["time"] == "T4"


def test_get_recent_tasks_returns_empty_on_error() -> None:
    class BrokenScheduler:
        @staticmethod
        def list_tasks() -> list[dict[str, Any]]:
            raise RuntimeError("list failed")

    assert dashboard.get_recent_tasks(BrokenScheduler()) == []


def test_get_services_status_reflects_cookie_state(monkeypatch: pytest.MonkeyPatch) -> None:
    class ConfigWithCookie:
        @staticmethod
        def get_quark_cookie() -> str:
            return "cookie"

    monkeypatch.setattr(dashboard, "config", ConfigWithCookie())
    services = dashboard.get_services_status({"running": True}, {"running": False})

    assert services == [
        {"name": "API服务", "status": "running"},
        {"name": "任务调度器", "status": "running"},
        {"name": "缓存服务", "status": "stopped"},
        {"name": "Emby代理", "status": "running"},
    ]


def test_calculate_file_types_counts_extensions_and_unknown() -> None:
    files = [
        {"filename": "a.MKV"},
        {"filename": "b.mp4"},
        {"filename": "noext"},
        {"filename": "b.mp4"},
    ]

    assert dashboard.calculate_file_types(files) == {"mkv": 1, "mp4": 2, "unknown": 1}


@pytest.mark.asyncio
async def test_get_dashboard_stats_success(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeDB:
        @staticmethod
        def get_all_strms() -> list[dict[str, str]]:
            return [{"filename": "a.mkv"}, {"filename": "b.mp4"}, {"filename": "noext"}]

    class FakeScheduler:
        @staticmethod
        def get_status() -> dict[str, Any]:
            return {"task_count": 2, "running": True}

        @staticmethod
        def list_tasks() -> list[dict[str, Any]]:
            return [{"name": "nightly", "mode": "sync", "enabled": True, "progress": 100, "last_run": "yesterday"}]

    class FakeCache:
        @staticmethod
        def get_stats() -> dict[str, Any]:
            return {"valid_entries": 4, "total_entries": 8, "total_access_count": 10, "default_ttl": 120, "running": True}

    monkeypatch.setattr(dashboard, "get_db", lambda: FakeDB())

    async def _get_scheduler() -> FakeScheduler:
        return FakeScheduler()

    async def _get_cache() -> FakeCache:
        return FakeCache()

    monkeypatch.setattr(dashboard, "get_task_scheduler", _get_scheduler)
    monkeypatch.setattr(dashboard, "get_link_cache", _get_cache)

    payload = await dashboard.get_dashboard_stats()

    assert payload["status"] == "ok"
    assert payload["stats"] == {"strm_count": 3, "task_count": 2, "cache_entries": 4, "cache_hit_rate": 50.0}
    assert payload["cache_detail"] == {"size": 4, "hit_rate": 50.0, "ttl": 120}
    assert payload["recent_tasks"][0]["name"] == "nightly"
    assert payload["services"][1]["status"] == "running"
    assert payload["file_types"] == {"mkv": 1, "mp4": 1, "unknown": 1}


@pytest.mark.asyncio
async def test_get_dashboard_stats_raises_http_500_on_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dashboard, "get_db", lambda: (_ for _ in ()).throw(RuntimeError("db boom")))

    with pytest.raises(HTTPException) as exc_info:
        await dashboard.get_dashboard_stats()

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "Failed to get dashboard stats"


@pytest.mark.asyncio
async def test_get_task_trends_builds_series(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeScheduler:
        @staticmethod
        def list_tasks() -> list[dict[str, Any]]:
            return [{"name": "a"}, {"name": "b"}, {"name": "c"}]

    async def _get_scheduler() -> FakeScheduler:
        return FakeScheduler()

    monkeypatch.setattr(dashboard, "get_task_scheduler", _get_scheduler)

    payload = await dashboard.get_task_trends(days=3)

    assert payload["status"] == "ok"
    assert len(payload["dates"]) == 3
    assert payload["success"] == [8, 7, 6]
    assert payload["failed"] == [1, 2, 3]


@pytest.mark.asyncio
async def test_get_task_trends_raises_http_500_on_error(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _raise_error() -> None:
        raise RuntimeError("scheduler boom")

    monkeypatch.setattr(dashboard, "get_task_scheduler", _raise_error)

    with pytest.raises(HTTPException) as exc_info:
        await dashboard.get_task_trends(days=1)

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "Failed to get task trends"
