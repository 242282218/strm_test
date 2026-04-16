from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.schemas.cloud_drive import CloudDriveCreate, CloudDriveUpdate
from app.services import cloud_drive_service as cds


def test_get_drives_uses_pagination_chain() -> None:
    db = MagicMock()
    query = db.query.return_value
    query.offset.return_value = query
    query.limit.return_value = query
    query.all.return_value = ["d1", "d2"]

    service = cds.CloudDriveService(db)
    result = service.get_drives(skip=5, limit=10)

    assert result == ["d1", "d2"]
    query.offset.assert_called_once_with(5)
    query.limit.assert_called_once_with(10)


def test_get_drive_returns_first_match() -> None:
    db = MagicMock()
    query = db.query.return_value
    query.filter.return_value = query
    query.first.return_value = "drive"

    service = cds.CloudDriveService(db)

    assert service.get_drive(7) == "drive"


def test_get_default_drive_uses_ordered_query() -> None:
    db = MagicMock()
    query = db.query.return_value
    query.filter.return_value = query
    query.order_by.return_value = query
    query.first.return_value = "default-drive"

    service = cds.CloudDriveService(db)

    assert service.get_default_drive() == "default-drive"
    query.order_by.assert_called_once()


def test_create_drive_adds_and_commits() -> None:
    db = MagicMock()
    service = cds.CloudDriveService(db)
    payload = CloudDriveCreate(name="Q1", drive_type="quark", cookie="cookie", remark="r")

    created = service.create_drive(payload)

    assert created.name == "Q1"
    assert created.drive_type == "quark"
    db.add.assert_called_once()
    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(created)


def test_update_drive_returns_none_when_not_found() -> None:
    db = MagicMock()
    service = cds.CloudDriveService(db)
    service.get_drive = MagicMock(return_value=None)  # type: ignore[method-assign]

    result = service.update_drive(1, CloudDriveUpdate(name="n"))

    assert result is None
    db.commit.assert_not_called()


def test_update_drive_applies_partial_fields() -> None:
    db = MagicMock()
    service = cds.CloudDriveService(db)
    drive = SimpleNamespace(name="old", remark="old", status="active")
    service.get_drive = MagicMock(return_value=drive)  # type: ignore[method-assign]

    updated = service.update_drive(1, CloudDriveUpdate(name="new", remark="new-remark"))

    assert updated is drive
    assert drive.name == "new"
    assert drive.remark == "new-remark"
    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(drive)


def test_delete_drive_returns_false_when_missing() -> None:
    db = MagicMock()
    service = cds.CloudDriveService(db)
    service.get_drive = MagicMock(return_value=None)  # type: ignore[method-assign]

    assert service.delete_drive(1) is False
    db.delete.assert_not_called()


def test_delete_drive_success() -> None:
    db = MagicMock()
    service = cds.CloudDriveService(db)
    drive = SimpleNamespace(id=1)
    service.get_drive = MagicMock(return_value=drive)  # type: ignore[method-assign]

    assert service.delete_drive(1) is True
    db.delete.assert_called_once_with(drive)
    db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_check_cookie_returns_false_when_drive_missing() -> None:
    service = cds.CloudDriveService(MagicMock())
    service.get_drive = MagicMock(return_value=None)  # type: ignore[method-assign]

    assert await service.check_cookie(1) is False


@pytest.mark.asyncio
async def test_check_cookie_returns_false_for_non_quark_drive() -> None:
    service = cds.CloudDriveService(MagicMock())
    drive = SimpleNamespace(drive_type="115")
    service.get_drive = MagicMock(return_value=drive)  # type: ignore[method-assign]

    assert await service.check_cookie(1) is False


@pytest.mark.asyncio
async def test_check_cookie_success_updates_status_and_closes(monkeypatch: pytest.MonkeyPatch) -> None:
    db = MagicMock()
    service = cds.CloudDriveService(db)
    drive = SimpleNamespace(name="q", drive_type="quark", cookie="cookie", status="expired", last_check=None)
    service.get_drive = MagicMock(return_value=drive)  # type: ignore[method-assign]
    calls: dict[str, int] = {"closed": 0}

    class _FakeQuarkService:
        def __init__(self, cookie: str) -> None:
            self.cookie = cookie

        async def get_files(self, parent: str, page_size: int):
            return []

        async def close(self):
            calls["closed"] += 1

    monkeypatch.setattr(cds, "QuarkService", _FakeQuarkService)

    result = await service.check_cookie(1)

    assert result is True
    assert drive.status == "active"
    assert isinstance(drive.last_check, datetime)
    assert calls["closed"] == 1
    assert db.commit.call_count == 1


@pytest.mark.asyncio
async def test_check_cookie_failure_marks_expired_and_closes(monkeypatch: pytest.MonkeyPatch) -> None:
    db = MagicMock()
    service = cds.CloudDriveService(db)
    drive = SimpleNamespace(name="q", drive_type="quark", cookie="cookie", status="active", last_check=None)
    service.get_drive = MagicMock(return_value=drive)  # type: ignore[method-assign]
    calls: dict[str, int] = {"closed": 0}

    class _FakeQuarkService:
        def __init__(self, cookie: str) -> None:
            self.cookie = cookie

        async def get_files(self, parent: str, page_size: int):
            raise RuntimeError("invalid cookie")

        async def close(self):
            calls["closed"] += 1

    monkeypatch.setattr(cds, "QuarkService", _FakeQuarkService)

    result = await service.check_cookie(1)

    assert result is False
    assert drive.status == "expired"
    assert isinstance(drive.last_check, datetime)
    assert calls["closed"] == 1
    assert db.commit.call_count == 1
