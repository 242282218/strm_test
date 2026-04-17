"""
稳定 STRM 播放入口
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

from app.api.proxy import (
    _build_stream_fallback_response,
    _build_local_download_stream_redirect,
    _resolve_redirect_target,
)
from app.core.config_manager import get_config
from app.core.logging import get_logger
from app.core.url_validator import URLValidationError, general_validator
from app.core.validators import InputValidationError, validate_identifier
from app.services.link_resolver import LinkResolver
from app.services.media_mapping_service import MediaMappingService
from app.services.playback_decision_service import PlaybackDecisionService
from app.services.quark_service import QuarkService
from app.services.webdav_fallback import WebDAVFallback
from app.utils.emby_request import (
    resolve_emby_authorization_context,
    resolve_emby_client_name,
    resolve_emby_device_name,
)


router = APIRouter(tags=["StableStream"])

config = get_config()
playback_decision_service = PlaybackDecisionService()
logger = get_logger(__name__)


@router.api_route("/strm/v1/m/{media_id}/{display_name:path}", methods=["GET", "HEAD"])
async def stable_media_entry(request: Request, media_id: str, display_name: str):
    """
    稳定媒体入口。

    入口本身只认 media_id，真实 file_id/path 通过映射层解析。
    """
    _ = display_name
    try:
        media_id = validate_identifier(media_id, "media_id")
        cookie = config.get_quark_cookie()
        if not cookie:
            raise HTTPException(status_code=400, detail="Cookie not configured")

        mapping_service = MediaMappingService()
        mapping = mapping_service.get_by_media_id(media_id)
        if mapping is None:
            raise HTTPException(status_code=404, detail="Media mapping not found")

        service = QuarkService(cookie=cookie)
        resolver = LinkResolver(quark_service=service)
        fallback = WebDAVFallback()
        auth_context = resolve_emby_authorization_context(request.headers)
        client_name = resolve_emby_client_name(request.headers, auth_context)
        device_name = resolve_emby_device_name(request.headers, auth_context)

        resolved_file_id = (mapping.provider_file_id or "").strip() or None
        source_path = (mapping.source_path or "").strip() or None

        if not resolved_file_id and source_path:
            file_info = await service.get_file_by_path(source_path)
            if file_info and getattr(file_info, "fid", ""):
                resolved_file_id = file_info.fid
                mapping_service.update_provider_file_id(media_id, resolved_file_id)

        if not resolved_file_id:
            await service.close()
            raise HTTPException(status_code=502, detail="Failed to resolve provider file ID")

        try:
            redirect_url, _ = await _resolve_redirect_target(
                file_id=resolved_file_id,
                path=source_path,
                resolver=resolver,
                service=service,
                fallback=fallback,
                client_name=client_name,
                device_name=device_name,
                user_agent=request.headers.get("User-Agent"),
            )
        finally:
            await service.close()

        if redirect_url:
            decision = playback_decision_service.decide_delivery_mode(
                client_name=client_name,
                device_name=device_name,
                user_agent=request.headers.get("User-Agent"),
                direct_url=redirect_url,
            )
            if decision.mode == "proxy":
                return _build_local_download_stream_redirect(resolved_file_id)
            try:
                general_validator.validate(redirect_url)
            except URLValidationError as exc:
                logger.warning("Stable media redirect failed validation for %s, fallback to local proxy: %s", resolved_file_id, exc)
                return _build_stream_fallback_response(resolved_file_id)
            return RedirectResponse(url=redirect_url, status_code=302)

        logger.warning("Stable media entry could not resolve redirect for %s, fallback to local proxy", resolved_file_id)
        return _build_stream_fallback_response(resolved_file_id)
    except HTTPException:
        raise
    except InputValidationError:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to resolve stable media entry") from exc
