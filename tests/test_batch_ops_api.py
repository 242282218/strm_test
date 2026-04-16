from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import batch_ops


@pytest.fixture(autouse=True)
def reset_operation_status() -> None:
    batch_ops._operation_status.clear()
    yield
    batch_ops._operation_status.clear()


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(batch_ops.router)
    app.dependency_overrides[batch_ops.require_api_key] = lambda: None
    app.dependency_overrides[batch_ops.get_db] = lambda: None
    return TestClient(app)


def test_batch_delete_strm_success_missing_and_failure(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    existing = tmp_path / "existing.strm"
    existing.write_text("http://ok", encoding="utf-8")
    missing = tmp_path / "missing.strm"
    failing = tmp_path / "failing.strm"
    failing.write_text("http://fail", encoding="utf-8")

    original_unlink = Path.unlink

    def fake_unlink(path: Path, *args, **kwargs) -> None:
        if path == failing:
            raise PermissionError("cannot delete")
        original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fake_unlink)

    response = client.post("/api/batch/delete/strm", json={"paths": [str(existing), str(missing), str(failing)]})

    assert response.status_code == 200
    assert response.json() == {
        "deleted_count": 2,
        "failed_count": 1,
        "failed_paths": [str(failing)],
    }
    assert not existing.exists()


def test_batch_generate_strm_creates_files_and_collects_failures(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    output_dir = tmp_path / "strm-out"

    original_open = open

    def fake_open(path, *args, **kwargs):
        if str(path).endswith("broken.strm"):
            raise OSError("disk full")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr("builtins.open", fake_open)

    response = client.post(
        "/api/batch/strm/generate",
        json={
            "output_dir": str(output_dir),
            "files": [
                {"name": "ok", "url": "http://ok"},
                {"name": "", "url": "http://invalid"},
                {"name": "broken", "url": "http://broken"},
                {"name": "missing-url", "url": ""},
            ],
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "success_count": 1,
        "failed_count": 3,
        "failed_files": [
            {"name": "", "url": "http://invalid"},
            {"name": "broken", "url": "http://broken"},
            {"name": "missing-url", "url": ""},
        ],
    }
    assert (output_dir / "ok.strm").read_text(encoding="utf-8") == "http://ok"
    assert not (output_dir / "broken.strm").exists()


def test_get_batch_operation_status_returns_404_for_unknown_operation(client: TestClient) -> None:
    response = client.get("/api/batch/status/not-found")

    assert response.status_code == 404
    assert response.json() == {"detail": "Operation not found"}


def test_operation_helper_functions_cover_lifecycle_fields() -> None:
    operation_id = batch_ops.create_batch_operation(total=3)
    created = batch_ops._operation_status[operation_id]
    assert created.status == "pending"
    assert created.total == 3
    assert created.completed_at is None

    batch_ops.update_batch_operation(operation_id, status="processing", processed=1, success=1, unknown_field=123)
    updated = batch_ops._operation_status[operation_id]
    assert updated.status == "processing"
    assert updated.processed == 1
    assert updated.success == 1

    batch_ops.complete_batch_operation(operation_id)
    completed = batch_ops._operation_status[operation_id]
    assert completed.status == "completed"
    assert completed.completed_at is not None

    failed_id = batch_ops.create_batch_operation(total=1)
    batch_ops.fail_batch_operation(failed_id, error="boom")
    failed = batch_ops._operation_status[failed_id]
    assert failed.status == "failed"
    assert failed.completed_at is not None

    batch_ops.update_batch_operation("unknown-id", status="failed")
    batch_ops.complete_batch_operation("unknown-id")
    batch_ops.fail_batch_operation("unknown-id", error="ignored")


def test_get_batch_operation_status_endpoint_returns_saved_operation(client: TestClient) -> None:
    operation_id = batch_ops.create_batch_operation(total=2)
    batch_ops.update_batch_operation(operation_id, status="processing", processed=2, success=2, failed=0)

    response = client.get(f"/api/batch/status/{operation_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["operation_id"] == operation_id
    assert payload["status"] == "processing"
    assert payload["processed"] == 2
    assert payload["success"] == 2
