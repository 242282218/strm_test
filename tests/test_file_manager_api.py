from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi import FastAPI, HTTPException, status
from fastapi.testclient import TestClient

import app.api.file_manager as file_manager_api
from app.schemas.file_manager import StorageType
from app.services.file_manager_service import FileManagerService
from app.services.storage.local import LocalStorageProvider


class ExplodingFileManagerService:
    async def browse(self, storage, path, page, size):
        raise RuntimeError("browse failed: secret filesystem path")

    async def handle_operation(self, request):
        raise RuntimeError("operation failed: secret filesystem path")


class _FakeQuarkStorageProvider:
    async def list(self, path, page, size):
        return [], 0, None


def create_file_manager_app() -> FastAPI:
    app = FastAPI()
    app.include_router(file_manager_api.router)
    app.dependency_overrides[file_manager_api.require_api_key] = lambda: None
    app.dependency_overrides[file_manager_api.get_file_manager_service] = lambda: ExplodingFileManagerService()
    return app


def test_browse_does_not_leak_internal_error_details() -> None:
    client = TestClient(create_file_manager_app())

    response = client.get("/files/browse")

    assert response.status_code == 500
    assert response.json() == {"detail": "Failed to browse files"}


def test_operation_does_not_leak_internal_error_details() -> None:
    client = TestClient(create_file_manager_app())

    response = client.post(
        "/files/operation",
        json={
            "action": "delete",
            "storage": "quark",
            "paths": ["/tmp/demo"],
        },
    )

    assert response.status_code == 500
    assert response.json() == {"detail": "Failed to process file operation"}


def test_local_storage_provider_requires_explicit_root_when_env_missing(monkeypatch) -> None:
    monkeypatch.delenv("SMART_MEDIA_LOCAL_ROOT", raising=False)

    with pytest.raises(HTTPException) as exc_info:
        LocalStorageProvider()

    assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert exc_info.value.detail == "SMART_MEDIA_LOCAL_ROOT must be set for local storage"


@pytest.mark.asyncio
async def test_file_manager_service_allows_quark_when_local_storage_is_unavailable() -> None:
    local_storage_error = HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="SMART_MEDIA_LOCAL_ROOT must be set for local storage",
    )

    with patch("app.services.file_manager_service.LocalStorageProvider", side_effect=local_storage_error):
        with patch("app.services.file_manager_service.QuarkStorageProvider", return_value=_FakeQuarkStorageProvider()):
            service = FileManagerService()
            response = await service.browse(StorageType.QUARK, "0")

    assert response.total == 0
    assert response.path == "0"
