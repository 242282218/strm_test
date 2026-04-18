from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import urlparse

from app.core.logging import get_logger
from app.services.config_service import get_config_service


if TYPE_CHECKING:
    from fastapi import Request


logger = get_logger(__name__)

DEDICATED_EMBY_PROXY_PORT = 18097
_EMBY_PROXY_PREFIXES = (
    "/emby",
    "/items",
    "/users",
    "/videos",
    "/audio",
    "/system",
    "/sessions",
    "/embywebsocket",
)


def parse_host_port(url_or_host: str, scheme_hint: str = "http") -> tuple[str, int]:
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


def request_host_port(request: Request) -> tuple[str, int]:
    host_header = (request.headers.get("host") or "").strip()
    if host_header:
        host, port = parse_host_port(host_header, request.url.scheme)
        if host:
            return host, port

    if request.url.hostname:
        host = request.url.hostname.lower()
        if request.url.port:
            return host, request.url.port
        return host, 443 if request.url.scheme == "https" else 80

    return "", 0


def is_emby_proxy_path(path: str) -> bool:
    normalized = (path or "").strip() or "/"
    if normalized == "/":
        return True

    lowered = normalized.lower()
    if lowered.startswith(_EMBY_PROXY_PREFIXES):
        return True

    api_emby_prefixes = tuple(f"/api/emby{prefix}" for prefix in _EMBY_PROXY_PREFIXES if prefix != "/emby")
    return lowered.startswith(api_emby_prefixes)


def is_dedicated_emby_proxy_request(request: Request) -> bool:
    if not is_emby_proxy_path(request.url.path):
        return False

    req_host, req_port = request_host_port(request)
    if not req_host:
        return False

    if req_port == DEDICATED_EMBY_PROXY_PORT:
        return True

    try:
        cfg = get_config_service().get_config()
        emby_cfg = getattr(cfg, "emby", None)
        configured_proxy = (getattr(emby_cfg, "proxy_base_url", "") or "").strip()
        if not configured_proxy:
            return False

        proxy_host, proxy_port = parse_host_port(configured_proxy, request.url.scheme)
    except Exception as exc:
        logger.debug("Failed to resolve dedicated emby proxy config: %s", exc)
        return False
    return req_host == proxy_host and req_port == proxy_port
