from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.core import audit_log as audit_module


@pytest.fixture(autouse=True)
def reset_audit_logger_singleton() -> None:
    audit_module._global_audit_logger = None
    yield
    audit_module._global_audit_logger = None


def make_record(action: audit_module.AuditAction = audit_module.AuditAction.FILE_RENAME) -> audit_module.AuditRecord:
    return audit_module.AuditRecord(
        timestamp=datetime.now().isoformat(),
        action=action.value,
        level=audit_module.AuditLevel.INFO.value,
        user_id=None,
        user_name=None,
        ip_address=None,
        request_id=None,
        resource_type=None,
        resource_id=None,
        resource_name=None,
        before_value=None,
        after_value=None,
        status="success",
        error_message=None,
        metadata=None,
        duration_ms=None,
    )


def test_audit_record_to_dict_and_json() -> None:
    record = make_record()
    data = record.to_dict()
    assert data["action"] == "file_rename"
    assert data["status"] == "success"

    as_json = record.to_json()
    assert '"action": "file_rename"' in as_json


@pytest.mark.asyncio
async def test_logger_worker_write_and_stop(tmp_path: Path) -> None:
    logger = audit_module.AuditLogger(log_dir=str(tmp_path), async_queue_size=10)
    await logger.start()
    await logger.log(
        action=audit_module.AuditAction.FILE_DELETE,
        level=audit_module.AuditLevel.IMPORTANT,
        resource_name="demo.txt",
    )
    await logger.stop()

    today = datetime.now().strftime("%Y-%m-%d")
    log_file = tmp_path / f"audit_{today}.log"
    assert log_file.exists()
    content = log_file.read_text(encoding="utf-8")
    assert '"action": "file_delete"' in content
    assert '"resource_name": "demo.txt"' in content


@pytest.mark.asyncio
async def test_queue_full_falls_back_to_sync_write(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    logger = audit_module.AuditLogger(log_dir=str(tmp_path), async_queue_size=1)
    logger._queue.put_nowait(make_record(audit_module.AuditAction.FILE_DELETE))

    write_mock = AsyncMock()
    monkeypatch.setattr(logger, "_write_record", write_mock)

    await logger.log(action=audit_module.AuditAction.FILE_RENAME)
    write_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_rotate_and_cleanup_old_files(tmp_path: Path) -> None:
    logger = audit_module.AuditLogger(log_dir=str(tmp_path), max_file_size=1, max_files=1)

    old_a = tmp_path / "audit_2026-04-01.log"
    old_b = tmp_path / "audit_2026-04-02.log"
    old_c = tmp_path / "audit_2026-04-03.log"
    old_a.write_text("a", encoding="utf-8")
    old_b.write_text("b", encoding="utf-8")
    old_c.write_text("c", encoding="utf-8")
    os.utime(old_a, (1, 1))
    os.utime(old_b, (2, 2))
    os.utime(old_c, (3, 3))

    logger.current_size = 1
    await logger._rotate_if_needed()

    remaining = sorted(path.name for path in tmp_path.glob("audit_2026-04-*.log"))
    assert remaining == ["audit_2026-04-03.log"]
    assert logger.current_size == 0


@pytest.mark.asyncio
async def test_cleanup_old_files_error_is_swallowed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    logger = audit_module.AuditLogger(log_dir=str(tmp_path), max_files=1)

    original_glob: Callable[..., Any] = Path.glob

    def broken_glob(self: Path, pattern: str):
        if self == logger.log_dir:
            raise RuntimeError("glob failed")
        return original_glob(self, pattern)

    monkeypatch.setattr(Path, "glob", broken_glob)
    await logger._cleanup_old_files()


@pytest.mark.asyncio
async def test_write_record_io_error_is_swallowed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    logger = audit_module.AuditLogger(log_dir=str(tmp_path))

    class BrokenAioFile:
        async def __aenter__(self):
            raise OSError("write failed")

        async def __aexit__(self, _exc_type, _exc, _tb):
            return False

    monkeypatch.setattr(audit_module.aiofiles, "open", lambda *_args, **_kwargs: BrokenAioFile())
    await logger._write_record(make_record())


@pytest.mark.asyncio
async def test_convenience_methods_build_expected_payload(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    logger = audit_module.AuditLogger(log_dir=str(tmp_path))
    log_mock = AsyncMock()
    monkeypatch.setattr(logger, "log", log_mock)

    await logger.log_rename("old", "new", user_id="u1")
    kwargs = log_mock.await_args.kwargs
    assert kwargs["action"] == audit_module.AuditAction.FILE_RENAME
    assert kwargs["level"] == audit_module.AuditLevel.IMPORTANT
    assert kwargs["before_value"] == "old"
    assert kwargs["after_value"] == "new"

    await logger.log_batch_rename(
        files=[{"old": "a", "new": "b"}, {"old": "c", "new": "d"}],
        success_count=1,
        failure_count=1,
    )
    kwargs = log_mock.await_args.kwargs
    assert kwargs["status"] == "partial"
    assert kwargs["metadata"]["total_count"] == 2
    assert len(kwargs["metadata"]["files"]) == 2

    await logger.log_delete("target")
    kwargs = log_mock.await_args.kwargs
    assert kwargs["action"] == audit_module.AuditAction.FILE_DELETE
    assert kwargs["resource_name"] == "target"

    await logger.log_config_update("api_password", "secret-old", "secret-new")
    kwargs = log_mock.await_args.kwargs
    assert kwargs["resource_id"] == "api_password"
    assert kwargs["before_value"] == "***masked***"
    assert kwargs["after_value"] == "***masked***"

    await logger.log_task(audit_module.AuditAction.TASK_CREATE, task_id="t-1", task_name="demo", status="failure")
    kwargs = log_mock.await_args.kwargs
    assert kwargs["resource_type"] == "task"
    assert kwargs["resource_id"] == "t-1"
    assert kwargs["status"] == "failure"

    await logger.log_cloud_operation(audit_module.AuditAction.CLOUD_UPLOAD, cloud_type="quark", file_name="f.mp4")
    kwargs = log_mock.await_args.kwargs
    assert kwargs["resource_type"] == "cloud:quark"
    assert kwargs["resource_name"] == "f.mp4"


@pytest.mark.asyncio
async def test_audit_decorator_success_and_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []

    class FakeAudit:
        async def log(self, **kwargs: Any) -> None:
            calls.append(kwargs)

    monkeypatch.setattr(audit_module, "get_audit_logger", lambda: FakeAudit())

    @audit_module.audit_log(
        action=audit_module.AuditAction.FILE_COPY,
        level=audit_module.AuditLevel.CRITICAL,
        resource_type="file",
        get_resource_name=lambda name: name,
    )
    async def do_copy(name: str) -> str:
        return f"ok:{name}"

    @audit_module.audit_log(
        action=audit_module.AuditAction.FILE_MOVE,
        get_resource_name=lambda *_args, **_kwargs: 1 / 0,
    )
    async def do_fail(_name: str) -> None:
        raise ValueError("boom")

    assert await do_copy("a.txt") == "ok:a.txt"
    assert calls[-1]["status"] == "success"
    assert calls[-1]["resource_name"] == "a.txt"
    assert calls[-1]["duration_ms"] >= 0

    with pytest.raises(ValueError, match="boom"):
        await do_fail("b.txt")

    assert calls[-1]["status"] == "failure"
    assert calls[-1]["resource_name"] is None
    assert calls[-1]["error_message"] == "boom"


def test_get_audit_logger_singleton() -> None:
    logger_a = audit_module.get_audit_logger()
    logger_b = audit_module.get_audit_logger()
    assert logger_a is logger_b
