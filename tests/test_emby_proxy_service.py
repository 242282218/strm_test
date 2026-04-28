from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.services.emby_proxy_service import EmbyProxyService


class TestEmbyProxyService:
    @pytest.mark.asyncio
    async def test_get_stream_url_with_fallback_when_direct_link_invalid_then_returns_proxy_url(self):
        service = EmbyProxyService(
            emby_base_url="http://emby.local", api_key="api-key", cookie="cookie", proxy_base_url="http://proxy.local/"
        )
        service.quark_service = AsyncMock()
        service.quark_service.get_download_link.return_value = SimpleNamespace(url="https://download.example/video.mp4")

        with patch.object(service, "_check_url_alive", new=AsyncMock(return_value=False)):
            result = await service._get_stream_url_with_fallback("file123")

        assert result == "http://proxy.local/api/proxy/stream/file123"

    @pytest.mark.asyncio
    async def test_check_url_alive_when_reused_session_then_does_not_create_new_session(self):
        created_sessions = []

        class _FakeResponse:
            def __init__(self, status: int):
                self.status = status

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return None

        class _FakeSession:
            closed = False

            def __init__(self, *args, **kwargs):
                created_sessions.append((args, kwargs))

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return None

            def head(self, *args, **kwargs):
                return _FakeResponse(200)

            async def close(self):
                self.closed = True

        service = EmbyProxyService(
            emby_base_url="http://emby.local", api_key="api-key", cookie="cookie", proxy_base_url="http://proxy.local"
        )
        service._url_check_session = _FakeSession()

        with patch("app.services.emby_proxy_service.aiohttp.ClientSession", _FakeSession):
            first = await service._check_url_alive("https://download.example/1.mp4")
            second = await service._check_url_alive("https://download.example/2.mp4")

        assert first is True
        assert second is True
        assert len(created_sessions) == 1
