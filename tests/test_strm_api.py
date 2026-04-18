"""
STRM API 端点单元测试

测试目录扫描和 STRM 生成端点
"""

import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.strm import router


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


class TestStrmScanEndpoint:
    """STRM 扫描端点测试"""

    def test_scan_directory_success(self, app, mock_cookie):
        """测试扫描目录成功"""
        mock_service = AsyncMock()
        mock_service.scan_directory = AsyncMock(return_value={
            "strms": ["movie1.strm", "movie2.strm"],
            "generated_count": 2,
            "skipped_count": 0,
            "failed_count": 0,
            "total_files": 2,
        })
        mock_service.close = AsyncMock()

        mock_database = MagicMock()
        mock_database.close = MagicMock()

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("app.api.strm.get_quark_cookie", return_value=mock_cookie):
                with patch("app.api.strm.StrmService", return_value=mock_service):
                    with patch("app.api.strm.Database", return_value=mock_database):
                        with patch("app.api.strm.resolve_db_path", return_value="test.db"):
                            client = TestClient(app)
                            response = client.post(
                                "/api/strm/scan",
                                params={
                                    "remote_path": "/videos",
                                    "local_path": tmpdir,
                                    "recursive": True,
                                    "concurrent_limit": 5,
                                    "base_url": "http://localhost:8000",
                                    "strm_url_mode": "redirect",
                                    "overwrite": False,
                                }
                            )

                            assert response.status_code == 200
                            data = response.json()
                            assert "strms" in data
                            assert data["count"] == 2

    def test_scan_directory_with_overwrite(self, app, mock_cookie):
        """测试扫描目录并覆盖"""
        mock_service = AsyncMock()
        mock_service.scan_directory = AsyncMock(return_value={
            "strms": ["movie.strm"],
            "generated_count": 1,
            "skipped_count": 0,
            "failed_count": 0,
            "total_files": 1,
        })
        mock_service.close = AsyncMock()

        mock_database = MagicMock()
        mock_database.close = MagicMock()

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("app.api.strm.get_quark_cookie", return_value=mock_cookie):
                with patch("app.api.strm.StrmService", return_value=mock_service):
                    with patch("app.api.strm.Database", return_value=mock_database):
                        with patch("app.api.strm.resolve_db_path", return_value="test.db"):
                            client = TestClient(app)
                            response = client.post(
                                "/api/strm/scan",
                                params={
                                    "remote_path": "/videos",
                                    "local_path": tmpdir,
                                    "recursive": True,
                                    "concurrent_limit": 5,
                                    "base_url": "http://localhost:8000",
                                    "strm_url_mode": "redirect",
                                    "overwrite": True,
                                }
                            )

                            assert response.status_code == 200

    def test_scan_directory_non_recursive(self, app, mock_cookie):
        """测试非递归扫描目录"""
        mock_service = AsyncMock()
        mock_service.scan_directory = AsyncMock(return_value={
            "strms": [],
            "generated_count": 0,
            "skipped_count": 0,
            "failed_count": 0,
            "total_files": 0,
        })
        mock_service.close = AsyncMock()

        mock_database = MagicMock()
        mock_database.close = MagicMock()

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("app.api.strm.get_quark_cookie", return_value=mock_cookie):
                with patch("app.api.strm.StrmService", return_value=mock_service):
                    with patch("app.api.strm.Database", return_value=mock_database):
                        with patch("app.api.strm.resolve_db_path", return_value="test.db"):
                            client = TestClient(app)
                            response = client.post(
                                "/api/strm/scan",
                                params={
                                    "remote_path": "/videos",
                                    "local_path": tmpdir,
                                    "recursive": False,
                                    "concurrent_limit": 5,
                                }
                            )

                            assert response.status_code == 200

    def test_scan_directory_different_modes(self, app, mock_cookie):
        """测试不同 URL 模式扫描"""
        modes = ["redirect", "stream", "direct", "webdav"]

        for mode in modes:
            mock_service = AsyncMock()
            mock_service.scan_directory = AsyncMock(return_value={
                "strms": [],
                "generated_count": 0,
                "skipped_count": 0,
                "failed_count": 0,
                "total_files": 0,
            })
            mock_service.close = AsyncMock()

            mock_database = MagicMock()
            mock_database.close = MagicMock()

            with tempfile.TemporaryDirectory() as tmpdir:
                with patch("app.api.strm.get_quark_cookie", return_value=mock_cookie):
                    with patch("app.api.strm.StrmService", return_value=mock_service):
                        with patch("app.api.strm.Database", return_value=mock_database):
                            with patch("app.api.strm.resolve_db_path", return_value="test.db"):
                                client = TestClient(app)
                                response = client.post(
                                    "/api/strm/scan",
                                    params={
                                        "remote_path": "/videos",
                                        "local_path": tmpdir,
                                        "strm_url_mode": mode,
                                    }
                                )

                                assert response.status_code == 200, f"Mode {mode} failed"


class TestStrmScanValidation:
    """STRM 扫描验证测试"""

    def test_scan_missing_remote_path(self, app, mock_cookie):
        """测试缺少远程路径"""
        with patch("app.api.strm.get_quark_cookie", return_value=mock_cookie):
            client = TestClient(app)
            response = client.post(
                "/api/strm/scan",
                params={
                    "local_path": "/tmp",
                }
            )

            assert response.status_code == 422

    def test_scan_missing_local_path(self, app, mock_cookie):
        """测试缺少本地路径"""
        with patch("app.api.strm.get_quark_cookie", return_value=mock_cookie):
            client = TestClient(app)
            response = client.post(
                "/api/strm/scan",
                params={
                    "remote_path": "/videos",
                }
            )

            assert response.status_code == 422

    def test_scan_invalid_concurrent_limit(self, app, mock_cookie):
        """测试无效并发限制"""
        mock_service = AsyncMock()
        mock_service.close = AsyncMock()

        mock_database = MagicMock()
        mock_database.close = MagicMock()

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("app.api.strm.get_quark_cookie", return_value=mock_cookie):
                with patch("app.api.strm.StrmService", return_value=mock_service):
                    with patch("app.api.strm.Database", return_value=mock_database):
                        with patch("app.api.strm.resolve_db_path", return_value="test.db"):
                            client = TestClient(app)
                            # 并发限制超出范围
                            response = client.post(
                                "/api/strm/scan",
                                params={
                                    "remote_path": "/videos",
                                    "local_path": tmpdir,
                                    "concurrent_limit": 100,  # 超出最大值
                                }
                            )

                            # 应该返回验证错误
                            assert response.status_code == 422

    def test_scan_empty_paths(self, app, mock_cookie):
        """测试空路径"""
        with patch("app.api.strm.get_quark_cookie", return_value=mock_cookie):
            client = TestClient(app)
            response = client.post(
                "/api/strm/scan",
                params={
                    "remote_path": "",
                    "local_path": "",
                }
            )

            assert response.status_code == 422


class TestStrmScanErrorHandling:
    """STRM 扫描错误处理测试"""

    def test_scan_service_error(self, app, mock_cookie):
        """测试服务错误"""
        mock_service = AsyncMock()
        mock_service.scan_directory = AsyncMock(
            side_effect=Exception("Service error")
        )
        mock_service.close = AsyncMock()

        mock_database = MagicMock()
        mock_database.close = MagicMock()

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("app.api.strm.get_quark_cookie", return_value=mock_cookie):
                with patch("app.api.strm.StrmService", return_value=mock_service):
                    with patch("app.api.strm.Database", return_value=mock_database):
                        with patch("app.api.strm.resolve_db_path", return_value="test.db"):
                            client = TestClient(app)
                            response = client.post(
                                "/api/strm/scan",
                                params={
                                    "remote_path": "/videos",
                                    "local_path": tmpdir,
                                }
                            )

                            assert response.status_code == 500

    def test_scan_path_not_found(self, app, mock_cookie):
        """测试路径不存在"""
        mock_service = AsyncMock()
        mock_service.scan_directory = AsyncMock(
            side_effect=ValueError("Remote path not found")
        )
        mock_service.close = AsyncMock()

        mock_database = MagicMock()
        mock_database.close = MagicMock()

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("app.api.strm.get_quark_cookie", return_value=mock_cookie):
                with patch("app.api.strm.StrmService", return_value=mock_service):
                    with patch("app.api.strm.Database", return_value=mock_database):
                        with patch("app.api.strm.resolve_db_path", return_value="test.db"):
                            client = TestClient(app)
                            response = client.post(
                                "/api/strm/scan",
                                params={
                                    "remote_path": "/nonexistent",
                                    "local_path": tmpdir,
                                }
                            )

                            assert response.status_code == 500


class TestStrmScanConcurrency:
    """STRM 扫描并发测试"""

    def test_scan_with_different_concurrent_limits(self, app, mock_cookie):
        """测试不同并发限制"""
        for limit in [1, 5, 10]:
            mock_service = AsyncMock()
            mock_service.scan_directory = AsyncMock(return_value={
                "strms": [],
                "generated_count": 0,
                "skipped_count": 0,
                "failed_count": 0,
                "total_files": 0,
            })
            mock_service.close = AsyncMock()

            mock_database = MagicMock()
            mock_database.close = MagicMock()

            with tempfile.TemporaryDirectory() as tmpdir:
                with patch("app.api.strm.get_quark_cookie", return_value=mock_cookie):
                    with patch("app.api.strm.StrmService", return_value=mock_service):
                        with patch("app.api.strm.Database", return_value=mock_database):
                            with patch("app.api.strm.resolve_db_path", return_value="test.db"):
                                client = TestClient(app)
                                response = client.post(
                                    "/api/strm/scan",
                                    params={
                                        "remote_path": "/videos",
                                        "local_path": tmpdir,
                                        "concurrent_limit": limit,
                                    }
                                )

                                assert response.status_code == 200


class TestStrmScanBaseUrl:
    """STRM 扫描 Base URL 测试"""

    def test_scan_with_custom_base_url(self, app, mock_cookie):
        """测试自定义 Base URL"""
        mock_service = AsyncMock()
        mock_service.scan_directory = AsyncMock(return_value={
            "strms": [],
            "generated_count": 0,
            "skipped_count": 0,
            "failed_count": 0,
            "total_files": 0,
        })
        mock_service.close = AsyncMock()

        mock_database = MagicMock()
        mock_database.close = MagicMock()

        custom_url = "http://custom.server:9000"

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("app.api.strm.get_quark_cookie", return_value=mock_cookie):
                with patch("app.api.strm.StrmService", return_value=mock_service) as mock_strm_service:
                    with patch("app.api.strm.Database", return_value=mock_database):
                        with patch("app.api.strm.resolve_db_path", return_value="test.db"):
                            client = TestClient(app)
                            response = client.post(
                                "/api/strm/scan",
                                params={
                                    "remote_path": "/videos",
                                    "local_path": tmpdir,
                                    "base_url": custom_url,
                                }
                            )

                            assert response.status_code == 200
                            mock_strm_service.assert_called_once()
                            assert mock_strm_service.call_args.kwargs["base_url"] == custom_url

    def test_scan_with_proxy_override_header(self, app, mock_cookie):
        """测试请求头覆盖默认 Base URL"""
        mock_service = AsyncMock()
        mock_service.scan_directory = AsyncMock(return_value={
            "strms": [],
            "generated_count": 0,
            "skipped_count": 0,
            "failed_count": 0,
            "total_files": 0,
        })
        mock_service.close = AsyncMock()

        mock_database = MagicMock()
        mock_database.close = MagicMock()

        mock_config = MagicMock()
        mock_emby = MagicMock()
        mock_emby.proxy_base_url = "http://configured.proxy:18097"
        mock_config.emby = mock_emby

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("app.api.strm.get_quark_cookie", return_value=mock_cookie):
                with patch("app.api.strm.StrmService", return_value=mock_service) as mock_strm_service:
                    with patch("app.api.strm.Database", return_value=mock_database):
                        with patch("app.api.strm.resolve_db_path", return_value="test.db"):
                            with patch("app.api.strm.get_config_service") as mock_get_config_service:
                                mock_get_config_service.return_value.get_config.return_value = mock_config
                                client = TestClient(app)
                                response = client.post(
                                    "/api/strm/scan",
                                    params={
                                        "remote_path": "/videos",
                                        "local_path": tmpdir,
                                    },
                                    headers={
                                        "X-Proxy-Server-Url": "https://public.proxy.example",
                                    },
                                )

                                assert response.status_code == 200
                                mock_strm_service.assert_called_once()
                                assert mock_strm_service.call_args.kwargs["base_url"] == "https://public.proxy.example"

    def test_scan_with_invalid_proxy_override_header_then_returns_400(self, app, mock_cookie):
        """测试非法请求头代理覆盖地址返回固定 400"""
        mock_config = MagicMock()
        mock_emby = MagicMock()
        mock_emby.proxy_base_url = "http://configured.proxy:18097"
        mock_config.emby = mock_emby

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("app.api.strm.get_quark_cookie", return_value=mock_cookie):
                with patch(
                    "app.api.strm.StrmService",
                    side_effect=AssertionError("should reject invalid proxy override before service init"),
                ):
                    with patch("app.api.strm.Database", side_effect=AssertionError("should not open database on invalid input")):
                        with patch("app.api.strm.resolve_db_path", return_value="test.db"):
                            with patch("app.api.strm.get_config_service") as mock_get_config_service:
                                mock_get_config_service.return_value.get_config.return_value = mock_config
                                client = TestClient(app, raise_server_exceptions=False)
                                response = client.post(
                                    "/api/strm/scan",
                                    params={
                                        "remote_path": "/videos",
                                        "local_path": tmpdir,
                                    },
                                    headers={
                                        "X-Proxy-Server-Url": "not-a-url",
                                    },
                                )

                                assert response.status_code == 400
                                assert response.json() == {"detail": "Invalid proxy server URL"}

    def test_scan_with_default_base_url(self, app, mock_cookie):
        """测试默认 Base URL"""
        mock_service = AsyncMock()
        mock_service.scan_directory = AsyncMock(return_value={
            "strms": [],
            "generated_count": 0,
            "skipped_count": 0,
            "failed_count": 0,
            "total_files": 0,
        })
        mock_service.close = AsyncMock()

        mock_database = MagicMock()
        mock_database.close = MagicMock()

        mock_config = MagicMock()
        mock_emby = MagicMock()
        mock_emby.proxy_base_url = "http://192.168.100.101:18097"
        mock_config.emby = mock_emby

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("app.api.strm.get_quark_cookie", return_value=mock_cookie):
                with patch("app.api.strm.StrmService", return_value=mock_service) as mock_strm_service:
                    with patch("app.api.strm.Database", return_value=mock_database):
                        with patch("app.api.strm.resolve_db_path", return_value="test.db"):
                            with patch("app.api.strm.get_config_service") as mock_get_config_service:
                                mock_get_config_service.return_value.get_config.return_value = mock_config
                                client = TestClient(app)
                                response = client.post(
                                    "/api/strm/scan",
                                    params={
                                        "remote_path": "/videos",
                                        "local_path": tmpdir,
                                    }
                                )

                                assert response.status_code == 200
                                mock_strm_service.assert_called_once()
                                assert mock_strm_service.call_args.kwargs["base_url"] == "http://192.168.100.101:18097"


class TestStrmScanResponse:
    """STRM 扫描响应测试"""

    def test_scan_response_structure(self, app, mock_cookie):
        """测试响应结构"""
        mock_service = AsyncMock()
        mock_service.scan_directory = AsyncMock(return_value={
            "strms": ["movie1.strm", "movie2.strm", "movie3.strm"],
            "generated_count": 3,
            "skipped_count": 2,
            "failed_count": 1,
            "total_files": 6,
        })
        mock_service.close = AsyncMock()

        mock_database = MagicMock()
        mock_database.close = MagicMock()

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("app.api.strm.get_quark_cookie", return_value=mock_cookie):
                with patch("app.api.strm.StrmService", return_value=mock_service):
                    with patch("app.api.strm.Database", return_value=mock_database):
                        with patch("app.api.strm.resolve_db_path", return_value="test.db"):
                            client = TestClient(app)
                            response = client.post(
                                "/api/strm/scan",
                                params={
                                    "remote_path": "/videos",
                                    "local_path": tmpdir,
                                }
                            )

                            assert response.status_code == 200
                            data = response.json()

                            # 验证响应字段
                            assert "strms" in data
                            assert "count" in data
                            assert "skipped" in data
                            assert "failed" in data
                            assert "total" in data

                            # 验证值
                            assert len(data["strms"]) == 3
                            assert data["count"] == 3
                            assert data["skipped"] == 2
                            assert data["failed"] == 1
                            assert data["total"] == 6

    def test_scan_empty_result(self, app, mock_cookie):
        """测试空结果"""
        mock_service = AsyncMock()
        mock_service.scan_directory = AsyncMock(return_value={
            "strms": [],
            "generated_count": 0,
            "skipped_count": 0,
            "failed_count": 0,
            "total_files": 0,
        })
        mock_service.close = AsyncMock()

        mock_database = MagicMock()
        mock_database.close = MagicMock()

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("app.api.strm.get_quark_cookie", return_value=mock_cookie):
                with patch("app.api.strm.StrmService", return_value=mock_service):
                    with patch("app.api.strm.Database", return_value=mock_database):
                        with patch("app.api.strm.resolve_db_path", return_value="test.db"):
                            client = TestClient(app)
                            response = client.post(
                                "/api/strm/scan",
                                params={
                                    "remote_path": "/empty",
                                    "local_path": tmpdir,
                                }
                            )

                            assert response.status_code == 200
                            data = response.json()
                            assert data["count"] == 0
                            assert data["strms"] == []
