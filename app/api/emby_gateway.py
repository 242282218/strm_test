"""
Dedicated Emby gateway routes.

When requests hit the configured Emby proxy entrance (for example :18097),
this router forwards normal Emby UI/API traffic to the real Emby server and
intercepts PlaybackInfo for STRM hook processing.
"""

from __future__ import annotations

import asyncio
import re
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, Response

from app.core.config_manager import get_config
from app.core.http_pool import ClientType, get_http_pool_sync
from app.core.logging import get_logger
from app.core.validators import validate_http_url, validate_identifier
from app.services.config_service import get_config_service
from app.services.emby_proxy_service import EmbyProxyService


logger = get_logger(__name__)
router = APIRouter(tags=["EmbyGateway"])

config = get_config()
config_service = get_config_service()

_PLAYBACKINFO_RE = re.compile(r"^(?:emby/)?Items/(?P<item_id>[^/]+)/PlaybackInfo/?$", re.IGNORECASE)
_HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}
_FORWARDED_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]
_NO_BODY_METHODS = {"GET", "HEAD", "OPTIONS"}
_forward_pool = None
_forward_client: httpx.AsyncClient | None = None
_forward_client_lock = asyncio.Lock()


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


def _is_dedicated_proxy_request(request: Request, app_config) -> bool:
    req_host, req_port = _request_host_port(request)
    if not req_host:
        return False

    configured_proxy = (getattr(app_config.emby, "proxy_base_url", "") or "").strip()
    if configured_proxy:
        proxy_host, proxy_port = _parse_host_port(configured_proxy, request.url.scheme)
        return req_host == proxy_host and req_port == proxy_port

    # Fallback: default dedicated proxy port
    return req_port == 18097


def _resolve_emby_base_url(app_config) -> str:
    emby_base_url = (getattr(app_config.emby, "url", "") or "").strip()
    if not emby_base_url and getattr(app_config, "endpoints", None):
        first = app_config.endpoints[0]
        emby_base_url = (getattr(first, "emby_url", "") or "").strip()
    if not emby_base_url:
        emby_base_url = "http://localhost:8096"

    validate_http_url(emby_base_url, "emby_base_url")
    return emby_base_url.rstrip("/")


def _resolve_proxy_base_url(app_config, request: Request) -> str:
    configured_proxy = (getattr(app_config.emby, "proxy_base_url", "") or "").strip()
    if configured_proxy:
        validate_http_url(configured_proxy, "proxy_base_url")
        return configured_proxy.rstrip("/")
    return str(request.base_url).rstrip("/")


def _rewrite_location(location: str, emby_base_url: str, request: Request) -> str:
    if not location:
        return location

    proxy_base_url = str(request.base_url).rstrip("/")
    normalized_emby = emby_base_url.rstrip("/")
    if location.startswith(normalized_emby):
        return f"{proxy_base_url}{location[len(normalized_emby):]}"
    return location


def _build_forward_headers(request: Request) -> dict[str, str]:
    headers: dict[str, str] = {}
    for key, value in request.headers.items():
        lowered = key.lower()
        if lowered == "host" or lowered in _HOP_BY_HOP_HEADERS:
            continue
        # Avoid upstream compression ambiguity. httpx may decode compressed
        # payloads while preserving upstream headers, which can break clients.
        if lowered == "accept-encoding":
            continue
        headers[key] = value
    headers["Accept-Encoding"] = "identity"
    return headers


def _build_response_headers(upstream_headers: httpx.Headers, emby_base_url: str, request: Request) -> dict[str, str]:
    headers: dict[str, str] = {}
    # Let Starlette/Uvicorn recalculate framing/date/server headers for proxied responses.
    # Forwarding upstream content-length with middleware transforms (e.g. gzip) can cause
    # "Response content longer than Content-Length" runtime errors.
    # Content-Encoding is also stripped to avoid decode/encode mismatches.
    # Set-Cookie is appended separately so duplicate cookies are preserved.
    filtered_headers = {"content-length", "content-encoding", "date", "server", "set-cookie"}
    for key, value in upstream_headers.items():
        lowered = key.lower()
        if lowered in _HOP_BY_HOP_HEADERS or lowered in filtered_headers:
            continue
        if lowered == "location":
            headers[key] = _rewrite_location(value, emby_base_url, request)
            continue
        headers[key] = value
    return headers


async def _get_forward_client() -> httpx.AsyncClient:
    global _forward_pool, _forward_client

    if _forward_client is not None and not _forward_client.is_closed:
        return _forward_client

    async with _forward_client_lock:
        if _forward_client is not None and not _forward_client.is_closed:
            return _forward_client

        if _forward_pool is None:
            _forward_pool = get_http_pool_sync()
        _forward_client = await _forward_pool.get_client(ClientType.EMBY)
        return _forward_client


async def _proxy_playback_info(request: Request, app_config, item_id: str) -> Response:
    user_id = request.query_params.get("UserId") or request.query_params.get("user_id") or ""
    media_source_id = request.query_params.get("MediaSourceId") or request.query_params.get("media_source_id")
    api_key = (
        request.query_params.get("api_key")
        or request.headers.get("X-Emby-Token")
        or request.headers.get("X-MediaBrowser-Token")
        or (getattr(app_config.emby, "api_key", "") or "")
    )
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing API key")

    cookie = config.get_quark_cookie()
    if not cookie:
        raise HTTPException(status_code=400, detail="Cookie not configured")

    emby_base_url = _resolve_emby_base_url(app_config)
    proxy_base_url = _resolve_proxy_base_url(app_config, request)

    async with EmbyProxyService(
        emby_base_url=emby_base_url,
        api_key=api_key,
        cookie=cookie,
        proxy_base_url=proxy_base_url,
    ) as proxy_service:
        data = await proxy_service.proxy_playback_info(
            item_id=item_id,
            user_id=user_id,
            media_source_id=media_source_id,
        )
    return JSONResponse(content=data)


async def _forward_to_emby(request: Request, app_config, path: str) -> Response:
    emby_base_url = _resolve_emby_base_url(app_config)
    target_path = (path or "").lstrip("/")
    target_url = emby_base_url if not target_path else f"{emby_base_url}/{target_path}"
    query_string = str(request.url.query)
    if query_string:
        target_url = f"{target_url}?{query_string}"

    body = None
    if request.method.upper() not in _NO_BODY_METHODS:
        body = await request.body()
    headers = _build_forward_headers(request)
    client = await _get_forward_client()
    upstream = await client.request(
        method=request.method,
        url=target_url,
        headers=headers,
        content=body,
        follow_redirects=False,
        timeout=30.0,
    )

    response_headers = _build_response_headers(upstream.headers, emby_base_url, request)
    media_type = upstream.headers.get("content-type")
    response = Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers=response_headers,
        media_type=media_type,
    )
    for cookie in upstream.headers.get_list("set-cookie"):
        response.headers.append("set-cookie", cookie)
    return response


async def _handle_gateway_request(request: Request, path: str) -> Response:
    app_config = config_service.get_config()
    if not _is_dedicated_proxy_request(request, app_config):
        raise HTTPException(status_code=404, detail="Not Found")

    path = (path or "").lstrip("/")
    if request.method == "GET":
        matched = _PLAYBACKINFO_RE.match(path)
        if matched:
            item_id = validate_identifier(matched.group("item_id"), "item_id")
            return await _proxy_playback_info(request, app_config, item_id)

    return await _forward_to_emby(request, app_config, path)


@router.api_route("/", methods=_FORWARDED_METHODS, include_in_schema=False)
async def emby_gateway_root(request: Request):
    return await _handle_gateway_request(request, "")


@router.api_route("/{path:path}", methods=_FORWARDED_METHODS, include_in_schema=False)
async def emby_gateway(request: Request, path: str):
    return await _handle_gateway_request(request, path)
