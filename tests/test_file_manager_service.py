from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.schemas.file_manager import FileOperationAction, FileOperationRequest, StorageType
from app.services import file_manager_service as fms


class _FakeProvider:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    async def list(self, path: str, page: int, size: int):
        self.calls.append(("list", path, page, size))
        return [], 0, None

    async def move_batch(self, paths: list[str], target: str):
        self.calls.append(("move", tuple(paths), target))

    async def delete_batch(self, paths: list[str]):
        self.calls.append(("delete", tuple(paths)))

    async def rename(self, path: str, target: str):
        self.calls.append(("rename", path, target))
        return {"ok": True}

    async def mkdir(self, parent: str, target: str):
        self.calls.append(("mkdir", parent, target))
        return {"path": f"{parent}/{target}"}


def test_init_keeps_local_provider_when_available(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fms, "QuarkStorageProvider", lambda: _FakeProvider())
    monkeypatch.setattr(fms, "LocalStorageProvider", lambda: _FakeProvider())

    service = fms.FileManagerService()

    assert StorageType.QUARK in service._providers
    assert StorageType.LOCAL in service._providers


def test_init_ignores_local_provider_http_5xx(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fms, "QuarkStorageProvider", lambda: _FakeProvider())
    monkeypatch.setattr(fms, "LocalStorageProvider", lambda: (_ for _ in ()).throw(HTTPException(status_code=503, detail="down")))

    service = fms.FileManagerService()

    assert StorageType.QUARK in service._providers
    assert StorageType.LOCAL not in service._providers


def test_init_raises_local_provider_http_4xx(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fms, "QuarkStorageProvider", lambda: _FakeProvider())
    monkeypatch.setattr(fms, "LocalStorageProvider", lambda: (_ for _ in ()).throw(HTTPException(status_code=400, detail="bad")))

    with pytest.raises(HTTPException):
        fms.FileManagerService()


def test_get_provider_raises_on_unknown_storage(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fms, "QuarkStorageProvider", lambda: _FakeProvider())
    monkeypatch.setattr(fms, "LocalStorageProvider", lambda: _FakeProvider())
    service = fms.FileManagerService()
    service._providers.pop(StorageType.LOCAL, None)

    with pytest.raises(HTTPException, match="not supported"):
        service._get_provider(StorageType.LOCAL)


@pytest.mark.asyncio
async def test_browse_converts_quark_root_to_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fms, "QuarkStorageProvider", lambda: _FakeProvider())
    monkeypatch.setattr(fms, "LocalStorageProvider", lambda: _FakeProvider())
    service = fms.FileManagerService()
    provider = service._providers[StorageType.QUARK]

    response = await service.browse(StorageType.QUARK, path="/", page=2, size=10)

    assert response.path == "0"
    assert provider.calls[0] == ("list", "0", 2, 10)


@pytest.mark.asyncio
async def test_browse_uses_raw_local_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fms, "QuarkStorageProvider", lambda: _FakeProvider())
    monkeypatch.setattr(fms, "LocalStorageProvider", lambda: _FakeProvider())
    service = fms.FileManagerService()
    provider = service._providers[StorageType.LOCAL]

    response = await service.browse(StorageType.LOCAL, path="C:/data", page=1, size=5)

    assert response.path == "C:/data"
    assert provider.calls[0] == ("list", "C:/data", 1, 5)


@pytest.mark.asyncio
async def test_handle_move_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fms, "QuarkStorageProvider", lambda: _FakeProvider())
    monkeypatch.setattr(fms, "LocalStorageProvider", lambda: _FakeProvider())
    service = fms.FileManagerService()
    request = FileOperationRequest(
        action=FileOperationAction.MOVE, storage=StorageType.QUARK, paths=["a", "b"], target="dst"
    )

    result = await service.handle_operation(request)

    assert result == {"status": "success", "action": "move", "count": 2}


@pytest.mark.asyncio
async def test_handle_move_requires_target(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fms, "QuarkStorageProvider", lambda: _FakeProvider())
    monkeypatch.setattr(fms, "LocalStorageProvider", lambda: _FakeProvider())
    service = fms.FileManagerService()
    request = FileOperationRequest(action=FileOperationAction.MOVE, storage=StorageType.QUARK, paths=["a"], target=None)

    with pytest.raises(HTTPException, match="Target path is required"):
        await service.handle_operation(request)


@pytest.mark.asyncio
async def test_handle_delete_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fms, "QuarkStorageProvider", lambda: _FakeProvider())
    monkeypatch.setattr(fms, "LocalStorageProvider", lambda: _FakeProvider())
    service = fms.FileManagerService()
    request = FileOperationRequest(action=FileOperationAction.DELETE, storage=StorageType.QUARK, paths=["a"], target=None)

    result = await service.handle_operation(request)

    assert result == {"status": "success", "action": "delete", "count": 1}


@pytest.mark.asyncio
async def test_handle_rename_collects_success_and_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fms, "QuarkStorageProvider", lambda: _FakeProvider())
    monkeypatch.setattr(fms, "LocalStorageProvider", lambda: _FakeProvider())
    service = fms.FileManagerService()
    provider = service._providers[StorageType.QUARK]

    async def _rename(path: str, target: str):
        if path == "bad":
            raise RuntimeError("rename failed")
        return {"ok": True}

    provider.rename = _rename  # type: ignore[method-assign]
    request = FileOperationRequest(
        action=FileOperationAction.RENAME,
        storage=StorageType.QUARK,
        paths=["ok", "bad"],
        target="new-name",
    )

    result = await service.handle_operation(request)

    assert result["status"] == "success"
    assert result["results"][0] == {"path": "ok", "success": True}
    assert result["results"][1]["success"] is False
    assert "rename failed" in result["results"][1]["error"]


@pytest.mark.asyncio
async def test_handle_mkdir_success_uses_default_parent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fms, "QuarkStorageProvider", lambda: _FakeProvider())
    monkeypatch.setattr(fms, "LocalStorageProvider", lambda: _FakeProvider())
    service = fms.FileManagerService()
    request = FileOperationRequest(action=FileOperationAction.MKDIR, storage=StorageType.QUARK, paths=[], target="folder")

    result = await service.handle_operation(request)

    assert result["status"] == "success"
    assert result["result"]["path"] == "0/folder"


@pytest.mark.asyncio
async def test_handle_mkdir_wraps_provider_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fms, "QuarkStorageProvider", lambda: _FakeProvider())
    monkeypatch.setattr(fms, "LocalStorageProvider", lambda: _FakeProvider())
    service = fms.FileManagerService()
    provider = service._providers[StorageType.QUARK]

    async def _mkdir(parent: str, target: str):
        raise RuntimeError("mkdir failed")

    provider.mkdir = _mkdir  # type: ignore[method-assign]
    request = FileOperationRequest(action=FileOperationAction.MKDIR, storage=StorageType.QUARK, paths=["p"], target="folder")

    with pytest.raises(HTTPException, match="mkdir failed"):
        await service.handle_operation(request)


@pytest.mark.asyncio
async def test_handle_unknown_action_returns_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fms, "QuarkStorageProvider", lambda: _FakeProvider())
    monkeypatch.setattr(fms, "LocalStorageProvider", lambda: _FakeProvider())
    service = fms.FileManagerService()
    request = SimpleNamespace(storage=StorageType.QUARK, action="unknown", paths=[], target=None)

    result = await service.handle_operation(request)  # type: ignore[arg-type]

    assert result == {"status": "error", "message": "Unknown action"}
