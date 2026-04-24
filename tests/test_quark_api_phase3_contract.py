import asyncio
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.quark import (
    QuarkWorkflowTaskRequest,
    _base_workflow_task,
    _cloud_workflow_handles,
    _cloud_workflow_tasks,
    _run_cloud_workflow_task,
    router,
)


@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(router)
    return app


def test_quark_config_uses_runtime_quark_facade(app):
    mock_quark_config = SimpleNamespace(
        cookie="test_cookie",
        referer="https://pan.quark.cn/",
        root_id="0",
        only_video=True,
    )

    with patch("app.api.quark._get_runtime_quark_config", return_value=mock_quark_config):
        client = TestClient(app)
        response = client.get("/api/quark/config")

    assert response.status_code == 200
    assert response.json() == {
        "referer": "https://pan.quark.cn/",
        "root_id": "0",
        "only_video": True,
        "cookie_configured": True,
    }


def test_quark_sync_reads_cookie_from_runtime_quark_facade(app):
    mock_quark_config = SimpleNamespace(cookie=None, root_id="0", only_video=True)

    with patch("app.api.quark._get_runtime_quark_config", return_value=mock_quark_config):
        client = TestClient(app)
        response = client.post("/api/quark/sync")

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_workflow_task_reuses_internal_routes_without_auth_kwarg():
    task_id = str(uuid.uuid4())
    request = QuarkWorkflowTaskRequest(
        pdir_fid="test_fid",
        algorithm="standard",
        naming_standard="emby",
        auto_execute=True,
    )
    _cloud_workflow_tasks[task_id] = _base_workflow_task(task_id, request)
    _cloud_workflow_handles[task_id] = asyncio.current_task()

    preview_response = {
        "data": {
            "batch_id": "batch-1",
            "total_items": 1,
            "items": [{"fid": "file1", "new_name": "renamed.mp4"}],
        }
    }
    execute_response = {
        "data": {
            "success": 1,
            "failed": 0,
            "skipped": 0,
        }
    }

    try:
        with patch("app.api.quark.smart_rename_cloud_files", AsyncMock(return_value=preview_response)) as mock_preview:
            with patch("app.api.quark.execute_cloud_rename", AsyncMock(return_value=execute_response)) as mock_execute:
                await _run_cloud_workflow_task(task_id, request, "test_cookie")

        mock_preview.assert_awaited_once_with(request=request, _cookie="test_cookie")
        mock_execute.assert_awaited_once()
        execute_kwargs = mock_execute.await_args.kwargs
        assert execute_kwargs["_cookie"] == "test_cookie"
        assert "request" in execute_kwargs
        assert "_auth" not in execute_kwargs
        assert _cloud_workflow_tasks[task_id]["status"] == "completed"
    finally:
        _cloud_workflow_tasks.pop(task_id, None)
        _cloud_workflow_handles.pop(task_id, None)
