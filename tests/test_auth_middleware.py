"""
Tests for AuthMiddleware

Tests cover:
- Public path access without authentication
- Protected path requires authentication
- Valid API key grants access
- Invalid API key denied
- Bearer token authentication
- Environment variable configuration
"""

from __future__ import annotations

import inspect
import os
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.auth_middleware import AuthMiddleware


# Create a simple test app
def create_test_app() -> FastAPI:
    """Create a minimal FastAPI app for testing."""
    app = FastAPI()

    @app.get("/")
    async def root():
        return {"message": "root"}

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/ready")
    async def ready():
        return {"status": "ready"}

    @app.get("/health/ready")
    async def health_ready():
        return {"status": "ready"}

    @app.get("/api/protected")
    async def protected():
        return {"message": "protected"}

    @app.get("/api/data")
    async def data():
        return {"data": "sensitive"}

    @app.get("/api/emby/items/144/PlaybackInfo")
    async def emby_playback_info():
        return {"ok": True, "route": "playback"}

    @app.get("/api/emby/not-emby")
    async def emby_non_proxy_path():
        return {"ok": True, "route": "non-proxy"}

    @app.get("/api/auth/status")
    async def auth_status():
        return {"auth_required": True}

    @app.get("/api/auth/verify")
    async def auth_verify():
        return {"valid": True}

    @app.post("/api/auth/init-admin")
    async def init_admin():
        return {"ok": True}

    return app


class TestPublicPathNoAuthRequired:
    """Test that public paths don't require authentication."""

    def test_root_path_no_auth_required(self):
        """Root path should be accessible without authentication."""
        app = create_test_app()
        app.add_middleware(AuthMiddleware)

        with patch.dict(os.environ, {"REQUIRE_API_KEY": "true", "API_KEY": "test-key"}):
            client = TestClient(app)
            response = client.get("/")
            assert response.status_code == 200
            assert response.json() == {"message": "root"}

    def test_health_path_no_auth_required(self):
        """Health check path should be accessible without authentication."""
        app = create_test_app()
        app.add_middleware(AuthMiddleware)

        with patch.dict(os.environ, {"REQUIRE_API_KEY": "true", "API_KEY": "test-key"}):
            client = TestClient(app)
            response = client.get("/health")
            assert response.status_code == 200
            assert response.json() == {"status": "ok"}

    def test_ready_paths_no_auth_required(self):
        """Readiness probe paths should be accessible without authentication."""
        app = create_test_app()
        app.add_middleware(AuthMiddleware)

        with patch.dict(os.environ, {"REQUIRE_API_KEY": "true", "API_KEY": "test-key"}):
            client = TestClient(app)
            ready = client.get("/ready")
            health_ready = client.get("/health/ready")
            assert ready.status_code == 200
            assert health_ready.status_code == 200

    def test_docs_path_no_auth_required(self):
        """API docs path should be accessible without authentication."""
        app = create_test_app()
        app.add_middleware(AuthMiddleware)

        with patch.dict(os.environ, {"REQUIRE_API_KEY": "true", "API_KEY": "test-key"}):
            client = TestClient(app)
            response = client.get("/docs")
            assert response.status_code == 200

    def test_openapi_json_no_auth_required(self):
        """OpenAPI JSON should be accessible without authentication."""
        app = create_test_app()
        app.add_middleware(AuthMiddleware)

        with patch.dict(os.environ, {"REQUIRE_API_KEY": "true", "API_KEY": "test-key"}):
            client = TestClient(app)
            response = client.get("/openapi.json")
            assert response.status_code == 200

    def test_static_path_no_auth_required(self):
        """Static file paths should be accessible without authentication."""
        app = create_test_app()
        app.add_middleware(AuthMiddleware)

        with patch.dict(os.environ, {"REQUIRE_API_KEY": "true", "API_KEY": "test-key"}):
            client = TestClient(app)
            # Static paths are whitelisted
            response = client.get("/static/test.css")
            # Will return 404 because route doesn't exist, but not 401
            assert response.status_code == 404

    def test_auth_status_path_no_auth_required(self):
        """Auth status endpoint should be accessible without authentication."""
        app = create_test_app()
        app.add_middleware(AuthMiddleware)

        with patch.dict(os.environ, {"REQUIRE_API_KEY": "true", "API_KEY": "test-key"}):
            client = TestClient(app)
            response = client.get("/api/auth/status")
            assert response.status_code == 200
            assert response.json() == {"auth_required": True}

    def test_auth_verify_path_no_auth_required(self):
        """Auth verify endpoint should be accessible without authentication."""
        app = create_test_app()
        app.add_middleware(AuthMiddleware)

        with patch.dict(os.environ, {"REQUIRE_API_KEY": "true", "API_KEY": "test-key"}):
            client = TestClient(app)
            response = client.get("/api/auth/verify")
            assert response.status_code == 200
            assert response.json() == {"valid": True}

    def test_non_emby_path_on_dedicated_proxy_port_still_requires_auth(self):
        """Dedicated proxy port alone must not make arbitrary API paths public."""
        app = create_test_app()
        app.add_middleware(AuthMiddleware)

        with patch.dict(os.environ, {"REQUIRE_API_KEY": "true", "API_KEY": "test-key"}):
            client = TestClient(app)
            response = client.get("/api/protected", headers={"host": "127.0.0.1:18097"})
            assert response.status_code == 401

    def test_api_emby_playbackinfo_on_dedicated_proxy_port_is_public(self):
        """Dedicated proxy PlaybackInfo route should bypass app auth for Emby clients."""
        app = create_test_app()
        app.add_middleware(AuthMiddleware)

        with patch.dict(os.environ, {"REQUIRE_API_KEY": "true", "API_KEY": "test-key"}):
            client = TestClient(app)
            response = client.get("/api/emby/items/144/PlaybackInfo", headers={"host": "127.0.0.1:18097"})
            assert response.status_code == 200
            assert response.json() == {"ok": True, "route": "playback"}

    def test_api_emby_non_proxy_path_on_dedicated_proxy_port_still_requires_auth(self):
        """Non-proxy /api/emby paths must not become public just because the host matches."""
        app = create_test_app()
        app.add_middleware(AuthMiddleware)

        with patch.dict(os.environ, {"REQUIRE_API_KEY": "true", "API_KEY": "test-key"}):
            client = TestClient(app)
            response = client.get("/api/emby/not-emby", headers={"host": "127.0.0.1:18097"})
            assert response.status_code == 401


class TestProtectedPathRequiresAuth:
    """Test that protected paths require authentication."""

    def test_protected_path_requires_auth_when_enabled(self):
        """Protected path should return 401 when no API key provided."""
        app = create_test_app()
        app.add_middleware(AuthMiddleware)

        with patch.dict(os.environ, {"REQUIRE_API_KEY": "true", "API_KEY": "test-key"}):
            client = TestClient(app)
            response = client.get("/api/protected")
            assert response.status_code == 401
            assert "API key is required" in response.json().get("detail", "")

    def test_protected_path_returns_401_without_key(self):
        """Protected path should return 401 without any API key."""
        app = create_test_app()
        app.add_middleware(AuthMiddleware)

        with patch.dict(os.environ, {"REQUIRE_API_KEY": "true", "API_KEY": "test-key"}):
            client = TestClient(app)
            response = client.get("/api/data")
            assert response.status_code == 401

    def test_protected_path_accessible_when_auth_disabled(self):
        """Protected path should be accessible when authentication is disabled."""
        app = create_test_app()
        app.add_middleware(AuthMiddleware)

        with patch.dict(os.environ, {"REQUIRE_API_KEY": "false"}):
            client = TestClient(app)
            response = client.get("/api/protected")
            assert response.status_code == 200
            assert response.json() == {"message": "protected"}

    def test_init_admin_not_public_by_default(self):
        """Init-admin should not be publicly callable by default."""
        app = create_test_app()
        app.add_middleware(AuthMiddleware)

        with patch.dict(os.environ, {"REQUIRE_API_KEY": "true", "API_KEY": "test-key"}):
            client = TestClient(app)
            response = client.post("/api/auth/init-admin")
            assert response.status_code == 401

    def test_init_admin_not_public_even_when_allow_public_env_enabled(self):
        """Init-admin should still require a trusted local request even if ALLOW_PUBLIC_INIT_ADMIN is set."""
        app = create_test_app()
        app.add_middleware(AuthMiddleware)

        with patch.dict(
            os.environ,
            {"REQUIRE_API_KEY": "true", "API_KEY": "test-key", "ALLOW_PUBLIC_INIT_ADMIN": "true"},
        ):
            client = TestClient(app)
            response = client.post("/api/auth/init-admin")
            assert response.status_code == 401


class TestValidApiKeyGrantsAccess:
    """Test that valid API key grants access to protected paths."""

    def test_valid_x_api_key_header_grants_access(self):
        """Valid X-API-Key header should grant access."""
        app = create_test_app()
        app.add_middleware(AuthMiddleware)

        with patch.dict(os.environ, {"REQUIRE_API_KEY": "true", "API_KEY": "test-key-123"}):
            client = TestClient(app)
            response = client.get(
                "/api/protected",
                headers={"X-API-Key": "test-key-123"}
            )
            assert response.status_code == 200
            assert response.json() == {"message": "protected"}

    def test_valid_bearer_token_grants_access(self):
        """Valid Bearer token should grant access."""
        app = create_test_app()
        app.add_middleware(AuthMiddleware)

        with patch.dict(os.environ, {"REQUIRE_API_KEY": "true", "API_KEY": "bearer-token-456"}):
            client = TestClient(app)
            response = client.get(
                "/api/data",
                headers={"Authorization": "Bearer bearer-token-456"}
            )
            assert response.status_code == 200
            assert response.json() == {"data": "sensitive"}

    def test_explicit_header_overrides_invalid_auth_cookie(self):
        """Explicit header credentials should override stale auth cookies."""
        app = create_test_app()
        app.add_middleware(AuthMiddleware)

        with patch.dict(os.environ, {"REQUIRE_API_KEY": "true", "API_KEY": "header-token-456"}):
            client = TestClient(app)
            client.cookies.set("auth_token", "stale-cookie-token")
            response = client.get(
                "/api/data",
                headers={"Authorization": "Bearer header-token-456"},
            )
            assert response.status_code == 200
            assert response.json() == {"data": "sensitive"}

    def test_smart_media_api_key_env_var_works(self):
        """SMART_MEDIA_API_KEY environment variable should work."""
        app = create_test_app()
        app.add_middleware(AuthMiddleware)

        with patch.dict(os.environ, {"REQUIRE_API_KEY": "true", "SMART_MEDIA_API_KEY": "smart-key-789"}):
            client = TestClient(app)
            response = client.get(
                "/api/protected",
                headers={"X-API-Key": "smart-key-789"}
            )
            assert response.status_code == 200

    def test_smart_media_security_api_key_env_var_works(self):
        """SMART_MEDIA_SECURITY_API_KEY should work as the canonical env override."""
        app = create_test_app()
        app.add_middleware(AuthMiddleware)

        with patch.dict(os.environ, {"REQUIRE_API_KEY": "true", "SMART_MEDIA_SECURITY_API_KEY": "security-key-987"}, clear=True):
            client = TestClient(app)
            response = client.get(
                "/api/protected",
                headers={"X-API-Key": "security-key-987"}
            )
            assert response.status_code == 200

    def test_canonical_security_api_key_env_overrides_legacy_aliases(self):
        """Canonical security env should win when legacy aliases are also configured."""
        app = create_test_app()
        app.add_middleware(AuthMiddleware)

        with patch.dict(
            os.environ,
            {
                "REQUIRE_API_KEY": "true",
                "SMART_MEDIA_SECURITY_API_KEY": "canonical-key",
                "SMART_MEDIA_API_KEY": "legacy-smart-key",
                "API_KEY": "legacy-key",
            },
            clear=True,
        ):
            client = TestClient(app)
            canonical = client.get("/api/protected", headers={"X-API-Key": "canonical-key"})
            legacy = client.get("/api/protected", headers={"X-API-Key": "legacy-smart-key"})

            assert canonical.status_code == 200
            assert legacy.status_code == 403


class TestInvalidApiKeyDenied:
    """Test that invalid API key is denied access."""

    def test_invalid_api_key_denied(self):
        """Invalid API key should return 403 Forbidden."""
        app = create_test_app()
        app.add_middleware(AuthMiddleware)

        with patch.dict(os.environ, {"REQUIRE_API_KEY": "true", "API_KEY": "correct-key"}):
            client = TestClient(app)
            response = client.get(
                "/api/protected",
                headers={"X-API-Key": "wrong-key"}
            )
            assert response.status_code == 403
            assert "Invalid API key" in response.json().get("detail", "")

    def test_empty_api_key_denied(self):
        """Empty API key should return 401 Unauthorized."""
        app = create_test_app()
        app.add_middleware(AuthMiddleware)

        with patch.dict(os.environ, {"REQUIRE_API_KEY": "true", "API_KEY": "test-key"}):
            client = TestClient(app)
            response = client.get(
                "/api/protected",
                headers={"X-API-Key": ""}
            )
            assert response.status_code == 401

    def test_malformed_bearer_token_denied(self):
        """Malformed Bearer token should return 401."""
        app = create_test_app()
        app.add_middleware(AuthMiddleware)

        with patch.dict(os.environ, {"REQUIRE_API_KEY": "true", "API_KEY": "test-key"}):
            client = TestClient(app)
            response = client.get(
                "/api/protected",
                headers={"Authorization": "Basic test-key"}
            )
            assert response.status_code == 401


class TestEnvironmentVariableConfiguration:
    """Test environment variable configuration."""

    def test_require_api_key_true_enables_auth(self):
        """REQUIRE_API_KEY=true should enable authentication."""
        app = create_test_app()
        app.add_middleware(AuthMiddleware)

        with patch.dict(os.environ, {"REQUIRE_API_KEY": "true", "API_KEY": "test-key"}):
            client = TestClient(app)
            response = client.get("/api/protected")
            assert response.status_code == 401

    def test_require_api_key_false_disables_auth(self):
        """REQUIRE_API_KEY=false should disable authentication."""
        app = create_test_app()
        app.add_middleware(AuthMiddleware)

        with patch.dict(os.environ, {"REQUIRE_API_KEY": "false", "API_KEY": "test-key"}):
            client = TestClient(app)
            response = client.get("/api/protected")
            assert response.status_code == 200

    def test_require_api_key_1_enables_auth(self):
        """REQUIRE_API_KEY=1 should enable authentication."""
        app = create_test_app()
        app.add_middleware(AuthMiddleware)

        with patch.dict(os.environ, {"REQUIRE_API_KEY": "1", "API_KEY": "test-key"}):
            client = TestClient(app)
            response = client.get("/api/protected")
            assert response.status_code == 401

    def test_require_api_key_0_disables_auth(self):
        """REQUIRE_API_KEY=0 should disable authentication."""
        app = create_test_app()
        app.add_middleware(AuthMiddleware)

        with patch.dict(os.environ, {"REQUIRE_API_KEY": "0", "API_KEY": "test-key"}):
            client = TestClient(app)
            response = client.get("/api/protected")
            assert response.status_code == 200


class TestTimingAttackPrevention:
    """Test that timing attacks are prevented."""

    def test_timing_attack_prevention(self):
        """Verify that secrets.compare_digest is used for key comparison."""
        # This test verifies the implementation uses secrets.compare_digest
        # by checking the code structure

        # The actual comparison is in dispatch method
        dispatch_source = inspect.getsource(AuthMiddleware.dispatch)

        # Verify secrets.compare_digest is used
        assert "secrets.compare_digest" in dispatch_source, \
            "AuthMiddleware should use secrets.compare_digest for timing-safe comparison"


class TestConfigFileIntegration:
    """Test integration with config file."""

    def test_config_file_api_key_used(self):
        """API key from config file should be used when env var not set."""
        app = create_test_app()
        app.add_middleware(AuthMiddleware)

        mock_config = MagicMock()
        mock_security = MagicMock()
        mock_security.api_key = "config-api-key"
        mock_security.require_api_key = True
        mock_config.security = mock_security

        with patch.dict(os.environ, {}, clear=True):
            with patch("app.core.auth_middleware.get_config_service") as mock_get_config:
                mock_service = MagicMock()
                mock_service.get_config.return_value = mock_config
                mock_get_config.return_value = mock_service

                client = TestClient(app)
                response = client.get(
                    "/api/protected",
                    headers={"X-API-Key": "config-api-key"}
                )
                assert response.status_code == 200

    def test_configured_proxy_base_url_allows_emby_paths_on_non_default_port(self):
        """Configured proxy_base_url should mark matching Emby paths as public."""
        app = create_test_app()

        @app.get("/emby/system/info/public")
        async def emby_public():
            return {"ok": True}

        app.add_middleware(AuthMiddleware)

        mock_config = MagicMock()
        mock_security = MagicMock()
        mock_security.api_key = "config-api-key"
        mock_security.require_api_key = True
        mock_emby = MagicMock()
        mock_emby.proxy_base_url = "http://proxy.example:19097"
        mock_config.security = mock_security
        mock_config.emby = mock_emby

        with patch.dict(os.environ, {}, clear=True):
            with patch("app.core.auth_middleware.get_config_service") as mock_get_config:
                mock_service = MagicMock()
                mock_service.get_config.return_value = mock_config
                mock_get_config.return_value = mock_service

                client = TestClient(app)
                response = client.get(
                    "/emby/system/info/public",
                    headers={"host": "proxy.example:19097"}
                )
                assert response.status_code == 200
                assert response.json() == {"ok": True}
