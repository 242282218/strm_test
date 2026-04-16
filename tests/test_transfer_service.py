from __future__ import annotations

import sys
import types
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services import transfer_service as ts


class FakeBackgroundTasks:
    def __init__(self) -> None:
        self.calls: list[tuple[object, int]] = []

    def add_task(self, func, task_id: int) -> None:
        self.calls.append((func, task_id))


def _build_transfer_service(
    monkeypatch: pytest.MonkeyPatch,
    *,
    drive: object | None = None,
    config_cookie: str = "global-cookie",
    share_token: str | None = "token",
    share_files: list[dict[str, str]] | None = None,
    target: object | None = None,
) -> tuple[ts.TransferService, AsyncMock, list[SimpleNamespace]]:
    service = ts.TransferService(db_session=object())
    service.cloud_drive_service = SimpleNamespace(get_drive=lambda _drive_id: drive)
    service._resolve_target_directory = AsyncMock(
        return_value=target or SimpleNamespace(fid="target-fid", is_dir=True)
    )  # type: ignore[method-assign]

    config = SimpleNamespace(quark=SimpleNamespace(cookie=config_cookie))
    monkeypatch.setattr(ts, "get_config_service", lambda: SimpleNamespace(get_config=lambda: config))

    save_share = AsyncMock(return_value=None)
    instances: list[SimpleNamespace] = []

    class FakeQuarkService:
        def __init__(self, cookie: str) -> None:
            self.cookie = cookie
            self.client = SimpleNamespace(
                get_share_token=AsyncMock(return_value=share_token),
                get_share_files=AsyncMock(return_value=share_files if share_files is not None else [{"fid": "f1"}]),
                save_share=save_share,
            )
            self.closed = False
            instances.append(self)

        async def close(self) -> None:
            self.closed = True

    monkeypatch.setattr(ts, "QuarkService", FakeQuarkService)
    return service, save_share, instances


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("https://pan.quark.cn/s/abcdef123456", "abcdef123456"),
        ("abcdef123456", "abcdef123456"),
        ("invalid-url", None),
    ],
)
def test_extract_pwd_id_supports_share_url_and_raw_input(raw: str, expected: str | None) -> None:
    service = ts.TransferService(db_session=object())
    assert service._extract_pwd_id(raw) == expected


@pytest.mark.asyncio
async def test_resolve_target_directory_retries_until_found(monkeypatch: pytest.MonkeyPatch) -> None:
    service = ts.TransferService(db_session=object())
    target = SimpleNamespace(fid="target", is_dir=True)
    attempts = {"count": 0}
    sleeps: list[float] = []

    async def fake_get_file_by_path(_path: str):
        attempts["count"] += 1
        if attempts["count"] < 3:
            return None
        return target

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr(ts.asyncio, "sleep", fake_sleep)
    quark = SimpleNamespace(get_file_by_path=fake_get_file_by_path)

    found = await service._resolve_target_directory(quark, "/Movies", retries=4, retry_delay_seconds=0.01)

    assert found is target
    assert attempts["count"] == 3
    assert sleeps == [0.01, 0.01]


@pytest.mark.asyncio
async def test_resolve_target_directory_returns_none_after_exhausting_retries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = ts.TransferService(db_session=object())
    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr(ts.asyncio, "sleep", fake_sleep)
    quark = SimpleNamespace(get_file_by_path=AsyncMock(return_value=None))

    found = await service._resolve_target_directory(quark, "/Movies", retries=2, retry_delay_seconds=0.02)

    assert found is None
    assert sleeps == [0.02, 0.02]


@pytest.mark.asyncio
async def test_transfer_share_rejects_invalid_share_url(monkeypatch: pytest.MonkeyPatch) -> None:
    service, _save_share, _instances = _build_transfer_service(monkeypatch)

    with pytest.raises(ValueError, match="Invalid share URL"):
        await service.transfer_share(None, "bad", "/target")


@pytest.mark.asyncio
async def test_transfer_share_rejects_missing_or_invalid_drive(monkeypatch: pytest.MonkeyPatch) -> None:
    missing_drive_service, _save_share, _instances = _build_transfer_service(monkeypatch, drive=None)
    with pytest.raises(ValueError, match="Drive 7 not found"):
        await missing_drive_service.transfer_share(7, "abcdef123456", "/target")

    not_quark = SimpleNamespace(drive_type="onedrive", cookie="cookie")
    invalid_type_service, _save_share, _instances = _build_transfer_service(monkeypatch, drive=not_quark)
    with pytest.raises(ValueError, match="Only quark drive is supported for transfer"):
        await invalid_type_service.transfer_share(7, "abcdef123456", "/target")

    empty_cookie = SimpleNamespace(drive_type="quark", cookie=" ")
    empty_cookie_service, _save_share, _instances = _build_transfer_service(monkeypatch, drive=empty_cookie)
    with pytest.raises(ValueError, match="cookie is empty"):
        await empty_cookie_service.transfer_share(7, "abcdef123456", "/target")


@pytest.mark.asyncio
async def test_transfer_share_rejects_empty_global_cookie(monkeypatch: pytest.MonkeyPatch) -> None:
    service, _save_share, _instances = _build_transfer_service(monkeypatch, config_cookie=" ")

    with pytest.raises(ValueError, match="quark.cookie is empty"):
        await service.transfer_share(None, "abcdef123456", "/target")


@pytest.mark.asyncio
async def test_transfer_share_raises_when_share_files_missing_and_still_closes_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    drive = SimpleNamespace(drive_type="quark", cookie="drive-cookie")
    service, _save_share, instances = _build_transfer_service(monkeypatch, drive=drive, share_files=[])

    with pytest.raises(ValueError, match="No files found in share"):
        await service.transfer_share(1, "abcdef123456", "/target")

    assert instances[0].closed is True


@pytest.mark.asyncio
async def test_transfer_share_raises_when_target_directory_missing_or_not_directory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    drive = SimpleNamespace(drive_type="quark", cookie="drive-cookie")
    missing_target_service, _save_share, instances = _build_transfer_service(monkeypatch, drive=drive, target=None)
    missing_target_service._resolve_target_directory = AsyncMock(return_value=None)  # type: ignore[method-assign]

    with pytest.raises(ValueError, match="Target directory /target not found"):
        await missing_target_service.transfer_share(1, "abcdef123456", "/target")

    assert instances[0].closed is True

    file_target = SimpleNamespace(fid="target-fid", is_dir=False)
    not_dir_service, _save_share, instances = _build_transfer_service(monkeypatch, drive=drive, target=file_target)

    with pytest.raises(ValueError, match="is not a directory"):
        await not_dir_service.transfer_share(1, "abcdef123456", "/target")

    assert instances[0].closed is True


@pytest.mark.asyncio
async def test_transfer_share_success_with_drive_cookie_calls_save_share(monkeypatch: pytest.MonkeyPatch) -> None:
    drive = SimpleNamespace(drive_type="quark", cookie="drive-cookie")
    service, save_share, instances = _build_transfer_service(
        monkeypatch,
        drive=drive,
        share_files=[{"fid": "f1"}, {"fid": "f2"}],
    )

    await service.transfer_share(5, "abcdef123456", "/target")

    save_share.assert_awaited_once_with("abcdef123456", "token", ["f1", "f2"], "target-fid")
    assert instances[0].cookie == "drive-cookie"
    assert instances[0].closed is True


@pytest.mark.asyncio
async def test_transfer_share_auto_organize_skips_when_drive_id_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    warnings: list[str] = []
    service, _save_share, instances = _build_transfer_service(monkeypatch)
    monkeypatch.setattr(ts.logger, "warning", lambda message: warnings.append(message))

    await service.transfer_share(None, "abcdef123456", "/target", auto_organize=True)

    assert any("Auto-organize skipped because drive_id is missing" in message for message in warnings)
    assert instances[0].closed is True


@pytest.mark.asyncio
async def test_transfer_share_auto_organize_creates_task_and_starts_runner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    drive = SimpleNamespace(drive_type="quark", cookie="drive-cookie")
    service, _save_share, instances = _build_transfer_service(monkeypatch, drive=drive)
    background_tasks = FakeBackgroundTasks()
    created_tasks: list[object] = []

    class FakeTaskCreate:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

    class FakeTaskService:
        def __init__(self, _db) -> None:
            pass

        def create_task(self, task_in):
            created_tasks.append(task_in)
            return SimpleNamespace(id=99)

    class FakeTaskRunner:
        @staticmethod
        def run_task(task_id: int) -> None:
            return None

    monkeypatch.setitem(sys.modules, "app.schemas.task", types.SimpleNamespace(TaskCreate=FakeTaskCreate))
    monkeypatch.setitem(sys.modules, "app.services.platform.task_queue", types.SimpleNamespace(TaskService=FakeTaskService))
    monkeypatch.setitem(sys.modules, "app.services.platform.task_runner", types.SimpleNamespace(TaskRunner=FakeTaskRunner))

    await service.transfer_share(9, "abcdef123456", "/target", auto_organize=True, background_tasks=background_tasks)

    assert len(created_tasks) == 1
    params = created_tasks[0].kwargs["params"]
    assert params["drive_id"] == 9
    assert params["source_dir"] == "/target"
    assert background_tasks.calls == [(FakeTaskRunner.run_task, 99)]
    assert instances[0].closed is True


@pytest.mark.asyncio
async def test_transfer_share_auto_organize_logs_when_background_tasks_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    drive = SimpleNamespace(drive_type="quark", cookie="drive-cookie")
    service, _save_share, _instances = _build_transfer_service(monkeypatch, drive=drive)
    warnings: list[str] = []
    created_tasks: list[object] = []

    class FakeTaskCreate:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

    class FakeTaskService:
        def __init__(self, _db) -> None:
            pass

        def create_task(self, task_in):
            created_tasks.append(task_in)
            return SimpleNamespace(id=7)

    class FakeTaskRunner:
        @staticmethod
        def run_task(task_id: int) -> None:
            return None

    monkeypatch.setitem(sys.modules, "app.schemas.task", types.SimpleNamespace(TaskCreate=FakeTaskCreate))
    monkeypatch.setitem(sys.modules, "app.services.platform.task_queue", types.SimpleNamespace(TaskService=FakeTaskService))
    monkeypatch.setitem(sys.modules, "app.services.platform.task_runner", types.SimpleNamespace(TaskRunner=FakeTaskRunner))
    monkeypatch.setattr(ts.logger, "warning", lambda message: warnings.append(message))

    await service.transfer_share(9, "abcdef123456", "/target", auto_organize=True, background_tasks=None)

    assert len(created_tasks) == 1
    assert any("not started immediately" in message for message in warnings)
