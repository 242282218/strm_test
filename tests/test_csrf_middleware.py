from __future__ import annotations

from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.csrf_middleware import CSRFMiddleware


def create_csrf_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(CSRFMiddleware)

    @app.get("/")
    async def root():
        return {"ok": True}

    @app.post("/api/protected")
    async def protected():
        return {"ok": True}

    @app.post("/api/emby/items/144/PlaybackInfo")
    async def emby_playback_info():
        return {"ok": True, "route": "playback"}

    @app.post("/api/emby/not-emby")
    async def emby_non_proxy_path():
        return {"ok": True, "route": "non-proxy"}

    @app.post("/api/auth/refresh")
    async def refresh():
        return {"ok": True}

    @app.post("/emby/Users/authenticatebyname")
    async def emby_authenticate():
        return {"ok": True}

    return app


def test_post_requires_csrf_token_for_non_exempt_routes() -> None:
    client = TestClient(create_csrf_app())

    bootstrap = client.get("/")
    assert bootstrap.status_code == 200
    assert "csrf_token" in bootstrap.cookies

    response = client.post("/api/protected")

    assert response.status_code == 403
    assert response.json() == {"detail": "CSRF token validation failed"}


def test_post_when_dedicated_proxy_port_then_skip_csrf_validation() -> None:
    client = TestClient(create_csrf_app())

    response = client.post(
        "/emby/Users/authenticatebyname",
        headers={"host": "127.0.0.1:18097"},
        json={"Username": "demo", "Pw": "demo"},
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert response.cookies.get("csrf_token") is None


def test_non_emby_path_on_dedicated_proxy_port_still_requires_csrf() -> None:
    client = TestClient(create_csrf_app())

    response = client.post(
        "/api/protected",
        headers={"host": "127.0.0.1:18097"},
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "CSRF token validation failed"}


def test_api_emby_playbackinfo_on_dedicated_proxy_port_skips_csrf() -> None:
    client = TestClient(create_csrf_app())

    response = client.post(
        "/api/emby/items/144/PlaybackInfo",
        headers={"host": "127.0.0.1:18097"},
        json={"StartTimeTicks": 0},
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True, "route": "playback"}


def test_api_emby_non_proxy_path_on_dedicated_proxy_port_still_requires_csrf() -> None:
    client = TestClient(create_csrf_app())

    response = client.post(
        "/api/emby/not-emby",
        headers={"host": "127.0.0.1:18097"},
        json={"x": 1},
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "CSRF token validation failed"}


def test_refresh_route_is_csrf_exempt() -> None:
    client = TestClient(create_csrf_app())

    response = client.post("/api/auth/refresh")

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_emby_path_on_configured_proxy_base_url_skips_csrf() -> None:
    config = type("Cfg", (), {"emby": type("EmbyCfg", (), {"proxy_base_url": "http://proxy.example:19097"})()})()

    with patch("app.core.emby_proxy_request.get_config_service") as mock_get_config_service:
        mock_get_config_service.return_value.get_config.return_value = config
        client = TestClient(create_csrf_app())
        response = client.post(
            "/emby/Users/authenticatebyname",
            headers={"host": "proxy.example:19097"},
            json={"Username": "demo", "Pw": "demo"},
        )

    assert response.status_code == 200
    assert response.json() == {"ok": True}
