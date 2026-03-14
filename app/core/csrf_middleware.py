"""
CSRF protection middleware.

Implements the Double Submit Cookie pattern:
1. Server generates/stores a CSRF token in cookie.
2. Frontend reads cookie and sends token via request header.
3. Server validates cookie token == header token.
"""

from __future__ import annotations

import os
import secrets
from urllib.parse import urlparse

from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from app.core.logging import get_logger
from app.services.config_service import get_config_service


logger = get_logger(__name__)

# CSRF token cookie/header names
CSRF_COOKIE_NAME = "csrf_token"
CSRF_HEADER_NAME = "X-CSRF-Token"

# Paths that do not require CSRF validation
CSRF_EXEMPT_PATHS = {
    "/api/auth/login",
    "/api/auth/verify",
    "/api/auth/status",
    "/health",
    "/metrics",
    "/",
}

# Safe methods do not require CSRF validation
CSRF_SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}

# Dedicated Emby proxy default port
DEDICATED_PROXY_PORT = 18097


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


def _is_dedicated_emby_proxy_request(request: Request) -> bool:
    req_host, req_port = _request_host_port(request)
    if not req_host:
        return False

    # Fallback: dedicated proxy default port.
    if req_port == DEDICATED_PROXY_PORT:
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
        logger.debug(f"Failed to resolve dedicated emby proxy config for CSRF check: {exc}")
        return False


class CSRFMiddleware(BaseHTTPMiddleware):
    """
    CSRF middleware based on Double Submit Cookie.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        csrf_token = self._get_or_create_csrf_token(request)

        if self._requires_csrf_validation(request):
            if not self._validate_csrf_token(request, csrf_token):
                logger.warning(
                    f"CSRF validation failed for {request.method} {request.url.path}",
                    extra={
                        "path": request.url.path,
                        "method": request.method,
                        "client_ip": self._get_client_ip(request),
                    },
                )
                response = JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={"detail": "CSRF token validation failed"},
                )
                if not request.cookies.get(CSRF_COOKIE_NAME):
                    self._set_csrf_cookie(response, csrf_token)
                return response

        response = await call_next(request)

        # Dedicated Emby proxy traffic should remain transparent and avoid
        # injecting smart_media-specific cookies into upstream responses.
        if _is_dedicated_emby_proxy_request(request):
            return response

        if not request.cookies.get(CSRF_COOKIE_NAME):
            self._set_csrf_cookie(response, csrf_token)

        return response

    def _get_or_create_csrf_token(self, request: Request) -> str:
        existing_token = request.cookies.get(CSRF_COOKIE_NAME)
        if existing_token:
            return existing_token
        return secrets.token_hex(32)

    def _requires_csrf_validation(self, request: Request) -> bool:
        # Dedicated Emby proxy traffic should behave like transparent reverse proxy.
        if _is_dedicated_emby_proxy_request(request):
            return False

        if request.method in CSRF_SAFE_METHODS:
            return False

        path = request.url.path
        if path in CSRF_EXEMPT_PATHS:
            return False

        return True

    def _validate_csrf_token(self, request: Request, expected_token: str) -> bool:
        header_token = request.headers.get(CSRF_HEADER_NAME)

        if not header_token:
            logger.debug(f"Missing CSRF token in header for {request.method} {request.url.path}")
            return False

        if not secrets.compare_digest(header_token, expected_token):
            logger.debug(f"CSRF token mismatch for {request.method} {request.url.path}")
            return False

        return True

    def _set_csrf_cookie(self, response: Response, token: str) -> None:
        secure = os.getenv("COOKIE_SECURE", "true").lower() not in ("false", "0", "no")

        response.set_cookie(
            key=CSRF_COOKIE_NAME,
            value=token,
            httponly=False,
            secure=secure,
            samesite="lax",
            max_age=60 * 60 * 24 * 365,  # 1 year
            path="/",
        )

    def _get_client_ip(self, request: Request) -> str:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"


def get_csrf_token_from_request(request: Request) -> str | None:
    """Extract CSRF token from request cookies."""
    return request.cookies.get(CSRF_COOKIE_NAME)


async def verify_csrf_token(request: Request) -> str:
    """Dependency function to verify CSRF token manually in routes."""
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
    header_token = request.headers.get(CSRF_HEADER_NAME)

    if not cookie_token or not header_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF token missing")

    if not secrets.compare_digest(cookie_token, header_token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF token validation failed")

    return cookie_token
