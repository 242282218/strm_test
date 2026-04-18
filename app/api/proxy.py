"""
代理API路由

参考: go-emby2openlist internal/service/emby/redirect.go
支持302重定向和Emby反代
安全: SSRF 防护 - 验证所有外部 URL
"""

import asyncio
import os
import time
import re

import aiohttp
from aiohttp.http_exceptions import LineTooLong

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse, Response, StreamingResponse

from app.core.config_manager import get_config
from app.core.dependencies import require_api_key
from app.core.logging import get_logger
from app.core.url_validator import URLValidationError, emby_validator, general_validator
from app.core.validators import InputValidationError, validate_identifier, validate_proxy_path
from app.services.config_service import get_config_service
from app.services.first_segment_cache_service import (
    FirstSegmentCacheEntry,
    get_first_segment_cache_service,
)
from app.services.link_resolver import LinkResolver
from app.services.playback_decision_service import PlaybackDecisionService
from app.services.proxy_service import ProxyService
from app.services.quark_service import QuarkService
from app.services.webdav_fallback import WebDAVFallback
from app.utils.emby_request import (
    resolve_emby_authorization_context,
    resolve_emby_client_name,
    resolve_emby_device_name,
)


logger = get_logger(__name__)
router = APIRouter(
    prefix="/api/proxy",
    tags=["代理服务"],
)

# 获取配置管理器
config = get_config()
config_service = get_config_service()
playback_decision_service = PlaybackDecisionService()
first_segment_cache_service = get_first_segment_cache_service()

# Playability probe cache (small TTL) to avoid repeated network checks.
_probe_cache: dict[str, tuple[float, bool]] = {}
_probe_cache_lock = asyncio.Lock()
_RANGE_HEADER_RE = re.compile(r"^bytes=(\d+)-(\d+)$")


def _is_internal_redirect_enabled() -> bool:
    flag = os.getenv("SMART_MEDIA_PROXY_INTERNAL_REDIRECT", "true").strip().lower()
    return flag not in {"0", "false", "no", "off"}


def _build_local_download_stream_redirect(file_id: str) -> RedirectResponse:
    normalized_file_id = file_id.strip()
    return RedirectResponse(url=f"/api/proxy/stream/{normalized_file_id}?source=download", status_code=302)


def _build_stream_fallback_response(file_id: str) -> RedirectResponse:
    normalized_file_id = file_id.strip()
    if _is_internal_redirect_enabled():
        return _build_local_download_stream_redirect(normalized_file_id)
    return RedirectResponse(url=f"/api/proxy/stream/{normalized_file_id}", status_code=307)


def _get_probe_cache_ttl_seconds() -> int:
    raw = os.getenv("SMART_MEDIA_PLAYABLE_PROBE_CACHE_TTL", "20").strip()
    try:
        return max(0, int(raw))
    except Exception:
        return 20


def _get_probe_cache_size() -> int:
    raw = os.getenv("SMART_MEDIA_PLAYABLE_PROBE_CACHE_SIZE", "512").strip()
    try:
        return max(1, int(raw))
    except Exception:
        return 512


def _build_first_segment_cache_key(file_id: str, source: str) -> str:
    return f"{file_id}:{(source or 'download').strip().lower()}"


def _parse_bounded_range_header(range_header: str | None) -> tuple[int, int] | None:
    if not range_header:
        return None
    match = _RANGE_HEADER_RE.match(range_header.strip())
    if not match:
        return None
    start = int(match.group(1))
    end = int(match.group(2))
    if end < start:
        return None
    return start, end


def _is_first_segment_cacheable_range(range_header: str | None) -> tuple[int, int] | None:
    parsed = _parse_bounded_range_header(range_header)
    if parsed is None:
        return None
    start, end = parsed
    if start != 0:
        return None
    segment_size = first_segment_cache_service.get_segment_size_bytes()
    if segment_size <= 0 or end >= segment_size:
        return None
    return start, end


def _extract_total_length_from_headers(headers: dict[str, str]) -> int:
    content_range = headers.get("Content-Range", "")
    if "/" in content_range:
        total = content_range.rsplit("/", 1)[-1].strip()
        if total.isdigit():
            return int(total)
    content_length = headers.get("Content-Length", "").strip()
    if content_length.isdigit():
        return int(content_length)
    return 0


def _build_cached_first_segment_response(
    entry: FirstSegmentCacheEntry,
    *,
    range_start: int,
    range_end: int,
) -> Response:
    payload = entry.data[range_start : range_end + 1]
    headers = {
        "Content-Type": entry.content_type,
        "Content-Length": str(len(payload)),
        "Content-Range": f"bytes {range_start}-{range_end}/{entry.total_length}",
        "Accept-Ranges": entry.accept_ranges or "bytes",
    }
    if entry.etag:
        headers["ETag"] = entry.etag
    if entry.last_modified:
        headers["Last-Modified"] = entry.last_modified
    return Response(content=payload, status_code=206, headers=headers, media_type=entry.content_type)


async def _prime_first_segment_cache(
    *,
    file_id: str,
    source: str,
    redirect_url: str,
    headers: dict[str, str],
) -> FirstSegmentCacheEntry | None:
    segment_size = first_segment_cache_service.get_segment_size_bytes()
    if not first_segment_cache_service.is_enabled() or segment_size <= 0:
        return None

    request_headers = dict(headers)
    request_headers["Range"] = f"bytes=0-{segment_size - 1}"

    session = aiohttp.ClientSession()
    response = None
    try:
        response = await session.get(redirect_url, headers=request_headers, allow_redirects=True)
        if response.status not in [200, 206]:
            return None

        collected = bytearray()
        async for chunk in response.content.iter_chunked(1024 * 1024):
            if not chunk:
                continue
            remaining = segment_size - len(collected)
            if remaining <= 0:
                break
            collected.extend(chunk[:remaining])
            if len(collected) >= segment_size:
                break

        if not collected:
            return None

        response_headers = dict(response.headers)
        total_length = _extract_total_length_from_headers(response_headers)
        if total_length <= 0:
            total_length = len(collected)

        cache_key = _build_first_segment_cache_key(file_id, source)
        first_segment_cache_service.put(
            cache_key,
            data=bytes(collected),
            total_length=total_length,
            content_type=response_headers.get("Content-Type", "application/octet-stream"),
            accept_ranges=response_headers.get("Accept-Ranges", "bytes"),
            etag=response_headers.get("ETag"),
            last_modified=response_headers.get("Last-Modified"),
        )
        return first_segment_cache_service.get(cache_key)
    finally:
        if response is not None:
            response.close()
        await session.close()


async def _get_probe_cache(url: str) -> bool | None:
    ttl = _get_probe_cache_ttl_seconds()
    if ttl <= 0:
        return None

    now = time.monotonic()
    async with _probe_cache_lock:
        cached = _probe_cache.get(url)
        if not cached:
            return None
        expires_at, playable = cached
        if expires_at <= now:
            _probe_cache.pop(url, None)
            return None
        return playable


async def _set_probe_cache(url: str, playable: bool) -> None:
    ttl = _get_probe_cache_ttl_seconds()
    if ttl <= 0:
        return

    expires_at = time.monotonic() + ttl
    max_size = _get_probe_cache_size()
    async with _probe_cache_lock:
        if url not in _probe_cache and len(_probe_cache) >= max_size:
            oldest_key = min(_probe_cache, key=lambda key: _probe_cache[key][0])
            _probe_cache.pop(oldest_key, None)
        _probe_cache[url] = (expires_at, playable)


async def _is_url_directly_playable(url: str, timeout_seconds: int = 8) -> bool:
    """Check whether a remote URL can be fetched without Quark-specific headers."""
    cached = await _get_probe_cache(url)
    if cached is not None:
        return cached

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Range": "bytes=0-1",
    }
    timeout = aiohttp.ClientTimeout(total=timeout_seconds)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, headers=headers, allow_redirects=True) as resp:
                playable = resp.status in (200, 206)
    except Exception:
        playable = False

    await _set_probe_cache(url, playable)
    return playable


async def _resolve_playable_transcoding_url(service: QuarkService, file_id: str) -> str | None:
    try:
        trans_link = await service.get_transcoding_link(file_id)
        if trans_link and trans_link.url and await _is_url_directly_playable(trans_link.url):
            logger.info(f"Using transcoding link for redirect fallback: {file_id}")
            return trans_link.url
    except Exception as exc:
        logger.warning(f"Transcoding fallback failed for {file_id}: {exc}")
    return None


async def _resolve_stream_link(service: QuarkService, file_id: str, source: str) -> tuple[str, dict[str, str]]:
    selected_source = (source or "download").strip().lower()
    if selected_source not in {"transcoding", "download"}:
        selected_source = "download"

    async def _resolve_candidate(source_name: str):
        try:
            if source_name == "download":
                link_model = await service.get_download_link(file_id)
            else:
                link_model = await service.get_transcoding_link(file_id)
        except Exception as exc:
            logger.warning("Failed to resolve %s link for %s: %s", source_name, file_id, exc)
            return None

        redirect_candidate = (getattr(link_model, "url", "") or "").strip()
        if not redirect_candidate:
            logger.warning("Resolved %s link is empty for %s", source_name, file_id)
            return None
        return link_model, redirect_candidate

    source_order = ("download", "transcoding") if selected_source == "download" else ("transcoding", "download")

    link = None
    redirect_url = None
    for source_name in source_order:
        resolved_candidate = await _resolve_candidate(source_name)
        if resolved_candidate is None:
            continue
        link, redirect_url = resolved_candidate
        break

    if not redirect_url:
        raise HTTPException(status_code=502, detail="Failed to resolve stream URL")

    try:
        general_validator.validate(redirect_url)
    except URLValidationError as e:
        logger.error(f"Invalid redirect URL (SSRF protection): {e}")
        raise HTTPException(status_code=400, detail=f"Invalid redirect URL: {e}")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://pan.quark.cn/",
        "Accept-Encoding": "identity",
    }
    link_headers = getattr(link, "headers", None)
    if link_headers:
        for header_name in ("Cookie", "Referer", "User-Agent"):
            header_value = link_headers.get(header_name)
            if header_value:
                headers[header_name] = header_value

    return redirect_url, headers


async def _stream_from_url(file_id: str, redirect_url: str, headers: dict[str, str], method: str = "GET") -> Response:
    request_method = (method or "GET").upper()

    class StreamContext:
        def __init__(self):
            self.session = aiohttp.ClientSession()
            self.resp = None

        async def open(self, request_method: str, url: str, request_headers: dict[str, str]):
            if self.resp:
                self.resp.close()
                self.resp = None
            if request_method == "HEAD":
                self.resp = await self.session.head(url, headers=request_headers, allow_redirects=True)
            else:
                self.resp = await self.session.get(url, headers=request_headers, allow_redirects=True)
            return self.resp

        async def close(self):
            if self.resp:
                self.resp.close()
            if self.session:
                await self.session.close()

    def _extract_total_length(response_headers: dict[str, str]) -> str | None:
        content_range = response_headers.get("Content-Range")
        if not content_range:
            return None
        _, _, total = content_range.partition("/")
        total = total.strip()
        if not total or total == "*":
            return None
        return total

    def _build_response_headers(upstream_headers, *, fallback_total_length: str | None = None) -> dict[str, str]:
        response_headers: dict[str, str] = {}
        for header_name in ["Content-Type", "Content-Length", "Content-Range", "Accept-Ranges", "Last-Modified", "ETag"]:
            header_value = upstream_headers.get(header_name)
            if header_value:
                response_headers[header_name] = header_value
        if fallback_total_length:
            response_headers["Content-Length"] = fallback_total_length
            response_headers.pop("Content-Range", None)
        return response_headers

    stream_ctx = StreamContext()
    try:
        try:
            upstream_resp = await stream_ctx.open(request_method, redirect_url, headers)
            fallback_total_length = None
        except LineTooLong:
            if request_method != "HEAD":
                raise
            probe_headers = dict(headers)
            probe_headers["Range"] = "bytes=0-0"
            upstream_resp = await stream_ctx.open("GET", redirect_url, probe_headers)
            fallback_total_length = _extract_total_length(upstream_resp.headers)

        if upstream_resp.status not in [200, 206]:
            raise HTTPException(status_code=upstream_resp.status, detail="Upstream error")

        response_headers = _build_response_headers(upstream_resp.headers, fallback_total_length=fallback_total_length)

        if request_method == "HEAD":
            return Response(
                content=b"",
                status_code=200,
                headers=response_headers,
                media_type=response_headers.get("Content-Type", "application/octet-stream"),
            )

        async def iter_stream():
            try:
                async for chunk in upstream_resp.content.iter_chunked(1024 * 1024):
                    yield chunk
            except Exception as e:
                logger.error(f"Stream interrupted: {e}")
                raise
            finally:
                logger.debug(f"Closing stream session for {file_id}")
                await stream_ctx.close()

        return StreamingResponse(
            iter_stream(),
            status_code=upstream_resp.status,
            headers=response_headers,
            media_type=response_headers.get("Content-Type", "application/octet-stream"),
        )
    except Exception:
        await stream_ctx.close()
        raise


async def proxy_stream_by_file_id(
    request: Request,
    file_id: str,
    range_header: str = None,
    source: str = "download",
):
    cookie = config.get_quark_cookie()

    if not cookie:
        raise HTTPException(status_code=400, detail="Cookie not configured")

    try:
        file_id = validate_identifier(file_id, "file_id")

        service = QuarkService(cookie=cookie)
        try:
            redirect_url, headers = await _resolve_stream_link(service, file_id, source)
        finally:
            await service.close()

        if not range_header:
            range_header = request.headers.get("Range")

        cacheable_range = None
        if request.method.upper() == "GET":
            cacheable_range = _is_first_segment_cacheable_range(range_header)
            if cacheable_range is not None and first_segment_cache_service.is_enabled():
                cache_key = _build_first_segment_cache_key(file_id, source)
                cached_entry = first_segment_cache_service.get(cache_key)
                if cached_entry is None:
                    cached_entry = await _prime_first_segment_cache(
                        file_id=file_id,
                        source=source,
                        redirect_url=redirect_url,
                        headers=headers,
                    )
                if cached_entry is not None:
                    range_start, range_end = cacheable_range
                    if range_end < len(cached_entry.data):
                        logger.info("First segment cache hit for %s, range=%s", file_id, range_header)
                        return _build_cached_first_segment_response(
                            cached_entry,
                            range_start=range_start,
                            range_end=range_end,
                        )

        if range_header:
            headers["Range"] = range_header

        logger.info(f"Stream proxy for {file_id}, source: {source}, range: {range_header}")
        return await _stream_from_url(file_id, redirect_url, headers, method=request.method)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to proxy stream: {e!s}")
        raise HTTPException(status_code=500, detail="Failed to proxy stream")


async def _resolve_redirect_target(
    file_id: str,
    path: str | None,
    resolver: LinkResolver,
    service: QuarkService,
    fallback: WebDAVFallback,
    client_name: str | None = None,
    device_name: str | None = None,
    user_agent: str | None = None,
) -> tuple[str | None, str | None]:
    redirect_url: str | None = None
    error_msg: str | None = None
    try:
        candidate_url = await resolver.resolve(file_id, path)
        logger.info(f"Resolved direct link for {file_id}")
        if candidate_url and await _is_url_directly_playable(candidate_url):
            redirect_url = candidate_url
        else:
            if candidate_url:
                logger.warning(f"Resolved direct link is not directly playable, fallback to transcoding: {file_id}")
                playback_decision_service.record_direct_failure(
                    client_name=client_name,
                    device_name=device_name,
                    user_agent=user_agent,
                    direct_url=candidate_url,
                    reason="preflight_failed",
                )
            redirect_url = await _resolve_playable_transcoding_url(service, file_id)
    except Exception as exc:
        logger.warning(f"Link resolution failed: {exc}")
        error_msg = str(exc)

    if not redirect_url and path:
        logger.info(f"Attempting WebDAV fallback for path: {path}")
        redirect_url = fallback.get_fallback_url(path)
        if redirect_url:
            logger.warning(f"Using WebDAV fallback for {file_id}")

    return redirect_url, error_msg


@router.get("/stream/test")
async def test_stream_endpoint():
    """
    测试代理流端点

    用于集成测试
    """
    try:
        # 返回测试数据
        return {"status": "ok", "message": "Test stream endpoint", "url": "http://example.com/test.mp4", "test": True}
    except Exception as e:
        logger.error(f"Failed to test stream endpoint: {e!s}")
        raise HTTPException(status_code=500, detail="Failed to test stream endpoint")


@router.api_route("/stream/{file_id}", methods=["GET", "HEAD"])
async def proxy_stream(
    request: Request,
    file_id: str,
    range_header: str = None,
    source: str = Query("download", description="上游源: download 或 transcoding"),
):
    """
    代理视频流 (Stream Mode)

    通过服务器中转流量，适用于不支持302重定向的场景。
    使用 StreamingResponse 实现流式传输。
    """
    return await proxy_stream_by_file_id(request=request, file_id=file_id, range_header=range_header, source=source)


@router.get("/redirect/{file_id}")
async def redirect_302(
    request: Request,
    file_id: str,
    path: str | None = Query(None, description="文件路径，用于WebDAV兜底"),
):
    """
    302重定向到夸克直链（支持智能兜底）。
    """
    cookie = config.get_quark_cookie()

    if not cookie:
        raise HTTPException(status_code=400, detail="Cookie not configured")

    try:
        file_id = validate_identifier(file_id, "file_id")
        auth_context = resolve_emby_authorization_context(request.headers)
        client_name = resolve_emby_client_name(request.headers, auth_context)
        device_name = resolve_emby_device_name(request.headers, auth_context)

        service = QuarkService(cookie=cookie)
        resolver = LinkResolver(quark_service=service)
        fallback = WebDAVFallback()

        resolved_file_id = file_id
        if path:
            try:
                file_info = await service.get_file_by_path(path)
                if file_info and getattr(file_info, "fid", ""):
                    resolved_file_id = file_info.fid
                    logger.info(f"Resolved file_id by path: {path} -> {resolved_file_id}")
            except Exception as exc:
                logger.warning(f"Failed to resolve file_id by path {path}: {exc}")

        try:
            redirect_url, error_msg = await _resolve_redirect_target(
                file_id=resolved_file_id,
                path=path,
                resolver=resolver,
                service=service,
                fallback=fallback,
                client_name=client_name,
                device_name=device_name,
                user_agent=request.headers.get("User-Agent"),
            )
        finally:
            await service.close()

        fallback_file_id = resolved_file_id
        if redirect_url:
            decision = playback_decision_service.decide_delivery_mode(
                client_name=client_name,
                device_name=device_name,
                user_agent=request.headers.get("User-Agent"),
                direct_url=redirect_url,
            )
            if decision.mode == "proxy":
                logger.info(
                    "Redirect route switched to local proxy for %s (reason=%s)",
                    fallback_file_id,
                    decision.reason,
                )
                return _build_local_download_stream_redirect(fallback_file_id)
            try:
                general_validator.validate(redirect_url)
            except URLValidationError as e:
                logger.warning("Resolved redirect URL failed validation for %s, fallback to local proxy: %s", fallback_file_id, e)
                return _build_stream_fallback_response(fallback_file_id)

            logger.info(f"302 redirect to: {redirect_url[:60]}... (Total len: {len(redirect_url)})")
            return RedirectResponse(url=redirect_url, status_code=302)

        logger.warning(f"Failed to resolve a playable redirect URL for {file_id}: {error_msg or 'fallback to stream'}")
        if _is_internal_redirect_enabled():
            logger.info(f"Using local 302 stream fallback for {fallback_file_id}")
        return _build_stream_fallback_response(fallback_file_id)

    except InputValidationError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get redirect URL: {e!s}")
        raise HTTPException(status_code=500, detail="Failed to get redirect URL")


@router.get("/transcoding/{file_id}")
async def get_transcoding_link(file_id: str):
    """
    获取转码直链（302重定向）

    用于Emby/Jellyfin播放

    Args:
        file_id: 文件ID

    Returns:
        302重定向到转码直链
    """
    cookie = config.get_quark_cookie()

    if not cookie:
        raise HTTPException(status_code=400, detail="Cookie not configured")

    try:
        file_id = validate_identifier(file_id, "file_id")
        service = QuarkService(cookie=cookie)
        link = await service.get_transcoding_link(file_id)
        await service.close()

        # SSRF 防护: 验证转码直链 URL
        try:
            general_validator.validate(link.url)
        except URLValidationError as e:
            logger.error(f"Invalid transcoding URL (SSRF protection): {e}")
            raise HTTPException(status_code=400, detail=f"Invalid transcoding URL: {e}")

        logger.info(f"302 redirect to transcoding link: {link.url[:100]}...")
        return RedirectResponse(url=link.url, status_code=302)
    except InputValidationError:
        raise
    except URLValidationError as e:
        logger.error(f"URL validation failed: {e!s}")
        raise HTTPException(status_code=400, detail="Invalid transcoding URL")
    except Exception as e:
        logger.error(f"Failed to get transcoding link: {e!s}")
        raise HTTPException(status_code=500, detail="Failed to get transcoding link")


@router.get("/emby/{path:path}")
async def proxy_emby_request(request: Request, path: str):
    """
    Emby反代

    将Emby请求转发到实际Emby服务器

    Args:
        request: FastAPI请求对象
        path: Emby路径

    Returns:
        Emby响应
    """
    try:
        path = validate_proxy_path(path, "path")
        app_config = config_service.get_config()
        from app.api import emby_gateway as emby_gateway_module

        emby_url = emby_gateway_module._resolve_emby_base_url(request, app_config)
        proxy_base_url = emby_gateway_module._resolve_requested_proxy_base_url(request, app_config)
        return await emby_gateway_module._forward_to_emby(
            request,
            app_config,
            path,
            emby_base_url=emby_url,
            proxy_base_url=proxy_base_url,
        )
    except HTTPException:
        raise
    except InputValidationError:
        raise
    except URLValidationError as e:
        logger.error(f"URL validation failed: {e!s}")
        raise HTTPException(status_code=400, detail="Invalid Emby server URL")
    except Exception as e:
        logger.error(f"Failed to proxy Emby request: {e!s}")
        raise HTTPException(status_code=500, detail="Failed to proxy Emby request")


@router.post("/cache/clear", dependencies=[Depends(require_api_key)])
async def clear_cache():
    """
    清除缓存
    """
    cookie = config.get_quark_cookie()

    if not cookie:
        raise HTTPException(status_code=400, detail="Cookie not configured")

    try:
        async with ProxyService(cookie=cookie) as service:
            await service.clear_cache()
            first_segment_cache_service.clear()
            return {"status": "ok", "message": "Cache cleared"}
    except InputValidationError:
        raise
    except Exception as e:
        logger.error(f"Failed to clear cache: {e!s}")
        raise HTTPException(status_code=500, detail="Failed to clear cache")


@router.get("/cache/stats", dependencies=[Depends(require_api_key)])
async def get_cache_stats():
    """
    获取缓存统计
    """
    cookie = config.get_quark_cookie()

    if not cookie:
        raise HTTPException(status_code=400, detail="Cookie not configured")

    try:
        async with ProxyService(cookie=cookie) as service:
            stats = dict(await service.get_cache_stats() or {})
            stats["first_segment_cache"] = first_segment_cache_service.get_stats()
            return {"status": "ok", "stats": stats}
    except InputValidationError:
        raise
    except Exception as e:
        logger.error(f"Failed to get cache stats: {e!s}")
        raise HTTPException(status_code=500, detail="Failed to get cache stats")
