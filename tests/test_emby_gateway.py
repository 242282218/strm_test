from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest
from fastapi import FastAPI, HTTPException, WebSocketDisconnect
from fastapi.responses import Response
from fastapi.testclient import TestClient
from starlette.requests import Request

import app.api.emby_gateway as emby_gateway_module
from app.api.emby_gateway import router as emby_gateway_router
# root handler is defined in app.main, import emby_gateway for proxy checks
from app.api import emby_gateway as emby_gateway_main


class _FakeEmbyProxyService:
    last_init: dict[str, str] | None = None
    last_proxy_playback_info_call: dict[str, object] | None = None

    def __init__(self, emby_base_url: str, api_key: str, cookie: str, proxy_base_url: str):
        _FakeEmbyProxyService.last_init = {
            "emby_base_url": emby_base_url,
            "api_key": api_key,
            "cookie": cookie,
            "proxy_base_url": proxy_base_url,
        }
        self.proxy_base_url = proxy_base_url

    async def __aenter__(self):
        self.playback_hook = self
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return None

    async def hook_playback_info(
        self,
        item_id: str,
        user_id: str,
        media_source_id: str | None = None,
        is_web_client: bool = False,
        client_name: str | None = None,
        device_name: str | None = None,
        playback_request: dict[str, object] | None = None,
    ):
        _FakeEmbyProxyService.last_proxy_playback_info_call = {
            "item_id": item_id,
            "user_id": user_id,
            "media_source_id": media_source_id,
            "is_web_client": is_web_client,
            "client_name": client_name,
            "device_name": device_name,
            "playback_request": playback_request,
        }
        return {
            "item_id": item_id,
            "user_id": user_id,
            "media_source_id": media_source_id,
            "proxy_base_url": self.proxy_base_url,
            "is_web_client": is_web_client,
            "client_name": client_name,
            "device_name": device_name,
            "playback_request": playback_request,
        }


def _build_client() -> TestClient:
    app = FastAPI()
    app.include_router(emby_gateway_router)
    return TestClient(app)


def _mock_config(proxy_base_url: str = "http://proxy.example:18097"):
    return SimpleNamespace(
        endpoints=[],
        emby=SimpleNamespace(
            enabled=True,
            url="http://emby.example:18096",
            proxy_base_url=proxy_base_url,
            api_key="emby-key",
        ),
    )


class _FakeWebSocketClient:
    def __init__(self, host: str, query: str = "", headers: dict[str, str] | None = None):
        hostname, _, raw_port = host.partition(":")
        self.headers = {
            "host": host,
            "user-agent": "pytest",
            **(headers or {}),
        }
        self.url = SimpleNamespace(
            scheme="ws",
            hostname=hostname,
            port=int(raw_port) if raw_port else 80,
            query=query,
        )
        self.accepted = 0
        self.closed_codes: list[int | None] = []
        self.sent_text_messages: list[str] = []
        self.sent_bytes_messages: list[bytes] = []

    async def accept(self) -> None:
        self.accepted += 1

    async def close(self, code: int | None = None) -> None:
        self.closed_codes.append(code)

    @staticmethod
    async def receive_text() -> str:
        raise WebSocketDisconnect(code=1000)

    async def send_text(self, message: str) -> None:
        self.sent_text_messages.append(message)

    async def send_bytes(self, message: bytes) -> None:
        self.sent_bytes_messages.append(message)


class _FakeUpstreamWebSocket:
    def __init__(self) -> None:
        self.closed = False
        self.sent_messages: list[str] = []

    async def send(self, message: str) -> None:
        self.sent_messages.append(message)

    def __aiter__(self):
        return self

    async def __anext__(self) -> str:
        raise StopAsyncIteration

    async def close(self) -> None:
        self.closed = True


def test_gateway_root_when_dedicated_proxy_host_then_forwards_to_emby():
    client = _build_client()
    app_config = _mock_config()

    with (
        patch("app.api.emby_gateway.config_service.get_config", return_value=app_config),
        patch(
            "app.api.emby_gateway._forward_to_emby",
            return_value=Response(content="emby-home", media_type="text/html"),
        ),
    ):
        response = client.get("/", headers={"host": "proxy.example:18097"})

    assert response.status_code == 200
    assert "emby-home" in response.text


def test_gateway_when_non_dedicated_host_then_returns_404():
    client = _build_client()
    app_config = _mock_config()

    with patch("app.api.emby_gateway.config_service.get_config", return_value=app_config):
        response = client.get("/", headers={"host": "localhost:8000"})

    assert response.status_code == 404


def test_gateway_when_proxy_base_url_empty_and_port_18097_then_enables_gateway():
    client = _build_client()
    app_config = _mock_config(proxy_base_url="")

    with (
        patch("app.api.emby_gateway.config_service.get_config", return_value=app_config),
        patch(
            "app.api.emby_gateway._forward_to_emby",
            return_value=Response(content="emby-home", media_type="text/html"),
        ),
    ):
        response = client.get("/", headers={"host": "127.0.0.1:18097"})

    assert response.status_code == 200
    assert "emby-home" in response.text


def test_gateway_playbackinfo_when_dedicated_proxy_host_then_uses_hook_proxy():
    client = _build_client()
    app_config = _mock_config()

    with (
        patch("app.api.emby_gateway.config_service.get_config", return_value=app_config),
        patch("app.api.emby_gateway.config.get_quark_cookie", return_value="quark-cookie"),
        patch("app.api.emby_gateway.EmbyProxyService", _FakeEmbyProxyService),
    ):
        response = client.get(
            "/Items/item123/PlaybackInfo",
            params={
                "UserId": "user123",
                "MediaSourceId": "media123",
                "api_key": "emby-api-key",
            },
            headers={"host": "proxy.example:18097"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["item_id"] == "item123"
    assert data["user_id"] == "user123"
    assert data["media_source_id"] == "media123"
    assert data["proxy_base_url"] == "http://proxy.example:18097"
    assert _FakeEmbyProxyService.last_init is not None
    assert _FakeEmbyProxyService.last_init["emby_base_url"] == "http://emby.example:18096"


def test_gateway_playbackinfo_when_header_and_query_api_keys_conflict_then_prefers_header_token():
    client = _build_client()
    app_config = _mock_config()

    with (
        patch("app.api.emby_gateway.config_service.get_config", return_value=app_config),
        patch("app.api.emby_gateway.config.get_quark_cookie", return_value="quark-cookie"),
        patch("app.api.emby_gateway.EmbyProxyService", _FakeEmbyProxyService),
    ):
        response = client.get(
            "/Items/item123/PlaybackInfo",
            params={
                "UserId": "user123",
                "MediaSourceId": "media123",
                "api_key": "query-emby-api-key",
            },
            headers={"host": "proxy.example:18097", "X-Emby-Token": "header-emby-api-key"},
        )

    assert response.status_code == 200
    assert _FakeEmbyProxyService.last_init is not None
    assert _FakeEmbyProxyService.last_init["api_key"] == "header-emby-api-key"


def test_gateway_playbackinfo_when_prefixed_lowercase_path_used_then_still_uses_hook_proxy():
    client = _build_client()
    app_config = _mock_config()

    with (
        patch("app.api.emby_gateway.config_service.get_config", return_value=app_config),
        patch("app.api.emby_gateway.config.get_quark_cookie", return_value="quark-cookie"),
        patch("app.api.emby_gateway.EmbyProxyService", _FakeEmbyProxyService),
        patch(
            "app.api.emby_gateway._forward_to_emby",
            new=AsyncMock(side_effect=AssertionError("should not forward prefixed lowercase PlaybackInfo upstream")),
        ),
    ):
        response = client.get(
            "/emby/items/item123/PlaybackInfo",
            params={
                "UserId": "user123",
                "MediaSourceId": "media123",
                "api_key": "emby-api-key",
            },
            headers={"host": "proxy.example:18097"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["item_id"] == "item123"
    assert data["user_id"] == "user123"
    assert data["media_source_id"] == "media123"
    assert _FakeEmbyProxyService.last_init is not None
    assert _FakeEmbyProxyService.last_init["emby_base_url"] == "http://emby.example:18096"


def test_gateway_playbackinfo_when_web_headers_present_then_forwards_web_client_hints():
    client = _build_client()
    app_config = _mock_config()

    with (
        patch("app.api.emby_gateway.config_service.get_config", return_value=app_config),
        patch("app.api.emby_gateway.config.get_quark_cookie", return_value="quark-cookie"),
        patch("app.api.emby_gateway.EmbyProxyService", _FakeEmbyProxyService),
    ):
        response = client.get(
            "/Items/item123/PlaybackInfo",
            params={
                "UserId": "user123",
                "MediaSourceId": "media123",
                "api_key": "emby-api-key",
            },
            headers={
                "host": "proxy.example:18097",
                "X-Emby-Client": "Emby Web",
                "X-Emby-Device-Name": "Chrome on Windows",
                "User-Agent": "Mozilla/5.0",
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["is_web_client"] is True
    assert data["client_name"] == "Emby Web"
    assert data["device_name"] == "Chrome on Windows"
    assert _FakeEmbyProxyService.last_proxy_playback_info_call is not None
    assert _FakeEmbyProxyService.last_proxy_playback_info_call["is_web_client"] is True


def test_gateway_playbackinfo_when_post_body_uses_emby_contract_then_intercepts_and_forwards_payload():
    client = _build_client()
    app_config = _mock_config()

    with (
        patch("app.api.emby_gateway.config_service.get_config", return_value=app_config),
        patch("app.api.emby_gateway.config.get_quark_cookie", return_value="quark-cookie"),
        patch("app.api.emby_gateway.EmbyProxyService", _FakeEmbyProxyService),
        patch(
            "app.api.emby_gateway._forward_to_emby",
            new=AsyncMock(side_effect=AssertionError("should not forward PlaybackInfo POST upstream")),
        ),
    ):
        response = client.post(
            "/Items/item123/PlaybackInfo",
            headers={"host": "proxy.example:18097", "X-MediaBrowser-Token": "legacy-emby-api-key"},
            json={
                "UserId": "user123",
                "MediaSourceId": "media123",
                "DeviceProfile": {"Name": "Android TV"},
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["item_id"] == "item123"
    assert data["user_id"] == "user123"
    assert data["media_source_id"] == "media123"
    assert data["playback_request"] == {
        "UserId": "user123",
        "MediaSourceId": "media123",
        "DeviceProfile": {"Name": "Android TV"},
    }
    assert _FakeEmbyProxyService.last_init is not None
    assert _FakeEmbyProxyService.last_init["api_key"] == "legacy-emby-api-key"


def test_gateway_videos_stream_when_head_requested_on_dedicated_proxy_host_then_intercepts_local_stream_path():
    client = _build_client()
    app_config = _mock_config()

    with (
        patch("app.api.emby_gateway.config_service.get_config", return_value=app_config),
        patch(
            "app.api.emby_gateway._handle_emby_style_stream",
            new=AsyncMock(
                return_value=Response(
                    content=b"",
                    media_type="video/x-matroska",
                    status_code=200,
                    headers={
                        "Content-Length": "67600285904",
                        "Accept-Ranges": "bytes",
                    },
                )
            ),
        ) as mock_stream,
        patch(
            "app.api.emby_gateway._forward_to_emby",
            new=AsyncMock(side_effect=AssertionError("should not forward to upstream emby")),
        ),
    ):
        response = client.head(
            "/Videos/item123/stream",
            params={"MediaSourceId": "media123", "Static": "true", "container": "mkv", "smart_media_proxy": "1"},
            headers={"host": "proxy.example:18097"},
        )

    assert response.status_code == 200
    assert response.content == b""
    assert response.headers["Content-Length"] == "67600285904"
    assert response.headers["Accept-Ranges"] == "bytes"
    mock_stream.assert_awaited_once()


def test_gateway_videos_stream_when_dedicated_proxy_host_then_intercepts_local_stream_path():
    client = _build_client()
    app_config = _mock_config()

    with (
        patch("app.api.emby_gateway.config_service.get_config", return_value=app_config),
        patch(
            "app.api.emby_gateway._handle_emby_style_stream",
            new=AsyncMock(return_value=Response(content=b"stream-body", media_type="video/mp4", status_code=206)),
        ) as mock_stream,
        patch(
            "app.api.emby_gateway._forward_to_emby",
            new=AsyncMock(side_effect=AssertionError("should not forward to upstream emby")),
        ),
    ):
        response = client.get(
            "/Videos/item123/stream",
            params={"MediaSourceId": "media123", "Static": "true", "container": "mkv", "smart_media_proxy": "1"},
            headers={"host": "proxy.example:18097", "Range": "bytes=0-1"},
        )

    assert response.status_code == 206
    assert response.content == b"stream-body"
    mock_stream.assert_awaited_once()


def test_gateway_videos_stream_when_container_suffix_present_then_intercepts_local_stream_path():
    client = _build_client()
    app_config = _mock_config()

    with (
        patch("app.api.emby_gateway.config_service.get_config", return_value=app_config),
        patch(
            "app.api.emby_gateway._handle_emby_style_stream",
            new=AsyncMock(return_value=Response(content=b"stream-body", media_type="video/mp4", status_code=206)),
        ) as mock_stream,
        patch(
            "app.api.emby_gateway._forward_to_emby",
            new=AsyncMock(side_effect=AssertionError("should not forward to upstream emby")),
        ),
    ):
        response = client.get(
            "/Videos/item123/stream.mkv",
            params={"MediaSourceId": "media123", "Static": "true", "smart_media_proxy": "1"},
            headers={"host": "proxy.example:18097", "Range": "bytes=0-1"},
        )

    assert response.status_code == 206
    assert response.content == b"stream-body"
    mock_stream.assert_awaited_once()
    assert mock_stream.await_args.kwargs["filename"] == "mkv"


def test_gateway_videos_stream_when_prefixed_lowercase_path_used_then_intercepts_local_stream_path():
    client = _build_client()
    app_config = _mock_config()

    with (
        patch("app.api.emby_gateway.config_service.get_config", return_value=app_config),
        patch(
            "app.api.emby_gateway._handle_emby_style_stream",
            new=AsyncMock(return_value=Response(content=b"stream-body", media_type="video/mp4", status_code=206)),
        ) as mock_stream,
        patch(
            "app.api.emby_gateway._forward_to_emby",
            new=AsyncMock(side_effect=AssertionError("should not forward prefixed lowercase stream upstream")),
        ),
    ):
        response = client.get(
            "/emby/videos/item123/stream.mkv",
            params={"MediaSourceId": "media123", "Static": "true", "smart_media_proxy": "1"},
            headers={"host": "proxy.example:18097", "Range": "bytes=0-1"},
        )

    assert response.status_code == 206
    assert response.content == b"stream-body"
    mock_stream.assert_awaited_once()
    assert mock_stream.await_args.kwargs["filename"] == "mkv"


def test_gateway_videos_master_playlist_when_dedicated_proxy_host_then_intercepts_local_master_path():
    client = _build_client()
    app_config = _mock_config()

    with (
        patch("app.api.emby_gateway.config_service.get_config", return_value=app_config),
        patch(
            "app.api.emby_gateway._handle_emby_style_master_playlist",
            new=AsyncMock(
                return_value=Response(
                    content="#EXTM3U\n#EXT-X-VERSION:3\n#EXT-X-STREAM-INF:BANDWIDTH=8000000,RESOLUTION=1920x1080\n/api/proxy/transcoding/file123\n",
                    media_type="application/vnd.apple.mpegurl",
                    status_code=200,
                )
            ),
        ) as mock_master,
        patch(
            "app.api.emby_gateway._forward_to_emby",
            new=AsyncMock(side_effect=AssertionError("should not forward to upstream emby")),
        ),
    ):
        response = client.get(
            "/Videos/item123/master.m3u8",
            params={"MediaSourceId": "media123", "smart_media_proxy": "1"},
            headers={"host": "proxy.example:18097"},
        )

    assert response.status_code == 200
    assert "/api/proxy/transcoding/file123" in response.text
    mock_master.assert_awaited_once()


def test_gateway_videos_master_playlist_when_prefixed_lowercase_path_used_then_intercepts_local_master_path():
    client = _build_client()
    app_config = _mock_config()

    with (
        patch("app.api.emby_gateway.config_service.get_config", return_value=app_config),
        patch(
            "app.api.emby_gateway._handle_emby_style_master_playlist",
            new=AsyncMock(
                return_value=Response(
                    content="#EXTM3U\n#EXT-X-VERSION:3\n#EXT-X-STREAM-INF:BANDWIDTH=8000000,RESOLUTION=1920x1080\n/api/proxy/transcoding/file123\n",
                    media_type="application/vnd.apple.mpegurl",
                    status_code=200,
                )
            ),
        ) as mock_master,
        patch(
            "app.api.emby_gateway._forward_to_emby",
            new=AsyncMock(side_effect=AssertionError("should not forward prefixed lowercase master upstream")),
        ),
    ):
        response = client.get(
            "/emby/videos/item123/master.m3u8",
            params={"MediaSourceId": "media123", "smart_media_proxy": "1"},
            headers={"host": "proxy.example:18097"},
        )

    assert response.status_code == 200
    assert "/api/proxy/transcoding/file123" in response.text
    mock_master.assert_awaited_once()


def test_gateway_videos_master_playlist_when_head_requested_with_local_proxy_marker_then_intercepts_local_master_path():
    client = _build_client()
    app_config = _mock_config()

    with (
        patch("app.api.emby_gateway.config_service.get_config", return_value=app_config),
        patch(
            "app.api.emby_gateway._handle_emby_style_master_playlist",
            new=AsyncMock(
                return_value=Response(
                    content="",
                    media_type="application/vnd.apple.mpegurl",
                    status_code=200,
                    headers={"Cache-Control": "no-cache"},
                )
            ),
        ) as mock_master,
        patch(
            "app.api.emby_gateway._forward_to_emby",
            new=AsyncMock(side_effect=AssertionError("should not forward to upstream emby")),
        ),
    ):
        response = client.head(
            "/Videos/item123/master.m3u8",
            params={"MediaSourceId": "media123", "smart_media_proxy": "1"},
            headers={"host": "proxy.example:18097"},
        )

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-cache"
    mock_master.assert_awaited_once()


def test_gateway_videos_stream_when_marker_missing_then_forwards_upstream_emby():
    client = _build_client()
    app_config = _mock_config()

    with (
        patch("app.api.emby_gateway.config_service.get_config", return_value=app_config),
        patch(
            "app.api.emby_gateway._handle_emby_style_stream",
            new=AsyncMock(side_effect=AssertionError("should not intercept local stream without marker")),
        ),
        patch(
            "app.api.emby_gateway._forward_to_emby",
            new=AsyncMock(return_value=Response(content=b"upstream-stream", media_type="video/mp4", status_code=206)),
        ) as mock_forward,
    ):
        response = client.get(
            "/Videos/item123/stream",
            params={"MediaSourceId": "media123", "Static": "true", "container": "mkv"},
            headers={"host": "proxy.example:18097", "Range": "bytes=0-1"},
        )

    assert response.status_code == 206
    assert response.content == b"upstream-stream"
    mock_forward.assert_awaited_once()


def test_gateway_videos_master_playlist_when_marker_missing_then_forwards_upstream_emby():
    client = _build_client()
    app_config = _mock_config()

    with (
        patch("app.api.emby_gateway.config_service.get_config", return_value=app_config),
        patch(
            "app.api.emby_gateway._handle_emby_style_master_playlist",
            new=AsyncMock(side_effect=AssertionError("should not intercept local playlist without marker")),
        ),
        patch(
            "app.api.emby_gateway._forward_to_emby",
            new=AsyncMock(
                return_value=Response(
                    content="#EXTM3U\n# upstream emby\n",
                    media_type="application/vnd.apple.mpegurl",
                    status_code=200,
                )
            ),
        ) as mock_forward,
    ):
        response = client.get(
            "/Videos/item123/master.m3u8",
            params={"MediaSourceId": "media123"},
            headers={"host": "proxy.example:18097"},
        )

    assert response.status_code == 200
    assert "# upstream emby" in response.text
    mock_forward.assert_awaited_once()


@pytest.mark.asyncio
async def test_gateway_websocket_when_non_dedicated_host_then_closes_before_accept():
    ws = _FakeWebSocketClient("localhost:8000")
    app_config = _mock_config()

    with (
        patch("app.api.emby_gateway.config_service.get_config", return_value=app_config),
        patch(
            "app.api.emby_gateway.websockets.connect",
            new=AsyncMock(side_effect=AssertionError("should not connect upstream")),
        ),
    ):
        await emby_gateway_module.emby_gateway_websocket(ws)

    assert ws.accepted == 0
    assert ws.closed_codes == [1008]


@pytest.mark.asyncio
async def test_gateway_websocket_when_dedicated_host_then_accepts_and_proxies_upstream():
    ws = _FakeWebSocketClient("proxy.example:18097", query="api_key=emby-api-key")
    upstream_ws = _FakeUpstreamWebSocket()
    app_config = _mock_config()

    with (
        patch("app.api.emby_gateway.config_service.get_config", return_value=app_config),
        patch(
            "app.api.emby_gateway.websockets.connect",
            new=AsyncMock(return_value=upstream_ws),
        ) as mock_connect,
    ):
        await emby_gateway_module.emby_gateway_websocket(ws)

    assert ws.accepted == 1
    assert ws.closed_codes == [None]
    assert upstream_ws.closed is True
    mock_connect.assert_awaited_once()


@pytest.mark.asyncio
async def test_gateway_websocket_when_proxy_base_url_empty_and_port_18097_then_accepts_and_proxies_upstream():
    ws = _FakeWebSocketClient("127.0.0.1:18097", query="api_key=emby-api-key")
    upstream_ws = _FakeUpstreamWebSocket()
    app_config = _mock_config(proxy_base_url="")

    with (
        patch("app.api.emby_gateway.config_service.get_config", return_value=app_config),
        patch(
            "app.api.emby_gateway.websockets.connect",
            new=AsyncMock(return_value=upstream_ws),
        ) as mock_connect,
    ):
        await emby_gateway_module.emby_gateway_websocket(ws)

    assert ws.accepted == 1
    assert ws.closed_codes == [None]
    assert upstream_ws.closed is True
    mock_connect.assert_awaited_once()


def test_build_ws_target_url_when_https_emby_base_url_then_uses_wss_and_preserves_query():
    app_config = _mock_config()
    app_config.emby.url = "https://emby.example/base"
    ws = _FakeWebSocketClient("proxy.example:18097", query="api_key=emby-api-key&device=pytest")

    target_url = emby_gateway_module._build_ws_target_url(app_config, ws)

    assert target_url == "wss://emby.example/base/embywebsocket?api_key=emby-api-key&device=pytest"


def test_build_ws_extra_headers_when_handshake_headers_present_then_filters_reserved_headers():
    ws = _FakeWebSocketClient(
        "proxy.example:18097",
        headers={
            "connection": "Upgrade",
            "upgrade": "websocket",
            "sec-websocket-key": "secret",
            "sec-websocket-version": "13",
            "sec-websocket-protocol": "chat",
            "x-emby-token": "emby-api-key",
            "x-request-id": "req-1",
        },
    )

    headers = emby_gateway_module._build_ws_extra_headers(ws)

    assert ("host", "proxy.example:18097") not in headers
    assert ("connection", "Upgrade") not in headers
    assert ("upgrade", "websocket") not in headers
    assert ("sec-websocket-key", "secret") not in headers
    assert ("sec-websocket-version", "13") not in headers
    assert ("sec-websocket-protocol", "chat") not in headers
    assert ("user-agent", "pytest") in headers
    assert ("x-emby-token", "emby-api-key") in headers
    assert ("x-request-id", "req-1") in headers


def test_build_response_headers_when_conflicting_headers_then_strip_and_rewrite_location():
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
        "headers": [(b"host", b"proxy.example:18097")],
        "client": ("127.0.0.1", 12345),
        "server": ("proxy.example", 18097),
    }
    request = Request(scope)
    upstream_headers = httpx.Headers(
        {
            "content-length": "123",
            "content-encoding": "gzip",
            "date": "Sat, 14 Mar 2026 12:00:00 GMT",
            "server": "UPnP/1.0",
            "location": "http://emby.example:18096/web/index.html",
            "content-type": "application/json",
            "set-cookie": "a=1",
        }
    )

    headers = emby_gateway_module._build_response_headers(
        upstream_headers,
        emby_base_url="http://emby.example:18096",
        request=request,
    )

    lowered = {k.lower() for k in headers}
    assert "content-length" not in lowered
    assert "content-encoding" not in lowered
    assert "date" not in lowered
    assert "server" not in lowered
    assert "set-cookie" not in lowered
    assert headers["location"] == "http://proxy.example:18097/web/index.html"


# 注意：main_root 测试已更新，因为 root handler 现在定义在 app.main 中
# 但转发逻辑仍在 app.api.emby_gateway 模块中
# 这些测试已集成到 test_api_v1_routes.py 的 TestMainRouterRegistration 中


@pytest.mark.asyncio
async def test_forward_to_emby_when_multiple_requests_then_reuses_pool_client():
    app_config = _mock_config()
    fake_upstream = httpx.Response(
        status_code=200,
        headers={"content-type": "application/javascript"},
        content=b"console.log('ok')",
    )
    fake_client = SimpleNamespace(
        request=AsyncMock(return_value=fake_upstream),
        is_closed=False,
    )
    fake_pool = SimpleNamespace(get_client=AsyncMock(return_value=fake_client))

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/web/modules/commandprocessor.js",
        "raw_path": b"/web/modules/commandprocessor.js",
        "query_string": b"v=4.9.3.0",
        "headers": [(b"host", b"proxy.example:18097")],
        "client": ("127.0.0.1", 12345),
        "server": ("proxy.example", 18097),
    }

    with (
        patch("app.api.emby_gateway.get_http_pool_sync", new=Mock(return_value=fake_pool)),
        patch("app.api.emby_gateway.httpx.AsyncClient", side_effect=AssertionError("should not create new client")),
        patch.object(emby_gateway_module, "_forward_pool", None),
        patch.object(emby_gateway_module, "_forward_client", None),
    ):
        req1 = Request(scope)
        req2 = Request(scope)
        resp1 = await emby_gateway_module._forward_to_emby(req1, app_config, "web/modules/commandprocessor.js")
        resp2 = await emby_gateway_module._forward_to_emby(req2, app_config, "web/modules/commandprocessor.js")

    assert resp1.status_code == 200
    assert resp2.status_code == 200
    assert fake_pool.get_client.await_count == 1
    assert fake_client.request.await_count == 2


def test_build_forward_headers_when_accept_encoding_then_force_identity():
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/web/index.html",
        "raw_path": b"/web/index.html",
        "query_string": b"",
        "headers": [
            (b"host", b"proxy.example:18097"),
            (b"accept-encoding", b"gzip, deflate, br"),
            (b"user-agent", b"test-agent"),
        ],
        "client": ("127.0.0.1", 12345),
        "server": ("proxy.example", 18097),
    }
    request = Request(scope)

    headers = emby_gateway_module._build_forward_headers(request)

    lowered = {k.lower() for k in headers}
    assert "host" not in lowered
    assert headers["Accept-Encoding"] == "identity"
    assert headers["user-agent"] == "test-agent"


@pytest.mark.asyncio
async def test_forward_to_emby_when_multiple_set_cookie_then_preserves_all():
    app_config = _mock_config()
    fake_upstream = httpx.Response(
        status_code=200,
        headers=[
            ("content-type", "application/json"),
            ("set-cookie", "a=1; Path=/"),
            ("set-cookie", "b=2; Path=/"),
        ],
        content=b'{"ok":true}',
    )
    fake_client = SimpleNamespace(
        request=AsyncMock(return_value=fake_upstream),
        is_closed=False,
    )
    fake_pool = SimpleNamespace(get_client=AsyncMock(return_value=fake_client))

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/web/index.html",
        "raw_path": b"/web/index.html",
        "query_string": b"",
        "headers": [(b"host", b"proxy.example:18097")],
        "client": ("127.0.0.1", 12345),
        "server": ("proxy.example", 18097),
    }
    request = Request(scope)

    with (
        patch("app.api.emby_gateway.get_http_pool_sync", new=Mock(return_value=fake_pool)),
        patch.object(emby_gateway_module, "_forward_pool", None),
        patch.object(emby_gateway_module, "_forward_client", None),
    ):
        response = await emby_gateway_module._forward_to_emby(request, app_config, "web/index.html")

    cookies = response.headers.getlist("set-cookie")
    assert len(cookies) == 2
    assert cookies[0].startswith("a=1")
    assert cookies[1].startswith("b=2")
