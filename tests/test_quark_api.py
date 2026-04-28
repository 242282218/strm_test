"""
夸克 API 端点单元测试

测试文件浏览、下载链接和智能重命名端点
"""

import asyncio
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

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
    """创建测试应用"""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    """创建测试客户端"""
    return TestClient(app)


@pytest.fixture
def mock_cookie():
    """模拟 Cookie"""
    return "test_cookie_value"


class TestQuarkConfigEndpoint:
    """夸克配置端点测试"""

    def test_get_quark_config(self, app, mock_cookie):
        """测试获取夸克配置"""
        mock_quark_config = SimpleNamespace(
            cookie=mock_cookie,
            referer="https://pan.quark.cn/",
            root_id="0",
            only_video=True,
        )

        with patch("app.api.quark._get_runtime_quark_config", return_value=mock_quark_config):
            client = TestClient(app)
            response = client.get("/api/quark/config")

            assert response.status_code == 200
            data = response.json()
            assert "referer" in data
            assert "cookie_configured" in data


class TestQuarkFilesEndpoint:
    """夸克文件端点测试"""

    def test_get_files_success(self, app, mock_cookie):
        """测试获取文件列表成功"""
        mock_service = AsyncMock()
        mock_service.get_files = AsyncMock(
            return_value=[
                {"fid": "file1", "file_name": "video1.mp4"},
                {"fid": "file2", "file_name": "video2.mp4"},
            ]
        )
        mock_service.close = AsyncMock()

        with patch("app.api.quark.get_quark_cookie", return_value=mock_cookie):
            with patch("app.api.quark.get_only_video_flag", return_value=True):
                with patch("app.api.quark.QuarkService", return_value=mock_service):
                    client = TestClient(app)
                    response = client.get("/api/quark/files/0")

                    assert response.status_code == 200
                    data = response.json()
                    assert "files" in data
                    assert "count" in data

    def test_get_files_with_validation_error(self, app, mock_cookie):
        """测试获取文件列表验证错误"""
        with patch("app.api.quark.get_quark_cookie", return_value=mock_cookie):
            with patch("app.api.quark.get_only_video_flag", return_value=True):
                client = TestClient(app)
                # 无效的 parent ID
                response = client.get("/api/quark/files/invalid@id")

                assert response.status_code == 400


class TestQuarkLinkEndpoint:
    """夸克链接端点测试"""

    def test_get_download_link_success(self, app, mock_cookie):
        """测试获取下载链接成功"""
        mock_link = MagicMock()
        mock_link.url = "http://download.url/video.mp4"
        mock_link.headers = {"Cookie": mock_cookie}

        mock_service = AsyncMock()
        mock_service.get_download_link = AsyncMock(return_value=mock_link)
        mock_service.close = AsyncMock()

        with patch("app.api.quark.get_quark_cookie", return_value=mock_cookie):
            with patch("app.api.quark.QuarkService", return_value=mock_service):
                client = TestClient(app)
                response = client.get("/api/quark/link/test_file_id")

                assert response.status_code == 200
                data = response.json()
                assert "url" in data
                assert "headers" in data

    def test_get_download_link_validation_error(self, app, mock_cookie):
        """测试获取下载链接验证错误"""
        with patch("app.api.quark.get_quark_cookie", return_value=mock_cookie):
            client = TestClient(app)
            response = client.get("/api/quark/link/invalid@id")

            assert response.status_code == 400


class TestQuarkBrowseEndpoint:
    """夸克浏览端点测试"""

    def test_browse_directory_success(self, app, mock_cookie):
        """测试浏览目录成功"""
        mock_service = AsyncMock()
        mock_service.list_files = AsyncMock(
            return_value={
                "list": [
                    {
                        "fid": "folder1",
                        "file_name": "Movies",
                        "file_type": 0,
                        "size": 0,
                        "created_at": 1234567890,
                        "updated_at": 1234567890,
                    }
                ],
                "metadata": {"_total": 1},
            }
        )
        mock_service.close = AsyncMock()

        with patch("app.api.quark.get_quark_cookie", return_value=mock_cookie):
            with patch("app.api.quark.QuarkService", return_value=mock_service):
                client = TestClient(app)
                response = client.get("/api/quark/browse?pdir_fid=0&page=1&size=50")

                assert response.status_code == 200
                data = response.json()
                assert data["status"] == 200
                assert "items" in data["data"]

    def test_browse_directory_video_filter(self, app, mock_cookie):
        """测试浏览目录视频过滤"""
        mock_service = AsyncMock()
        mock_service.list_files = AsyncMock(
            return_value={
                "list": [
                    {"fid": "folder1", "file_name": "Movies", "file_type": 0},
                    {"fid": "file1", "file_name": "video.mp4", "file_type": 1},
                    {"fid": "file2", "file_name": "doc.pdf", "file_type": 1},
                ],
                "metadata": {"_total": 3},
            }
        )
        mock_service.is_video_file = MagicMock(return_value=True)
        mock_service.close = AsyncMock()

        with patch("app.api.quark.get_quark_cookie", return_value=mock_cookie):
            with patch("app.api.quark.QuarkService", return_value=mock_service):
                client = TestClient(app)
                response = client.get("/api/quark/browse?file_type=video")

                assert response.status_code == 200
                # 应该只返回视频文件

    def test_browse_directory_folder_filter(self, app, mock_cookie):
        """测试浏览目录文件夹过滤"""
        mock_service = AsyncMock()
        mock_service.list_files = AsyncMock(
            return_value={
                "list": [
                    {"fid": "folder1", "file_name": "Movies", "file_type": 0},
                    {"fid": "file1", "file_name": "video.mp4", "file_type": 1},
                ],
                "metadata": {"_total": 2},
            }
        )
        mock_service.close = AsyncMock()

        with patch("app.api.quark.get_quark_cookie", return_value=mock_cookie):
            with patch("app.api.quark.QuarkService", return_value=mock_service):
                client = TestClient(app)
                response = client.get("/api/quark/browse?file_type=folder")

                assert response.status_code == 200
                # 应该只返回文件夹


class TestQuarkTestLinkEndpoint:
    """夸克测试链接端点测试"""

    def test_test_link_endpoint(self, app):
        """测试链接测试端点"""
        client = TestClient(app)
        response = client.get("/api/quark/test/link")

        assert response.status_code == 200
        data = response.json()
        assert data["test"] is True
        assert "url" in data
        assert "headers" in data


class TestQuarkSyncEndpoint:
    """夸克同步端点测试"""

    def test_sync_missing_cookie(self, app):
        """测试同步缺少 Cookie"""
        mock_quark_config = SimpleNamespace(cookie=None, root_id="0", only_video=True)

        with patch("app.api.quark._get_runtime_quark_config", return_value=mock_quark_config):
            client = TestClient(app)
            response = client.post("/api/quark/sync")

            assert response.status_code == 400

    def test_sync_validation_error(self, app, mock_cookie):
        """测试同步验证错误"""
        mock_quark_config = SimpleNamespace(cookie=mock_cookie, root_id="0", only_video=True)

        with patch("app.api.quark._get_runtime_quark_config", return_value=mock_quark_config):
            client = TestClient(app)
            # 无效路径
            response = client.post("/api/quark/sync?output_dir=")

            assert response.status_code == 422


class TestQuarkAIConnectivityEndpoint:
    """夸克 AI 连接测试端点测试"""

    def test_ai_connectivity_uses_unified_provider_names(self, app):
        """测试 AI 连接使用统一 provider 列表"""
        mock_service = AsyncMock()
        mock_service.test_providers = AsyncMock(
            return_value=[
                {"provider": "openai", "connected": True},
                {"provider": "qwen", "connected": False},
            ]
        )

        with patch("app.api.quark.get_ai_connectivity_service", return_value=mock_service):
            client = TestClient(app)
            response = client.get("/api/quark/ai-connectivity")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["providers"] == [
                {"provider": "openai", "connected": True},
                {"provider": "qwen", "connected": False},
            ]
            mock_service.test_providers.assert_awaited_once_with(timeout_seconds=30)


class TestQuarkSmartRenameEndpoint:
    """夸克智能重命名端点测试"""

    def test_smart_rename_cloud_empty(self, app, mock_cookie):
        """测试智能重命名空目录"""
        mock_quark_service = AsyncMock()
        mock_quark_service.get_all_video_files = AsyncMock(return_value=[])
        mock_quark_service.close = AsyncMock()

        mock_rename_service = MagicMock()
        mock_rename_service._parse_with_algorithm = AsyncMock(return_value=({}, "standard", 0.5))
        mock_rename_service._match_tmdb = AsyncMock(return_value=(None, 0.0))

        with patch("app.api.quark.get_quark_cookie", return_value=mock_cookie):
            with patch("app.api.quark.QuarkService", return_value=mock_quark_service):
                with patch("app.api.quark.get_smart_rename_service", return_value=mock_rename_service):
                    client = TestClient(app)
                    response = client.post(
                        "/api/quark/smart-rename-cloud",
                        json={"pdir_fid": "test_fid", "algorithm": "standard", "naming_standard": "emby"},
                    )

                    assert response.status_code == 200
                    data = response.json()
                    assert data["status"] == 200
                    assert data["data"]["total_items"] == 0


class TestQuarkWorkflowTaskEndpoint:
    """夸克工作流任务端点测试"""

    def test_create_workflow_task(self, app, mock_cookie):
        """测试创建工作流任务"""
        with patch("app.api.quark.get_quark_cookie", return_value=mock_cookie):
            client = TestClient(app)
            response = client.post(
                "/api/quark/smart-rename-cloud/workflow-tasks",
                json={
                    "pdir_fid": "test_fid",
                    "algorithm": "standard",
                    "naming_standard": "emby",
                    "auto_execute": False,
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert "task_id" in data
            assert data["status"] == "pending"

    def test_get_workflow_task_not_found(self, app):
        """测试获取不存在的工作流任务"""
        client = TestClient(app)
        response = client.get(f"/api/quark/smart-rename-cloud/workflow-tasks/{uuid.uuid4()}")

        assert response.status_code == 404

    def test_cancel_workflow_task_not_found(self, app):
        """测试取消不存在的工作流任务"""
        client = TestClient(app)
        response = client.post(f"/api/quark/smart-rename-cloud/workflow-tasks/{uuid.uuid4()}/cancel")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_run_workflow_task_calls_internal_routes_without_auth_kwarg(self, mock_cookie):
        """测试后台工作流直接复用内部路由时不会传入已删除的 _auth 参数"""
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
            with patch(
                "app.api.quark.smart_rename_cloud_files", AsyncMock(return_value=preview_response)
            ) as mock_preview, patch(
                "app.api.quark.execute_cloud_rename", AsyncMock(return_value=execute_response)
            ) as mock_execute:
                await _run_cloud_workflow_task(task_id, request, mock_cookie)

            mock_preview.assert_awaited_once_with(request=request, _cookie=mock_cookie)
            mock_execute.assert_awaited_once()
            execute_kwargs = mock_execute.await_args.kwargs
            assert execute_kwargs["_cookie"] == mock_cookie
            assert "request" in execute_kwargs
            assert "_auth" not in execute_kwargs
            assert _cloud_workflow_tasks[task_id]["status"] == "completed"
        finally:
            _cloud_workflow_tasks.pop(task_id, None)
            _cloud_workflow_handles.pop(task_id, None)


class TestQuarkExecuteRenameEndpoint:
    """夸克执行重命名端点测试"""

    def test_execute_cloud_rename(self, app, mock_cookie):
        """测试执行云盘重命名"""
        mock_service = AsyncMock()
        mock_service.rename_file = AsyncMock(return_value={"status": "success", "file_name": "new_name.mp4"})
        mock_service.close = AsyncMock()

        with patch("app.api.quark.get_quark_cookie", return_value=mock_cookie):
            with patch("app.api.quark.QuarkService", return_value=mock_service):
                client = TestClient(app)
                response = client.post(
                    "/api/quark/execute-cloud-rename",
                    json={"batch_id": str(uuid.uuid4()), "operations": [{"fid": "file1", "new_name": "new_name.mp4"}]},
                )

                assert response.status_code == 200
                data = response.json()
                assert data["status"] == 200
                assert "success" in data["data"]


class TestQuarkEndpointErrorHandling:
    """夸克端点错误处理测试"""

    def test_files_endpoint_error(self, app, mock_cookie):
        """测试文件端点错误"""
        mock_service = AsyncMock()
        mock_service.get_files = AsyncMock(side_effect=Exception("API Error"))
        mock_service.close = AsyncMock()

        with patch("app.api.quark.get_quark_cookie", return_value=mock_cookie):
            with patch("app.api.quark.get_only_video_flag", return_value=True):
                with patch("app.api.quark.QuarkService", return_value=mock_service):
                    client = TestClient(app)
                    response = client.get("/api/quark/files/0")

                    assert response.status_code == 500

    def test_link_endpoint_error(self, app, mock_cookie):
        """测试链接端点错误"""
        mock_service = AsyncMock()
        mock_service.get_download_link = AsyncMock(side_effect=Exception("API Error"))
        mock_service.close = AsyncMock()

        with patch("app.api.quark.get_quark_cookie", return_value=mock_cookie):
            with patch("app.api.quark.QuarkService", return_value=mock_service):
                client = TestClient(app)
                response = client.get("/api/quark/link/test_file_id")

                assert response.status_code == 500
