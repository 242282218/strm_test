from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from fastapi.testclient import TestClient
from starlette.requests import Request

import app.api.emby_gateway as emby_gateway_module
from app.api.emby_gateway import router as emby_gateway_router
from app.main import root as main_root_handler


class _FakeEmbyProxyService:
    last_init: dict[str, str] | None = None

    def __init__(self, emby_base_url: str, api_key: str, cookie: str, proxy_base_url: str):
        _FakeEmbyProxyService.last_init = {
            "emby_base_url": emby_base_url,
            "api_key": api_key,
            "cookie": cookie,
            "proxy_base_url": proxy_base_url,
        }
        self.proxy_base_url = proxy_base_url

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return None

    async def proxy_playback_info(self, item_id: str, user_id: str, media_source_id: str | None = None):
        return {
            "item_id": item_id,
            "user_id": user_id,
            "media_source_id": media_source_id,
            "proxy_base_url": self.proxy_base_url,
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


@pytest.mark.asyncio
async def test_main_root_when_dedicated_proxy_host_then_forwards_to_emby():
    app_config = _mock_config()
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

    with (
        patch("app.main.emby_gateway.config_service.get_config", return_value=app_config),
        patch(
            "app.main.emby_gateway._forward_to_emby",
            new=AsyncMock(return_value=Response(content="emby-home", media_type="text/html")),
        ),
    ):
        response = await main_root_handler(request)

    assert response.status_code == 200
    assert b"emby-home" in response.body


@pytest.mark.asyncio
async def test_main_root_when_dedicated_proxy_and_forward_fails_then_returns_502():
    app_config = _mock_config()
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

    with (
        patch("app.main.emby_gateway.config_service.get_config", return_value=app_config),
        patch(
            "app.main.emby_gateway._forward_to_emby",
            new=AsyncMock(side_effect=RuntimeError("forward failed")),
        ),
        pytest.raises(HTTPException) as exc_info,
    ):
        await main_root_handler(request)

    assert exc_info.value.status_code == 502


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
