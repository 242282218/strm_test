"""
Security Headers Middleware

Provides comprehensive security headers to protect against common web attacks:
- Content-Security-Policy (CSP): Prevents XSS and data injection attacks
- X-Frame-Options: Prevents clickjacking attacks
- X-Content-Type-Options: Prevents MIME type sniffing
- Strict-Transport-Security (HSTS): Enforces HTTPS connections
- X-XSS-Protection: Enables browser XSS filter
- Referrer-Policy: Controls referrer information
- Permissions-Policy: Restricts sensitive browser features

Reference: OWASP Secure Headers Project
"""

from __future__ import annotations

import os
from collections.abc import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.emby_proxy_request import is_dedicated_emby_proxy_request as _is_dedicated_emby_proxy_request
from app.core.logging import get_logger


logger = get_logger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware that adds security headers to all HTTP responses.

    Configuration via environment variables:
    - SECURITY_HEADERS_ENABLED: Enable/disable security headers (default: true)
    - CSP_REPORT_URI: URI for CSP violation reports
    - HSTS_MAX_AGE: HSTS max-age in seconds (default: 31536000 = 1 year)
    - HSTS_INCLUDE_SUBDOMAINS: Include subdomains in HSTS (default: true)
    """

    # Paths that need relaxed CSP (Swagger UI, ReDoc, etc.)
    DOCUMENTATION_PATHS: set[str] = {
        "/docs",
        "/redoc",
        "/openapi.json",
    }

    # Default CSP directives for API responses
    DEFAULT_CSP: str = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https:; "
        "font-src 'self'; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    )

    # Relaxed CSP for documentation pages (Swagger UI needs inline scripts)
    DOCUMENTATION_CSP: str = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https:; "
        "font-src 'self'; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'"
    )

    # Permissions Policy - disable sensitive features
    PERMISSIONS_POLICY: str = (
        "accelerometer=(), camera=(), geolocation=(), gyroscope=(), magnetometer=(), microphone=(), payment=(), usb=()"
    )

    def __init__(self, app, **kwargs):
        super().__init__(app, **kwargs)
        self._enabled = self._get_enabled()
        self._hsts_max_age = self._get_hsts_max_age()
        self._hsts_include_subdomains = self._get_hsts_include_subdomains()
        self._csp_report_uri = self._get_csp_report_uri()
        self._is_production = self._detect_production()

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process each request and add security headers to response.

        Args:
            request: The incoming HTTP request
            call_next: The next middleware or route handler

        Returns:
            Response with security headers added
        """
        response = await call_next(request)

        # Skip if security headers are disabled
        if not self._enabled:
            return response

        # Dedicated Emby proxy traffic should stay transparent and preserve
        # upstream frontend behavior (e.g. inline bootstrap scripts).
        if _is_dedicated_emby_proxy_request(request):
            return response

        path = request.url.path

        # Add security headers
        self._add_security_headers(response, path, request)

        return response

    def _add_security_headers(self, response: Response, path: str, request: Request) -> None:
        """
        Add all security headers to the response.

        Args:
            response: The HTTP response to modify
            path: The request path
            request: The HTTP request
        """
        # X-Frame-Options: Prevents clickjacking
        # DENY: Completely prevents framing
        # SAMEORIGIN: Allows framing from same origin
        response.headers["X-Frame-Options"] = "DENY"

        # X-Content-Type-Options: Prevents MIME sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # X-XSS-Protection: Enables browser XSS filter (deprecated but still useful for older browsers)
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Referrer-Policy: Controls referrer information
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Permissions-Policy: Restricts sensitive browser features
        response.headers["Permissions-Policy"] = self.PERMISSIONS_POLICY

        # Strict-Transport-Security: Enforces HTTPS (only in production/HTTPS)
        if self._should_add_hsts(request):
            hsts_value = f"max-age={self._hsts_max_age}"
            if self._hsts_include_subdomains:
                hsts_value += "; includeSubDomains"
            response.headers["Strict-Transport-Security"] = hsts_value

        # Content-Security-Policy: Prevents XSS and data injection
        csp = self._get_csp_for_path(path)
        if csp:
            response.headers["Content-Security-Policy"] = csp

    def _get_csp_for_path(self, path: str) -> str:
        """
        Get appropriate CSP for the given path.

        Args:
            path: The request path

        Returns:
            CSP string for the path
        """
        # Use relaxed CSP for documentation pages
        if path in self.DOCUMENTATION_PATHS:
            csp = self.DOCUMENTATION_CSP
        else:
            csp = self.DEFAULT_CSP

        # Add report-uri if configured
        if self._csp_report_uri:
            csp += f"; report-uri {self._csp_report_uri}"

        return csp

    def _should_add_hsts(self, request: Request) -> bool:
        """
        Determine if HSTS header should be added.

        HSTS should only be added when:
        1. The request is over HTTPS
        2. Or we're in production mode

        Args:
            request: The HTTP request

        Returns:
            True if HSTS should be added
        """
        # Check if request is HTTPS
        is_https = request.url.scheme == "https" or request.headers.get("x-forwarded-proto", "").lower() == "https"

        # Add HSTS for HTTPS or production
        return is_https or self._is_production

    def _get_enabled(self) -> bool:
        """Check if security headers are enabled."""
        env_value = os.getenv("SECURITY_HEADERS_ENABLED", "true").lower()
        return env_value in ("true", "1", "yes")

    def _get_hsts_max_age(self) -> int:
        """Get HSTS max-age from environment."""
        try:
            return int(os.getenv("HSTS_MAX_AGE", "31536000"))
        except ValueError:
            return 31536000  # Default: 1 year

    def _get_hsts_include_subdomains(self) -> bool:
        """Check if HSTS should include subdomains."""
        env_value = os.getenv("HSTS_INCLUDE_SUBDOMAINS", "true").lower()
        return env_value in ("true", "1", "yes")

    def _get_csp_report_uri(self) -> str | None:
        """Get CSP report URI from environment."""
        return os.getenv("CSP_REPORT_URI")

    def _detect_production(self) -> bool:
        """
        Detect if running in production mode.

        Returns:
            True if production mode is detected
        """
        # Check common production environment indicators
        env = os.getenv("ENVIRONMENT", "").lower()
        if env in ("production", "prod"):
            return True

        # Check for production-specific settings
        debug = os.getenv("DEBUG", "").lower()
        if debug in ("false", "0", "no"):
            return True

        return False


class CSPReportOnlyMiddleware(BaseHTTPMiddleware):
    """
    CSP Report-Only mode middleware.

    Use this middleware to test CSP policies without breaking functionality.
    Violations are reported but not enforced.

    Enable by setting CSP_REPORT_ONLY=true
    """

    def __init__(self, app, **kwargs):
        super().__init__(app, **kwargs)
        self._csp = SecurityHeadersMiddleware.DEFAULT_CSP
        report_uri = os.getenv("CSP_REPORT_URI")
        if report_uri:
            self._csp += f"; report-uri {report_uri}"

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Add CSP header in report-only mode."""
        response = await call_next(request)

        # Only add for non-documentation paths
        if request.url.path not in SecurityHeadersMiddleware.DOCUMENTATION_PATHS:
            response.headers["Content-Security-Policy-Report-Only"] = self._csp

        return response


def get_security_headers_middleware():
    """
    Factory function to get the appropriate security headers middleware.

    Returns CSPReportOnlyMiddleware if CSP_REPORT_ONLY=true,
    otherwise returns SecurityHeadersMiddleware.

    Returns:
        Middleware class
    """
    report_only = os.getenv("CSP_REPORT_ONLY", "false").lower()
    if report_only in ("true", "1", "yes"):
        logger.info("CSP running in report-only mode")
        return CSPReportOnlyMiddleware
    return SecurityHeadersMiddleware
