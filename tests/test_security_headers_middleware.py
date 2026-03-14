from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.security_headers_middleware import SecurityHeadersMiddleware


def create_security_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware)

    @app.get("/emby/system/info/public")
    async def system_info():
        return {"ok": True}

    return app


def test_security_headers_when_dedicated_proxy_request_then_skip() -> None:
    client = TestClient(create_security_app())

    response = client.get("/emby/system/info/public", headers={"host": "127.0.0.1:18097"})

    assert response.status_code == 200
    assert "content-security-policy" not in response.headers
    assert "x-frame-options" not in response.headers


def test_security_headers_when_normal_request_then_add() -> None:
    client = TestClient(create_security_app())

    response = client.get("/emby/system/info/public", headers={"host": "127.0.0.1:8001"})

    assert response.status_code == 200
    assert response.headers.get("x-frame-options") == "DENY"
    assert "content-security-policy" in response.headers
