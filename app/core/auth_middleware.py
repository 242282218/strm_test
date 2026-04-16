"""
API Authentication Middleware

Provides centralized authentication protection for all API endpoints.
Supports X-API-Key header, Bearer Token authorization, and JWT authentication.
Uses secrets.compare_digest to prevent timing attacks.
"""

from __future__ import annotations

import os
import secrets
from collections.abc import Callable
from urllib.parse import urlparse

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.auth_contract import resolve_expected_api_key
from app.core.logging import get_logger
from app.services.config_service import get_config_service


logger = get_logger(__name__)

# Dedicated Emby proxy default port
_DEDICATED_PROXY_PORT = 18097


def _parse_host_port(url_or_host: str, scheme_hint: str = "http") -> tuple[str, int]:
    text = (url_or_host or "").strip()
    if not text:
        return "", 0
    if "://" not in text:
        text = f"{scheme_hint}://{text}"
    parsed = urlparse(text)
    host = (parsed.hostname or "").lower()
    if not host:
        return "", 0
    if parsed.port:
        return host, parsed.port
    return host, 443 if parsed.scheme == "https" else 80


def _request_host_port(request: Request) -> tuple[str, int]:
    host_header = (request.headers.get("host") or "").strip()
    if host_header:
        host, port = _parse_host_port(host_header, request.url.scheme)
        if host:
            return host, port
    if request.url.hostname:
        host = request.url.hostname.lower()
        if request.url.port:
            return host, request.url.port
        return host, 443 if request.url.scheme == "https" else 80
    return "", 0


def _is_emby_proxy_path(path: str) -> bool:
    normalized = (path or "").strip() or "/"
    if normalized == "/":
        return True

    lowered = normalized.lower()
    allowed_prefixes = (
        "/emby",
        "/items",
        "/users",
        "/videos",
        "/audio",
        "/system",
        "/sessions",
        "/embywebsocket",
    )
    if lowered.startswith(allowed_prefixes):
        return True

    api_emby_prefixes = tuple(f"/api/emby{prefix}" for prefix in allowed_prefixes if prefix != "/emby")
    return lowered.startswith(api_emby_prefixes)



def _is_dedicated_emby_proxy_request(request: Request) -> bool:
    """Detect whether this request arrives via the dedicated Emby proxy entrance."""
    if not _is_emby_proxy_path(request.url.path):
        return False

    req_host, req_port = _request_host_port(request)
    if not req_host:
        return False

    # Fallback: dedicated proxy default port.
    if req_port == _DEDICATED_PROXY_PORT:
        return True

    try:
        cfg = get_config_service().get_config()
        emby_cfg = getattr(cfg, "emby", None)
        configured_proxy = (getattr(emby_cfg, "proxy_base_url", "") or "").strip()
        if not configured_proxy:
            return False
        proxy_host, proxy_port = _parse_host_port(configured_proxy, request.url.scheme)
        return req_host == proxy_host and req_port == proxy_port
    except Exception as exc:
        logger.debug(f"Failed to resolve dedicated emby proxy config for auth check: {exc}")
        return False


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Centralized API authentication middleware.

    Protects all non-whitelisted endpoints with authentication validation.
    Supports multiple authentication methods:
    - X-API-Key header (legacy API key)
    - Authorization: Bearer <token> (JWT or API key)

    Configuration:
    - Environment variable REQUIRE_API_KEY: Enable/disable authentication
    - Environment variable SMART_MEDIA_SECURITY_API_KEY: canonical API key value
    - Environment variable SMART_MEDIA_API_KEY / API_KEY: legacy compatible aliases
    - Config file security.api_key and security.require_api_key
    """

    # Whitelisted paths that don't require authentication
    PUBLIC_PATHS: set[str] = {
        "/",
        "/health",
        "/health/live",
        "/health/ready",
        "/ready",
        "/docs",
        "/redoc",
        "/openapi.json",
    }

    # Path prefixes that don't require authentication
    PUBLIC_PREFIXES: set[str] = {
        "/static/",
        "/web/",
        "/api/proxy/stream/",
        "/api/proxy/redirect/",
        "/api/proxy/transcoding/",
    }

    # Auth API paths - always public
    AUTH_PUBLIC_PATHS: set[str] = {
        "/api/auth/login",
        "/api/auth/refresh",
        "/api/auth/status",
        "/api/auth/verify",
    }

    def __init__(self, app, **kwargs):
        super().__init__(app, **kwargs)
        self._cached_api_key: str | None = None
        self._cached_require_auth: bool | None = None

    def _extract_api_key(self, request: Request) -> str | None:
        """
        Extract API key from headers or cookies with constant-time friendly trimming.

        Returns:
            API key string or None if missing
        """
        # Explicit request headers should override ambient cookies so callers can
        # recover from stale browser state and intentionally switch credentials.
        x_api_key = request.headers.get("X-API-Key")
        if x_api_key:
            return x_api_key.strip()

        # Authorization: Bearer <token>
        authorization = request.headers.get("Authorization")
        if authorization:
            parts = authorization.split()
            if len(parts) == 2 and parts[0].lower() == "bearer":
                return parts[1].strip()

        # Fall back to cookie (HttpOnly)
        auth_cookie = request.cookies.get("auth_token")
        if auth_cookie:
            return auth_cookie.strip()

        return None

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process each request and validate authentication if required.

        Args:
            request: The incoming HTTP request
            call_next: The next middleware or route handler

        Returns:
            Response from the next handler or 401/403 error response
        """
        path = request.url.path

        # Check if path is whitelisted
        if self._is_public_path(request):
            return await call_next(request)

        # Check if authentication is required
        if not self._is_auth_required():
            return await call_next(request)

        # Extract token from request
        provided_token = self._extract_token(request)
        if not provided_token:
            logger.warning(
                f"Authentication failed: missing token for {path}", extra={"path": path, "method": request.method}
            )
            # 记录未授权访问尝试
            await self._record_unauthorized_access(request, "missing_token")
            return self._create_unauthorized_response("API key is required")

        # Try JWT authentication first
        if await self._validate_jwt_token(provided_token):
            return await call_next(request)

        # Fall back to API key validation
        expected_key = self._get_expected_api_key()
        if expected_key and secrets.compare_digest(provided_token, expected_key):
            return await call_next(request)

        # All authentication methods failed
        logger.warning(
            f"Authentication failed: invalid token for {path}", extra={"path": path, "method": request.method}
        )
        # 记录未授权访问尝试
        await self._record_unauthorized_access(request, "invalid_token")
        return self._create_forbidden_response("Invalid API key")

    def _is_public_path(self, request: Request) -> bool:
        """
        Check if the path is in the public whitelist.

        Args:
            request: The incoming request

        Returns:
            True if path is whitelisted, False otherwise
        """
        # Dedicated Emby proxy traffic uses Emby's own authentication;
        # smart_media auth must not interfere.
        if _is_dedicated_emby_proxy_request(request):
            return True

        path = request.url.path

        # Check exact match for public paths
        if path in self.PUBLIC_PATHS:
            return True

        # Check auth public paths (login, refresh, etc.)
        if path in self.AUTH_PUBLIC_PATHS:
            return True

        # Check prefix match
        for prefix in self.PUBLIC_PREFIXES:
            if path.startswith(prefix):
                return True

        if path == "/api/auth/init-admin" and self._can_bootstrap_init_admin(request):
            return True

        return False

    def _can_bootstrap_init_admin(self, request: Request) -> bool:
        """Allow one-time admin bootstrap only from a trusted local request."""
        if self._admin_exists():
            return False

        client_host = request.client.host if request.client else ""
        return client_host in {"127.0.0.1", "::1", "localhost"}

    def _admin_exists(self) -> bool:
        """Check whether the system already has an admin user."""
        try:
            from app.core.db import SessionLocal
            from app.models.user import User

            db = SessionLocal()
            try:
                return User.has_admin(db)
            finally:
                db.close()
        except Exception as exc:
            logger.warning(f"Failed to check admin existence: {exc}")
            return True

    def _is_auth_required(self) -> bool:
        """
        Check if authentication is required based on configuration.

        Returns:
            True if authentication is required, False otherwise
        """
        # Check environment variable first (highest priority)
        env_require = os.getenv("REQUIRE_API_KEY", "").lower()
        if env_require in ("true", "1", "yes"):
            return True
        if env_require in ("false", "0", "no"):
            return False

        # Check config file
        try:
            cfg = get_config_service().get_config()
            security = getattr(cfg, "security", None)
            if security:
                return bool(security.require_api_key)
        except Exception as exc:
            logger.warning(f"Failed to read security config: {exc}")

        # Default: require authentication if API key is configured
        return self._get_expected_api_key() is not None

    def _get_expected_api_key(self) -> str | None:
        """
        Get the expected API key from configuration.

        Priority:
        1. SMART_MEDIA_SECURITY_API_KEY environment variable
        2. SMART_MEDIA_API_KEY / API_KEY legacy environment aliases
        3. Config file security.api_key

        Returns:
            The expected API key or None if not configured
        """
        return resolve_expected_api_key(self._get_config_api_key)

    def _get_config_api_key(self) -> str | None:
        """Read the configured API key from config service."""
        try:
            cfg = get_config_service().get_config()
            security = getattr(cfg, "security", None)
            if security and security.api_key:
                return security.api_key
        except Exception as exc:
            logger.warning(f"Failed to read API key from config: {exc}")
        return None

    def _extract_token(self, request: Request) -> str | None:
        """
        Extract authentication token from request headers or cookies.

        Supports:
        - Cookie: auth_token (HttpOnly Cookie - preferred)
        - X-API-Key header
        - Authorization: Bearer <token>

        Returns:
            The extracted token or None if not found
        """
        return self._extract_api_key(request)

    async def _validate_jwt_token(self, token: str) -> bool:
        """
        Validate JWT token.

        Args:
            token: JWT token string

        Returns:
            True if valid, False otherwise
        """
        try:
            from app.services.auth_service import AuthService

            user_id = AuthService.verify_access_token(token)
            if not user_id:
                return False

            # Verify user exists and is active
            from app.core.db import SessionLocal
            from app.models.user import User

            db = SessionLocal()
            try:
                user = User.get_by_id(db, user_id)
                return user is not None and user.is_active
            finally:
                db.close()

        except Exception as e:
            logger.debug(f"JWT validation failed: {e}")
            return False

    def _create_unauthorized_response(self, message: str) -> JSONResponse:
        """Create a 401 Unauthorized response."""
        return JSONResponse(
            status_code=401,
            content={"detail": message},
        )

    def _create_forbidden_response(self, message: str) -> JSONResponse:
        """Create a 403 Forbidden response."""
        return JSONResponse(
            status_code=403,
            content={"detail": message},
        )

    def _create_error_response(self, status_code: int, message: str) -> JSONResponse:
        """Create an error response with the given status code."""
        return JSONResponse(
            status_code=status_code,
            content={"detail": message},
        )

    async def _record_unauthorized_access(self, request: Request, reason: str) -> None:
        """
        记录未授权访问尝试

        Args:
            request: HTTP 请求对象
            reason: 失败原因
        """
        try:
            from app.core.db import SessionLocal
            from app.services.security_audit_service import get_security_audit_service

            security_audit = get_security_audit_service()
            db = SessionLocal()

            try:
                # 获取客户端信息
                ip_address = self._get_client_ip(request)
                user_agent = request.headers.get("user-agent", "")
                path = request.url.path
                method = request.method

                security_audit.record_unauthorized_access(
                    db=db,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    request_path=path,
                    request_method=method,
                )
            finally:
                db.close()

        except Exception as e:
            logger.error(f"Failed to record unauthorized access: {e}")

    def _get_client_ip(self, request: Request) -> str:
        """
        获取客户端真实 IP 地址

        Args:
            request: HTTP 请求对象

        Returns:
            客户端 IP 地址
        """
        # 检查代理头
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            # 取第一个 IP
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip

        # 直接连接
        if request.client:
            return request.client.host

        return "unknown"
