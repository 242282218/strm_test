from __future__ import annotations

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
