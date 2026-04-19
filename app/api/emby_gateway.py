"""
Dedicated Emby gateway routes.

When requests hit the configured Emby proxy entrance (for example :18097),
this router forwards normal Emby UI/API traffic to the real Emby server and
intercepts PlaybackInfo for STRM hook processing.
WebSocket connections (e.g. /embywebsocket) are transparently proxied.
"""

from __future__ import annotations

import asyncio
import re
from urllib.parse import urlparse

import httpx
import websockets
from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, Response
from starlette.requests import HTTPConnection

from app.api.emby import (
    _is_web_client_request,
    _read_playback_request_payload,
    _resolve_emby_authorization_context,
    _resolve_playback_request_field,
    _resolve_requested_emby_api_key,
    _resolve_requested_emby_base_url,
    _resolve_requested_client_name,
    _resolve_requested_device_name,
    _resolve_requested_proxy_base_url,
    _normalize_proxy_base_url_candidate,
    get_master_playlist,
    stream_video,
)
from app.services.playbackinfo_hook import (
    LOCAL_PLAYBACK_PROXY_QUERY_KEY,
    LOCAL_PLAYBACK_PROXY_QUERY_VALUE,
)

from app.core.config_manager import get_config
from app.core.http_pool import ClientType, get_http_pool_sync
from app.core.logging import get_logger
from app.core.validators import validate_identifier
from app.services.config_service import get_config_service
from app.services.emby_proxy_service import EmbyProxyService


logger = get_logger(__name__)
router = APIRouter(tags=["EmbyGateway"])

config = get_config()
config_service = get_config_service()

_PLAYBACKINFO_RE = re.compile(r"^(?:emby/)?Items/(?P<item_id>[^/]+)/PlaybackInfo/?$", re.IGNORECASE)
_VIDEOS_STREAM_RE = re.compile(
    r"^(?:emby/)?Videos/(?P<item_id>[^/]+)/stream(?:\.(?P<filename>[^/?]+))?/?$",
    re.IGNORECASE,
)
_VIDEOS_MASTER_RE = re.compile(r"^(?:emby/)?Videos/(?P<item_id>[^/]+)/master\.m3u8/?$", re.IGNORECASE)
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
_INTERNAL_PROXY_CONTROL_HEADERS = {
    "x-emby-server-url",
    "x-proxy-server-url",
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
    try:
        port = parsed.port
    except ValueError:
        return "", 0
    if port:
        return host, port
    return host, 443 if parsed.scheme == "https" else 80


def _request_host_port(connection: HTTPConnection) -> tuple[str, int]:
    host_header = (connection.headers.get("host") or "").strip()
    if host_header:
        host, port = _parse_host_port(host_header, connection.url.scheme)
        if host:
            return host, port
        return "", 0

    if connection.url.hostname:
        host = connection.url.hostname.lower()
        try:
            port = connection.url.port
        except ValueError:
            return "", 0
        if port:
            return host, port
        return host, 443 if connection.url.scheme == "https" else 80

    return "", 0


def _is_dedicated_proxy_request(connection: HTTPConnection, app_config) -> bool:
    req_host, req_port = _request_host_port(connection)
    if not req_host:
        return False

    configured_proxy = (getattr(app_config.emby, "proxy_base_url", "") or "").strip()
    if configured_proxy:
        proxy_host, proxy_port = _parse_host_port(configured_proxy, connection.url.scheme)
        return req_host == proxy_host and req_port == proxy_port

    # Fallback: default dedicated proxy port
    return req_port == 18097


def _resolve_emby_base_url(connection: HTTPConnection, app_config) -> str:
    return _resolve_requested_emby_base_url(connection, app_config).rstrip("/")


def _is_local_playback_proxy_request(request: Request) -> bool:
    return request.query_params.get(LOCAL_PLAYBACK_PROXY_QUERY_KEY) == LOCAL_PLAYBACK_PROXY_QUERY_VALUE


def _rewrite_location(location: str, emby_base_url: str, proxy_base_url: str) -> str:
    if not location:
        return location

    normalized_emby = emby_base_url.rstrip("/")
    if location.startswith(normalized_emby):
        return f"{proxy_base_url}{location[len(normalized_emby):]}"
    return location


def _build_forward_headers(request: Request) -> dict[str, str]:
    headers: dict[str, str] = {}
    for key, value in request.headers.items():
        lowered = key.lower()
        if lowered == "host" or lowered in _HOP_BY_HOP_HEADERS or lowered in _INTERNAL_PROXY_CONTROL_HEADERS:
            continue
        # Avoid upstream compression ambiguity. httpx may decode compressed
        # payloads while preserving upstream headers, which can break clients.
        if lowered == "accept-encoding":
            continue
        headers[key] = value
    headers["Accept-Encoding"] = "identity"
    return headers


def _build_response_headers(upstream_headers: httpx.Headers, emby_base_url: str, proxy_base_url: str) -> dict[str, str]:
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
            headers[key] = _rewrite_location(value, emby_base_url, proxy_base_url)
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
    playback_request = await _read_playback_request_payload(request)
    auth_context = _resolve_emby_authorization_context(request.headers)
    user_id = (
        request.query_params.get("UserId")
        or request.query_params.get("user_id")
        or _resolve_playback_request_field(playback_request, "UserId", "user_id")
        or auth_context.get("userid")
        or ""
    )
    media_source_id = (
        request.query_params.get("MediaSourceId")
        or request.query_params.get("media_source_id")
        or _resolve_playback_request_field(playback_request, "MediaSourceId", "media_source_id")
    )
    api_key = _resolve_requested_emby_api_key(request, app_config, auth_context)
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing API key")

    cookie = config.get_quark_cookie()
    if not cookie:
        raise HTTPException(status_code=400, detail="Cookie not configured")

    emby_base_url = _resolve_emby_base_url(request, app_config)
    proxy_base_url = _resolve_requested_proxy_base_url(request, app_config)
    client_name = _resolve_requested_client_name(request.headers, auth_context)
    device_name = _resolve_requested_device_name(request.headers, auth_context)
    user_agent = request.headers.get("User-Agent")
    is_web_client = _is_web_client_request(client_name, device_name, user_agent)

    async with EmbyProxyService(
        emby_base_url=emby_base_url,
        api_key=api_key,
        cookie=cookie,
        proxy_base_url=proxy_base_url,
    ) as proxy_service:
        playback_hook = proxy_service.playback_hook
        if playback_hook is None:
            raise RuntimeError("Playback hook not initialized")
        data = await playback_hook.hook_playback_info(
            item_id=item_id,
            user_id=user_id,
            media_source_id=media_source_id,
            is_web_client=is_web_client,
            client_name=client_name,
            device_name=device_name,
            playback_request=playback_request,
        )
    return JSONResponse(content=data)


def _raise_forward_http_exception(exc: httpx.RequestError, method: str, path: str) -> None:
    normalized_path = f"/{(path or '').lstrip('/')}" if path else "/"
    if isinstance(exc, httpx.TimeoutException):
        logger.warning(f"Emby upstream timeout during proxy forward: {method.upper()} {normalized_path}")
        raise HTTPException(status_code=504, detail="Emby upstream timeout") from exc

    logger.warning(f"Emby upstream request failed during proxy forward: {method.upper()} {normalized_path}")
    raise HTTPException(status_code=502, detail="Failed to proxy Emby request") from exc


async def _forward_to_emby(
    request: Request,
    app_config,
    path: str,
    *,
    emby_base_url: str | None = None,
    proxy_base_url: str | None = None,
) -> Response:
    emby_base_url = (emby_base_url or _resolve_emby_base_url(request, app_config)).rstrip("/")
    proxy_base_url = (proxy_base_url or _resolve_requested_proxy_base_url(request, app_config)).rstrip("/")
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
    try:
        upstream = await client.request(
            method=request.method,
            url=target_url,
            headers=headers,
            content=body,
            follow_redirects=False,
            timeout=30.0,
        )
    except httpx.RequestError as exc:
        _raise_forward_http_exception(exc, request.method, target_path)

    response_headers = _build_response_headers(upstream.headers, emby_base_url, proxy_base_url)
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


async def _handle_emby_style_stream(request: Request, item_id: str, filename: str | None = None) -> Response:
    media_source_id = request.query_params.get("MediaSourceId") or request.query_params.get("media_source_id")
    static = str(request.query_params.get("Static") or request.query_params.get("static") or "").lower() == "true"
    return await stream_video(
        item_id=item_id,
        request=request,
        media_source_id=media_source_id,
        static=static,
        filename=filename,
    )


async def _handle_emby_style_master_playlist(request: Request, item_id: str) -> Response:
    media_source_id = request.query_params.get("MediaSourceId") or request.query_params.get("media_source_id")
    return await get_master_playlist(
        item_id=item_id,
        request=request,
        media_source_id=media_source_id,
    )


async def _handle_gateway_request(request: Request, path: str) -> Response:
    app_config = config_service.get_config()
    if not _is_dedicated_proxy_request(request, app_config):
        raise HTTPException(status_code=404, detail="Not Found")

    path = (path or "").lstrip("/")
    if request.method in {"GET", "POST"}:
        matched = _PLAYBACKINFO_RE.match(path)
        if matched:
            item_id = validate_identifier(matched.group("item_id"), "item_id")
            return await _proxy_playback_info(request, app_config, item_id)

    if request.method in {"GET", "HEAD"} and _is_local_playback_proxy_request(request):
        stream_match = _VIDEOS_STREAM_RE.match(path)
        if stream_match:
            item_id = validate_identifier(stream_match.group("item_id"), "item_id")
            return await _handle_emby_style_stream(request, item_id, filename=stream_match.group("filename"))

    if request.method in {"GET", "HEAD"} and _is_local_playback_proxy_request(request):
        master_match = _VIDEOS_MASTER_RE.match(path)
        if master_match:
            item_id = validate_identifier(master_match.group("item_id"), "item_id")
            return await _handle_emby_style_master_playlist(request, item_id)

    emby_base_url = _resolve_emby_base_url(request, app_config)
    proxy_base_url = _resolve_requested_proxy_base_url(request, app_config)
    return await _forward_to_emby(
        request,
        app_config,
        path,
        emby_base_url=emby_base_url,
        proxy_base_url=proxy_base_url,
    )


# ------------------------------------------------------------------
# WebSocket proxy for /embywebsocket
# ------------------------------------------------------------------

_WS_FORWARD_HEADERS_SKIP = {"host", "connection", "upgrade", "sec-websocket-key",
                             "sec-websocket-version", "sec-websocket-extensions",
                             "sec-websocket-protocol"}


def _build_ws_target_url(app_config, client_ws: WebSocket) -> str:
    """Build the upstream Emby WebSocket URL from the incoming request."""
    emby_base_url = _resolve_emby_base_url(client_ws, app_config)
    # http(s) → ws(s)
    ws_base = emby_base_url.replace("https://", "wss://").replace("http://", "ws://")
    query_string = str(client_ws.url.query)
    path = "embywebsocket"
    if query_string:
        return f"{ws_base}/{path}?{query_string}"
    return f"{ws_base}/{path}"


def _build_ws_extra_headers(client_ws: WebSocket) -> list[tuple[str, str]]:
    """Forward non-hop-by-hop headers from the client to upstream."""
    extra: list[tuple[str, str]] = []
    for key, value in client_ws.headers.items():
        if key.lower() in _WS_FORWARD_HEADERS_SKIP or key.lower() in _INTERNAL_PROXY_CONTROL_HEADERS:
            continue
        extra.append((key, value))
    return extra


def _extract_ws_requested_subprotocols(client_ws: WebSocket) -> list[str]:
    """Keep client-requested subprotocol order for the upstream handshake."""
    values: list[str] = []
    for key, value in client_ws.headers.items():
        if key.lower() != "sec-websocket-protocol":
            continue
        values.extend(part.strip() for part in value.split(","))

    return [value for value in values if value]


def _resolve_upstream_ws_close_code(
    exc: websockets.exceptions.ConnectionClosed | None,
    upstream_ws,
) -> int | None:
    for close_frame in (getattr(exc, "rcvd", None), getattr(exc, "sent", None)):
        code = getattr(close_frame, "code", None)
        if code is not None:
            return int(code)

    code = getattr(upstream_ws, "close_code", None)
    if code is None:
        return None
    return int(code)


async def _receive_ws_client_message(client_ws: WebSocket) -> str | bytes:
    message = await client_ws.receive()
    if message["type"] == "websocket.disconnect":
        raise WebSocketDisconnect(code=int(message.get("code", 1000)))

    text = message.get("text")
    if text is not None:
        return str(text)

    payload = message.get("bytes")
    if payload is not None:
        return bytes(payload)

    return ""


@router.websocket("/embywebsocket")
async def emby_gateway_websocket(ws: WebSocket):
    """Transparently proxy Emby WebSocket connections to upstream server."""
    app_config = config_service.get_config()
    if not _is_dedicated_proxy_request(ws, app_config):
        await ws.close(code=1008)
        return

    try:
        target_url = _build_ws_target_url(app_config, ws)
        _normalize_proxy_base_url_candidate(ws.headers.get("X-Proxy-Server-Url"))
    except HTTPException:
        await ws.close(code=1008)
        return
    extra_headers = _build_ws_extra_headers(ws)
    requested_subprotocols = _extract_ws_requested_subprotocols(ws)

    upstream_ws = None
    upstream_close_code: int | None = None
    client_close_code: int | None = None
    try:
        connect_kwargs = {
            "additional_headers": extra_headers,
            "ping_interval": 20,
            "ping_timeout": 20,
            "close_timeout": 5,
        }
        if requested_subprotocols:
            connect_kwargs["subprotocols"] = requested_subprotocols

        upstream_ws = await websockets.connect(
            target_url,
            **connect_kwargs,
        )
        await ws.accept(subprotocol=getattr(upstream_ws, "subprotocol", None))

        async def _client_to_upstream() -> tuple[int | None, int | None]:
            try:
                while True:
                    data = await _receive_ws_client_message(ws)
                    await upstream_ws.send(data)
            except WebSocketDisconnect as exc:
                code = getattr(exc, "code", None)
                if code is None:
                    return None, None
                return int(code), None
            except websockets.exceptions.ConnectionClosed as exc:
                return None, _resolve_upstream_ws_close_code(exc, upstream_ws)

            return None, None

        async def _upstream_to_client() -> tuple[int | None, int | None]:
            try:
                async for message in upstream_ws:
                    if isinstance(message, str):
                        await ws.send_text(message)
                    else:
                        await ws.send_bytes(message)
            except websockets.exceptions.ConnectionClosed as exc:
                return None, _resolve_upstream_ws_close_code(exc, upstream_ws)

            return None, _resolve_upstream_ws_close_code(None, upstream_ws)

        # Run both relay directions concurrently; when either ends, cancel the other.
        client_to_upstream_task = asyncio.create_task(_client_to_upstream())
        upstream_to_client_task = asyncio.create_task(_upstream_to_client())
        done, pending = await asyncio.wait(
            [client_to_upstream_task, upstream_to_client_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in done:
            if task.cancelled():
                continue
            result_upstream_close_code, result_client_close_code = task.result()
            if result_upstream_close_code is not None:
                upstream_close_code = result_upstream_close_code
            if result_client_close_code is not None:
                client_close_code = result_client_close_code
        for task in pending:
            task.cancel()

    except Exception as exc:
        logger.debug(f"WebSocket proxy error: {exc}")
    finally:
        if upstream_ws and not upstream_ws.closed:
            if upstream_close_code is None:
                await upstream_ws.close()
            else:
                await upstream_ws.close(code=upstream_close_code)
        try:
            if client_close_code is None:
                await ws.close()
            else:
                await ws.close(code=client_close_code)
        except Exception:
            pass


@router.api_route("/", methods=_FORWARDED_METHODS, include_in_schema=False)
async def emby_gateway_root(request: Request):
    return await _handle_gateway_request(request, "")


@router.api_route("/{path:path}", methods=_FORWARDED_METHODS, include_in_schema=False)
async def emby_gateway(request: Request, path: str):
    return await _handle_gateway_request(request, path)
