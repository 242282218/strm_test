from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace
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
    frozen_now = datetime(2026, 4, 17, 12, 0, 0)
    tasks = [
        SimpleNamespace(
            task_type="file_sync",
            status="planning" if idx == 0 else "completed",
            progress=idx * 10,
            params={"remote_path": f"/video/season-{idx}"},
            created_at=frozen_now - timedelta(hours=idx),
            started_at=None,
            completed_at=None,
        )
        for idx in range(7)
    ]

    recent_tasks = dashboard.get_recent_tasks(tasks)

    assert len(recent_tasks) == 5
    assert recent_tasks[0]["name"] == "文件同步 · /video/season-0"
    assert recent_tasks[0]["status"] == "planning"
    assert recent_tasks[1]["progress"] == 10
    assert recent_tasks[4]["time"] == (frozen_now - timedelta(hours=4)).isoformat()


def test_get_recent_tasks_returns_empty_on_error() -> None:
    class BrokenTask:
        def __getattr__(self, _name: str) -> Any:
            raise RuntimeError("task broken")

    assert dashboard.get_recent_tasks([BrokenTask()]) == []


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
            return {"task_count": 99, "running": True}

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
    monkeypatch.setattr(dashboard, "count_platform_tasks", lambda: 2)
    monkeypatch.setattr(
        dashboard,
        "get_platform_tasks",
        lambda limit=None, since=None: [
            SimpleNamespace(
                task_type="strm_generation",
                status="completed",
                progress=100,
                params={"source_dir": "/media/library"},
                created_at=datetime(2026, 4, 17, 10, 0, 0),
                started_at=datetime(2026, 4, 17, 10, 1, 0),
                completed_at=datetime(2026, 4, 17, 10, 5, 0),
            )
        ],
    )

    payload = await dashboard.get_dashboard_stats()

    assert payload["status"] == "ok"
    assert payload["stats"] == {"strm_count": 3, "task_count": 2, "cache_entries": 4, "cache_hit_rate": 50.0}
    assert payload["cache_detail"] == {"size": 4, "hit_rate": 50.0, "ttl": 120}
    assert payload["recent_tasks"][0]["name"] == "生成 STRM · /media/library"
    assert payload["recent_tasks"][0]["status"] == "completed"
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
    frozen_now = datetime(2026, 4, 17, 9, 0, 0)

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return frozen_now
            return frozen_now.astimezone(tz)

    monkeypatch.setattr(dashboard, "datetime", FrozenDateTime)
    monkeypatch.setattr(
        dashboard,
        "get_platform_tasks",
        lambda limit=None, since=None: [
            SimpleNamespace(
                status="completed",
                created_at=frozen_now - timedelta(days=2, hours=2),
                completed_at=frozen_now - timedelta(days=2, hours=1),
            ),
            SimpleNamespace(
                status="partial_success",
                created_at=frozen_now - timedelta(days=1, hours=2),
                completed_at=frozen_now - timedelta(days=1, hours=1),
            ),
            SimpleNamespace(
                status="failed",
                created_at=frozen_now - timedelta(days=1, hours=4),
                completed_at=frozen_now - timedelta(days=1, hours=3),
            ),
            SimpleNamespace(
                status="cancelled",
                created_at=frozen_now - timedelta(hours=2),
                completed_at=frozen_now - timedelta(hours=1),
            ),
            SimpleNamespace(
                status="running",
                created_at=frozen_now - timedelta(hours=1),
                completed_at=None,
            ),
        ],
    )

    payload = await dashboard.get_task_trends(days=3)

    assert payload["status"] == "ok"
    assert len(payload["dates"]) == 3
    assert payload["success"] == [1, 1, 0]
    assert payload["failed"] == [0, 1, 1]


@pytest.mark.asyncio
async def test_get_task_trends_raises_http_500_on_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        dashboard,
        "get_platform_tasks",
        lambda limit=None, since=None: (_ for _ in ()).throw(RuntimeError("tasks boom")),
    )

    with pytest.raises(HTTPException) as exc_info:
        await dashboard.get_task_trends(days=1)

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "Failed to get task trends"
