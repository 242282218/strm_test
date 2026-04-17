from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.proxy import router as proxy_router
from app.core.dependencies import require_api_key


def _build_proxy_client() -> TestClient:
    app = FastAPI()
    app.include_router(proxy_router)
    app.dependency_overrides[require_api_key] = lambda: None
    return TestClient(app)


def test_stream_route_when_transcoding_source_fails_then_falls_back_to_download_link():
    client = _build_proxy_client()

    class _FakeUpstreamResponse:
        status = 200
        headers = {
            "Content-Type": "video/mp4",
            "Content-Length": "16",
            "Accept-Ranges": "bytes",
        }

        class _Content:
            @staticmethod
            async def iter_chunked(_size):
                yield b"fallback-download"

        content = _Content()

        def close(self):
            return None

    class _FakeAiohttpSession:
        last_url = None

        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

        async def get(self, url, headers=None, allow_redirects=True):
            _ = headers, allow_redirects
            _FakeAiohttpSession.last_url = url
            return _FakeUpstreamResponse()

        async def close(self):
            return None

    class _FakeFallbackQuarkService:
        last_instance = None

        def __init__(self, cookie: str):
            self.cookie = cookie
            self.download_calls = 0
            self.transcoding_calls = 0
            _FakeFallbackQuarkService.last_instance = self

        async def get_download_link(self, file_id: str):
            self.download_calls += 1
            return SimpleNamespace(url=f"https://download.example/{file_id}.mp4", headers={})

        async def get_transcoding_link(self, file_id: str):
            self.transcoding_calls += 1
            raise RuntimeError("transcoding unavailable")

        async def close(self):
            return None

    with (
        patch("app.api.proxy.config.get_quark_cookie", return_value="test-cookie"),
        patch("app.api.proxy.QuarkService", _FakeFallbackQuarkService),
        patch("app.services.quark_service.QuarkService", _FakeFallbackQuarkService),
        patch("app.api.proxy.aiohttp.ClientSession", _FakeAiohttpSession),
    ):
        response = client.get("/api/proxy/stream/file123", params={"source": "transcoding"})

    assert response.status_code == 200
    assert _FakeFallbackQuarkService.last_instance is not None
    assert _FakeFallbackQuarkService.last_instance.transcoding_calls == 1
    assert _FakeFallbackQuarkService.last_instance.download_calls == 1
    assert _FakeAiohttpSession.last_url == "https://download.example/file123.mp4"


def test_stream_route_when_download_and_transcoding_are_both_unavailable_then_returns_gateway_error():
    client = _build_proxy_client()

    class _BrokenQuarkService:
        def __init__(self, cookie: str):
            self.cookie = cookie

        async def get_download_link(self, file_id: str):
            _ = file_id
            return SimpleNamespace(url="", headers={})

        async def get_transcoding_link(self, file_id: str):
            _ = file_id
            raise RuntimeError("upstream missing")

        async def close(self):
            return None

    with (
        patch("app.api.proxy.config.get_quark_cookie", return_value="test-cookie"),
        patch("app.api.proxy.QuarkService", _BrokenQuarkService),
        patch("app.services.quark_service.QuarkService", _BrokenQuarkService),
    ):
        response = client.get("/api/proxy/stream/file123")

    assert response.status_code == 502
    assert response.json() == {"detail": "Failed to resolve stream URL"}
