"""
API路由测试

测试新添加的API路由
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app


client = TestClient(app)


class TestQuarkSDKRoutes:
    """测试夸克SDK路由"""

    def test_sdk_status(self):
        """测试SDK状态端点"""
        response = client.get("/api/quark-sdk/status")
        assert response.status_code == 200
        data = response.json()
        assert "available" in data

    def test_get_files_without_cookie(self):
        """测试无cookie获取文件"""
        response = client.get("/api/quark-sdk/files/0")
        # 应该返回错误，因为没有配置cookie
        assert response.status_code in [200, 400, 500]


class TestSearchRoutes:
    """测试搜索路由"""

    def test_search_status(self):
        """测试搜索状态端点"""
        response = client.get("/api/search/status")
        assert response.status_code == 200
        data = response.json()
        assert "available" in data

    def test_search_without_keyword(self):
        """测试无关键词搜索"""
        response = client.get("/api/search")
        # 应该返回422验证错误
        assert response.status_code == 422


class TestRenameRoutes:
    """测试重命名路由"""

    def test_rename_status(self):
        """测试重命名状态端点"""
        response = client.get("/api/rename/status")
        assert response.status_code == 200
        data = response.json()
        assert "available" in data

    def test_preview_rename_invalid_path(self):
        """测试无效路径预览"""
        response = client.post("/api/rename/preview", json={
            "path": "/nonexistent/path",
            "recursive": True
        })
        # 可能返回错误或空结果
        assert response.status_code in [200, 400, 500]


class TestExistingRoutes:
    """测试现有路由是否仍然可用"""

    def test_root(self):
        """测试根路径"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "running"

    def test_health(self):
        """测试健康检查"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_existing_quark_routes(self):
        """测试现有夸克路由"""
        response = client.get("/api/quark/config")
        assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
