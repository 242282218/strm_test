from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import HTTPException

from app.api import dashboard


@pytest.fixture(autouse=True)
def reset_dashboard_globals() -> None:
    dashboard._task_scheduler = None
    dashboard._link_cache = None
    yield
    dashboard._task_scheduler = None
    dashboard._link_cache = None


def test_get_strm_files_uses_primary_db_entrypoint(monkeypatch: pytest.MonkeyPatch) -> None:
    seen_sessions: list[object] = []

    @contextmanager
    def fake_session_context():
        session = object()
        seen_sessions.append(session)
        yield session

    class FakeRecord:
        def __init__(self, payload: dict[str, str]) -> None:
            self._payload = payload

        def to_dict(self) -> dict[str, str]:
            return self._payload

    class FakeStrmRecord:
        @staticmethod
        def get_all(session: object) -> list[FakeRecord]:
            assert session is seen_sessions[0]
            return [FakeRecord({"file_name": "episode01.mkv"})]

    monkeypatch.setattr(dashboard, "get_db_session", fake_session_context)
    monkeypatch.setattr(dashboard, "StrmRecord", FakeStrmRecord)

    assert dashboard.get_strm_files() == [{"file_name": "episode01.mkv"}]


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


def test_get_services_status_reflects_cookie_state() -> None:
    app_config = SimpleNamespace(quark=SimpleNamespace(cookie="cookie"))
    services = dashboard.get_services_status({"running": True}, {"running": False}, app_config)

    assert services == [
        {"name": "API服务", "status": "running"},
        {"name": "任务调度器", "status": "running"},
        {"name": "缓存服务", "status": "stopped"},
        {"name": "Emby代理", "status": "running"},
    ]


def test_calculate_file_types_counts_extensions_and_unknown() -> None:
    files = [
        {"filename": "a.MKV"},
        {"file_name": "b.mp4"},
        {"name": "noext"},
        {"filename": "b.mp4"},
    ]

    assert dashboard.calculate_file_types(files) == {"mkv": 1, "mp4": 2, "unknown": 1}


@pytest.mark.asyncio
async def test_get_dashboard_stats_success(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeScheduler:
        @staticmethod
        def get_status() -> dict[str, Any]:
            return {"task_count": 99, "running": True}

    class FakeCache:
        @staticmethod
        def get_stats() -> dict[str, Any]:
            return {"valid_entries": 4, "total_entries": 8, "total_access_count": 10, "default_ttl": 120, "running": True}

    monkeypatch.setattr(
        dashboard,
        "get_strm_files",
        lambda: [{"file_name": "a.mkv"}, {"file_name": "b.mp4"}, {"name": "noext"}],
    )
    monkeypatch.setattr(
        dashboard,
        "get_config_service",
        lambda: SimpleNamespace(get_config=lambda: SimpleNamespace(quark=SimpleNamespace(cookie="cookie"))),
    )

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
    monkeypatch.setattr(dashboard, "get_strm_files", lambda: (_ for _ in ()).throw(RuntimeError("db boom")))

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
