from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.auth import router as auth_router
from app.services.auth_service import AuthService, JWT_ACCESS_TOKEN_EXPIRE_HOURS
from app.core.db import Base


@pytest.fixture(scope="function")
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    Base.metadata.create_all(bind=engine)
    session = session_local()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def create_auth_app() -> FastAPI:
    app = FastAPI()
    app.include_router(auth_router)
    return app


def test_verify_accepts_valid_jwt_tokens() -> None:
    app = create_auth_app()
    client = TestClient(app)

    with patch.dict(os.environ, {"REQUIRE_API_KEY": "true", "API_KEY": "expected-api-key"}):
        with patch("app.api.auth.AuthService.verify_access_token", return_value=1):
            response = client.get(
                "/api/auth/verify",
                headers={"Authorization": "Bearer signed-jwt-token"},
            )

    assert response.status_code == 200
    assert response.json() == {"valid": True, "message": "Token is valid"}


def test_auth_status_returns_initialized_admin_state_when_admin_exists() -> None:
    app = create_auth_app()
    client = TestClient(app)
    db = MagicMock()

    with patch("app.api.auth.SessionLocal", return_value=db):
        with patch("app.api.auth._get_expected_api_key", return_value=None):
            with patch("app.api.auth._is_auth_required", return_value=False):
                with patch("app.models.user.User.has_admin", return_value=True):
                    response = client.get("/api/auth/status")

    assert response.status_code == 200
    assert response.json() == {
        "auth_required": False,
        "has_api_key_configured": False,
        "message": "No authentication required",
        "has_admin_user": True,
        "can_init_admin": False,
    }
    db.close.assert_called_once()


def test_auth_status_allows_init_when_no_admin_and_bootstrap_is_trusted() -> None:
    app = create_auth_app()
    client = TestClient(app)
    db = MagicMock()

    with patch("app.api.auth.SessionLocal", return_value=db):
        with patch("app.api.auth._get_expected_api_key", return_value=None):
            with patch("app.api.auth._is_auth_required", return_value=False):
                with patch("app.models.user.User.has_admin", return_value=False):
                    with patch("app.api.auth._can_bootstrap_init_admin", return_value=True):
                        response = client.get("/api/auth/status")

    assert response.status_code == 200
    assert response.json() == {
        "auth_required": False,
        "has_api_key_configured": False,
        "message": "No authentication required",
        "has_admin_user": False,
        "can_init_admin": True,
    }
    db.close.assert_called_once()


def test_auth_status_disallows_init_when_no_admin_but_bootstrap_is_untrusted() -> None:
    app = create_auth_app()
    client = TestClient(app)
    db = MagicMock()

    with patch("app.api.auth.SessionLocal", return_value=db):
        with patch("app.api.auth._get_expected_api_key", return_value=None):
            with patch("app.api.auth._is_auth_required", return_value=False):
                with patch("app.models.user.User.has_admin", return_value=False):
                    with patch("app.api.auth._can_bootstrap_init_admin", return_value=False):
                        response = client.get("/api/auth/status")

    assert response.status_code == 200
    assert response.json() == {
        "auth_required": False,
        "has_api_key_configured": False,
        "message": "No authentication required",
        "has_admin_user": False,
        "can_init_admin": False,
    }
    db.close.assert_called_once()


def test_init_admin_preserves_conflict_status_when_admin_exists() -> None:
    app = create_auth_app()
    client = TestClient(app)
    db = MagicMock()

    with patch("app.api.auth.SessionLocal", return_value=db):
        with patch("app.models.user.User.has_admin", return_value=True):
            response = client.post("/api/auth/init-admin")

    assert response.status_code == 409
    assert response.json() == {"detail": "Admin user already initialized"}
    db.close.assert_called_once()


def test_init_admin_preserves_forbidden_status_for_untrusted_bootstrap() -> None:
    app = create_auth_app()
    client = TestClient(app)
    db = MagicMock()

    with patch("app.api.auth.SessionLocal", return_value=db):
        with patch("app.models.user.User.has_admin", return_value=False):
            response = client.post("/api/auth/init-admin")

    assert response.status_code == 403
    assert response.json() == {"detail": "Init-admin is only available for local first-time bootstrap"}
    db.close.assert_called_once()



def test_init_admin_still_rejects_untrusted_bootstrap_when_allow_public_env_enabled() -> None:
    app = create_auth_app()
    client = TestClient(app)
    db = MagicMock()

    with patch.dict(os.environ, {"ALLOW_PUBLIC_INIT_ADMIN": "true"}, clear=False):
        with patch("app.api.auth.SessionLocal", return_value=db):
            with patch("app.models.user.User.has_admin", return_value=False):
                response = client.post("/api/auth/init-admin")

    assert response.status_code == 403
    assert response.json() == {"detail": "Init-admin is only available for local first-time bootstrap"}
    db.close.assert_called_once()


def test_init_admin_rejects_missing_password_configuration() -> None:
    app = create_auth_app()
    client = TestClient(app)
    db = MagicMock()

    with patch.dict(os.environ, {}, clear=True):
        with patch("app.api.auth.SessionLocal", return_value=db):
            with patch("app.models.user.User.has_admin", return_value=False):
                with patch("app.api.auth._can_bootstrap_init_admin", return_value=True):
                    response = client.post("/api/auth/init-admin")

    assert response.status_code == 500
    assert response.json() == {"detail": "Admin bootstrap password is not configured"}
    db.close.assert_called_once()



def test_init_admin_does_not_return_plaintext_password_when_env_password_configured() -> None:
    app = create_auth_app()
    client = TestClient(app)
    db = MagicMock()
    created_admin = SimpleNamespace(username="admin")

    with patch.dict(os.environ, {"ADMIN_PASSWORD": "custom-admin-pass"}, clear=True):
        with patch("app.api.auth.SessionLocal", return_value=db):
            with patch("app.models.user.User.has_admin", return_value=False):
                with patch("app.api.auth._can_bootstrap_init_admin", return_value=True):
                    with patch("app.api.auth.AuthService.create_user", return_value=created_admin) as create_user:
                        response = client.post("/api/auth/init-admin")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["username"] == "admin"
    assert payload["password_generated"] is False
    assert payload["generated_password"] is None
    assert create_user.call_args.kwargs["password"] == "custom-admin-pass"
    db.close.assert_called_once()



def test_init_admin_does_not_leak_internal_error_details() -> None:
    app = create_auth_app()
    client = TestClient(app)
    db = MagicMock()

    with patch.dict(os.environ, {"ADMIN_PASSWORD": "custom-admin-pass"}, clear=True):
        with patch("app.api.auth.SessionLocal", return_value=db):
            with patch("app.models.user.User.has_admin", return_value=False):
                with patch("app.api.auth._can_bootstrap_init_admin", return_value=True):
                    with patch("app.api.auth.AuthService.create_user", side_effect=RuntimeError("db exploded: admin secret path")):
                        response = client.post("/api/auth/init-admin")

    assert response.status_code == 500
    assert response.json() == {"detail": "Failed to initialize admin"}
    db.close.assert_called_once()


def test_login_expires_in_matches_access_token_lifetime() -> None:
    app = create_auth_app()
    client = TestClient(app)

    user = SimpleNamespace(
        id=7,
        username="expiry-user",
        email=None,
        role="admin",
        is_active=True,
        created_at=None,
        last_login=None,
    )

    with patch("app.api.auth.SessionLocal", return_value=MagicMock()):
        with patch("app.api.auth.AuthService.authenticate_user", return_value=(user, None)):
            response = client.post(
                "/api/auth/login",
                json={"username": "expiry-user", "password": "correct-password"},
            )

    assert response.status_code == 200
    assert response.json()["expires_in"] == JWT_ACCESS_TOKEN_EXPIRE_HOURS * 3600
    assert f"Max-Age={JWT_ACCESS_TOKEN_EXPIRE_HOURS * 3600}" in response.headers["set-cookie"]



def test_api_key_login_exchanges_key_for_session_token() -> None:
    app = create_auth_app()
    client = TestClient(app)
    api_key = "super-secret-api-key"

    with patch("app.api.auth.SessionLocal", return_value=MagicMock()):
        with patch("app.api.auth._get_expected_api_key", return_value=api_key):
            response = client.post(
                "/api/auth/login",
                json={"api_key": api_key},
            )

    assert response.status_code == 200
    payload = response.json()
    assert payload["access_token"] != api_key
    assert payload["refresh_token"] != api_key
    assert api_key not in response.headers["set-cookie"]


def test_api_key_login_accepts_canonical_security_env_alias() -> None:
    app = create_auth_app()
    client = TestClient(app)

    with patch.dict(os.environ, {"SMART_MEDIA_SECURITY_API_KEY": "canonical-env-key"}, clear=True):
        with patch("app.api.auth.SessionLocal", return_value=MagicMock()):
            response = client.post(
                "/api/auth/login",
                json={"api_key": "canonical-env-key"},
            )

    assert response.status_code == 200
    assert response.json()["access_token"]


def test_api_key_login_prefers_canonical_security_env_over_legacy_aliases() -> None:
    app = create_auth_app()
    client = TestClient(app)

    with patch.dict(
        os.environ,
        {
            "SMART_MEDIA_SECURITY_API_KEY": "canonical-env-key",
            "SMART_MEDIA_API_KEY": "legacy-smart-key",
            "API_KEY": "legacy-key",
        },
        clear=True,
    ):
        with patch("app.api.auth.SessionLocal", return_value=MagicMock()):
            canonical = client.post("/api/auth/login", json={"api_key": "canonical-env-key"})
            legacy = client.post("/api/auth/login", json={"api_key": "legacy-smart-key"})

    assert canonical.status_code == 200
    assert legacy.status_code == 403


def test_login_returns_distinct_refresh_token() -> None:
    app = create_auth_app()
    client = TestClient(app)

    user = SimpleNamespace(
        id=9,
        username="refresh-user",
        email=None,
        role="admin",
        is_active=True,
        created_at=None,
        last_login=None,
    )

    with patch("app.api.auth.SessionLocal", return_value=MagicMock()):
        with patch("app.api.auth.AuthService.authenticate_user", return_value=(user, None)):
            response = client.post(
                "/api/auth/login",
                json={"username": "refresh-user", "password": "correct-password"},
            )

    assert response.status_code == 200
    payload = response.json()
    assert payload["access_token"]
    assert payload["refresh_token"]
    assert payload["refresh_token"] != payload["access_token"]


def test_refresh_returns_new_access_token_for_valid_refresh_token() -> None:
    app = create_auth_app()
    client = TestClient(app)
    db = MagicMock()
    user = SimpleNamespace(id=7, username="refresh-user", role="admin")

    with patch("app.api.auth.SessionLocal", return_value=db):
        with patch("app.api.auth.AuthService.verify_refresh_token", return_value=7):
            with patch("app.models.user.User.get_by_id", return_value=user):
                with patch("app.api.auth.AuthService.create_access_token", return_value="new-access-token"):
                    response = client.post(
                        "/api/auth/refresh",
                        json={"refresh_token": "valid-refresh-token"},
                    )

    assert response.status_code == 200
    assert response.json()["access_token"] == "new-access-token"
    assert response.json()["token_type"] == "bearer"


def test_refresh_supports_api_key_session_tokens() -> None:
    app = create_auth_app()
    client = TestClient(app)
    db = MagicMock()

    with patch("app.api.auth.SessionLocal", return_value=db):
        with patch("app.api.auth.AuthService.verify_refresh_token", return_value=0):
            with patch("app.api.auth.AuthService.create_access_token", return_value="api-key-access-token") as create_access_token:
                response = client.post(
                    "/api/auth/refresh",
                    json={"refresh_token": "api-key-refresh-token"},
                )

    assert response.status_code == 200
    assert response.json()["access_token"] == "api-key-access-token"
    create_access_token.assert_called_once_with(user_id=0, username="api-key", role="api_key")


def test_change_password_updates_password_for_authenticated_user() -> None:
    app = create_auth_app()
    client = TestClient(app)
    db = MagicMock()
    current_user = SimpleNamespace(id=1, username="admin", password_hash="hashed", role="admin", is_active=True)

    with patch("app.api.auth.SessionLocal", return_value=db):
        with patch("app.api.auth.AuthService.decode_token", return_value={"sub": "1", "type": "access"}):
            with patch("app.models.user.User.get_by_id", return_value=current_user):
                with patch("app.api.auth.AuthService.change_password", return_value=True) as change_password:
                    client.cookies.set("auth_token", "valid-access-token")
                    response = client.post(
                        "/api/auth/change-password",
                        json={"old_password": "old-password", "new_password": "new-password"},
                    )

    assert response.status_code == 200
    assert response.json() == {"success": True, "message": "Password changed successfully"}
    change_password.assert_called_once()


def test_me_returns_authenticated_user_from_cookie_token() -> None:
    app = create_auth_app()
    client = TestClient(app)
    db = MagicMock()
    current_user = SimpleNamespace(
        id=1,
        username="admin",
        email="admin@example.com",
        role="admin",
        is_active=True,
        created_at=None,
        last_login=None,
    )

    with patch("app.api.auth.SessionLocal", return_value=db):
        with patch("app.api.auth.AuthService.decode_token", return_value={"sub": "1", "type": "access"}):
            with patch("app.models.user.User.get_by_id", return_value=current_user):
                client.cookies.set("auth_token", "valid-access-token")
                response = client.get(
                    "/api/auth/me",
                )

    assert response.status_code == 200
    assert response.json()["username"] == "admin"
    assert response.json()["email"] == "admin@example.com"


def test_me_returns_authenticated_user_from_bearer_token() -> None:
    app = create_auth_app()
    client = TestClient(app)
    db = MagicMock()
    current_user = SimpleNamespace(
        id=2,
        username="bearer-admin",
        email=None,
        role="admin",
        is_active=True,
        created_at=None,
        last_login=None,
    )

    with patch("app.api.auth.SessionLocal", return_value=db):
        with patch("app.api.auth.AuthService.decode_token", return_value={"sub": "2", "type": "access"}):
            with patch("app.models.user.User.get_by_id", return_value=current_user):
                response = client.get(
                    "/api/auth/me",
                    headers={"Authorization": "Bearer valid-access-token"},
                )

    assert response.status_code == 200
    assert response.json()["username"] == "bearer-admin"


def test_me_rejects_missing_token() -> None:
    app = create_auth_app()
    client = TestClient(app)
    db = MagicMock()

    with patch("app.api.auth.SessionLocal", return_value=db):
        response = client.get("/api/auth/me")

    assert response.status_code == 401
    assert response.json() == {"detail": "未登录"}


def test_me_rejects_missing_user_for_valid_token() -> None:
    app = create_auth_app()
    client = TestClient(app)
    db = MagicMock()

    with patch("app.api.auth.SessionLocal", return_value=db):
        with patch("app.api.auth.AuthService.decode_token", return_value={"sub": "3", "type": "access"}):
            with patch("app.models.user.User.get_by_id", return_value=None):
                client.cookies.set("auth_token", "valid-access-token")
                response = client.get(
                    "/api/auth/me",
                )

    assert response.status_code == 401
    assert response.json() == {"detail": "用户不存在"}


def test_me_prefers_authorization_header_over_invalid_cookie() -> None:
    app = create_auth_app()
    client = TestClient(app)
    db = MagicMock()
    current_user = SimpleNamespace(
        id=4,
        username="header-user",
        email=None,
        role="admin",
        is_active=True,
        created_at=None,
        last_login=None,
    )

    def decode_token(token: str):
        if token == "valid-header-token":
            return {"sub": "4", "type": "access"}
        return None

    with patch("app.api.auth.SessionLocal", return_value=db):
        with patch("app.api.auth.AuthService.decode_token", side_effect=decode_token):
            with patch("app.models.user.User.get_by_id", return_value=current_user):
                client.cookies.set("auth_token", "expired-cookie-token")
                response = client.get(
                    "/api/auth/me",
                    headers={"Authorization": "Bearer valid-header-token"},
                )

    assert response.status_code == 200
    assert response.json()["username"] == "header-user"
