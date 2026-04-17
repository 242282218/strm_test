"""
稳定媒体入口路由测试
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.stable_stream import router
from app.core.url_validator import URLValidationError


def test_stable_stream_route_when_mapping_exists_then_redirects_to_resolved_target():
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    mapping = SimpleNamespace(
        media_id="media123",
        provider_file_id="file123",
        source_path="/Movies/Avatar (2009).mkv",
    )

    class _FakeMediaMappingService:
        def get_by_media_id(self, media_id: str):
            assert media_id == "media123"
            return mapping

        def update_provider_file_id(self, media_id: str, provider_file_id: str):
            return SimpleNamespace(media_id=media_id, provider_file_id=provider_file_id)

    class _FakeQuarkService:
        def __init__(self, cookie: str):
            self.cookie = cookie

        async def close(self):
            return None

    with (
        patch("app.api.stable_stream.config.get_quark_cookie", return_value="test-cookie"),
        patch("app.api.stable_stream.MediaMappingService", return_value=_FakeMediaMappingService()),
        patch("app.api.stable_stream.QuarkService", _FakeQuarkService),
        patch("app.api.stable_stream.LinkResolver"),
        patch("app.api.stable_stream.WebDAVFallback"),
        patch(
            "app.api.stable_stream._resolve_redirect_target",
            new=AsyncMock(return_value=("https://download.example/file123.mp4", None)),
        ),
    ):
        response = client.get("/strm/v1/m/media123/Avatar%20(2009).mkv", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == "https://download.example/file123.mp4"


def test_stable_stream_route_when_direct_first_disabled_then_redirects_to_local_proxy_stream():
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    mapping = SimpleNamespace(
        media_id="media123",
        provider_file_id="file123",
        source_path="/Movies/Avatar (2009).mkv",
    )

    class _FakeMediaMappingService:
        def get_by_media_id(self, media_id: str):
            assert media_id == "media123"
            return mapping

        def update_provider_file_id(self, media_id: str, provider_file_id: str):
            return SimpleNamespace(media_id=media_id, provider_file_id=provider_file_id)

    class _FakeQuarkService:
        def __init__(self, cookie: str):
            self.cookie = cookie

        async def close(self):
            return None

    mock_config = SimpleNamespace(playback=SimpleNamespace(direct_first=False, force_proxy_clients=[], force_proxy_hosts=[]))

    with (
        patch("app.api.stable_stream.config.get_quark_cookie", return_value="test-cookie"),
        patch("app.api.stable_stream.MediaMappingService", return_value=_FakeMediaMappingService()),
        patch("app.api.stable_stream.QuarkService", _FakeQuarkService),
        patch("app.api.stable_stream.LinkResolver"),
        patch("app.api.stable_stream.WebDAVFallback"),
        patch("app.services.playback_decision_service.get_config_service") as mock_get_config_service,
        patch(
            "app.api.stable_stream._resolve_redirect_target",
            new=AsyncMock(return_value=("https://download.example/file123.mp4", None)),
        ),
    ):
        mock_get_config_service.return_value.get_config.return_value = mock_config
        response = client.get("/strm/v1/m/media123/Avatar%20(2009).mkv", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == "/api/proxy/stream/file123?source=download"


def test_stable_stream_route_when_resolved_redirect_url_invalid_then_falls_back_to_local_proxy_stream():
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    mapping = SimpleNamespace(
        media_id="media123",
        provider_file_id="file123",
        source_path="/Movies/Avatar (2009).mkv",
    )

    class _FakeMediaMappingService:
        def get_by_media_id(self, media_id: str):
            assert media_id == "media123"
            return mapping

        def update_provider_file_id(self, media_id: str, provider_file_id: str):
            return SimpleNamespace(media_id=media_id, provider_file_id=provider_file_id)

    class _FakeQuarkService:
        def __init__(self, cookie: str):
            self.cookie = cookie

        async def close(self):
            return None

    with (
        patch("app.api.stable_stream.config.get_quark_cookie", return_value="test-cookie"),
        patch("app.api.stable_stream.MediaMappingService", return_value=_FakeMediaMappingService()),
        patch("app.api.stable_stream.QuarkService", _FakeQuarkService),
        patch("app.api.stable_stream.LinkResolver"),
        patch("app.api.stable_stream.WebDAVFallback"),
        patch("app.api.proxy._is_internal_redirect_enabled", return_value=True),
        patch(
            "app.api.stable_stream._resolve_redirect_target",
            new=AsyncMock(return_value=("https://127.0.0.1/file123.mp4", None)),
        ),
        patch(
            "app.api.stable_stream.general_validator.validate",
            side_effect=URLValidationError("Private IP address '127.0.0.1' is not allowed"),
        ),
    ):
        response = client.get("/strm/v1/m/media123/Avatar%20(2009).mkv", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == "/api/proxy/stream/file123?source=download"
