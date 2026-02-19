"""
代理API路由

参考: go-emby2openlist internal/service/emby/redirect.go
支持302重定向和Emby反代
"""

from fastapi import APIRouter, HTTPException, Request, Response, Query, Depends
from fastapi.responses import RedirectResponse
from app.services.proxy_service import ProxyService
from app.services.quark_service import QuarkService
from app.services.link_resolver import LinkResolver
from app.services.webdav_fallback import WebDAVFallback
from app.services.config_service import get_config
from app.services.config_service import get_config_service
from app.core.logging import get_logger
from app.core.dependencies import get_quark_cookie, require_api_key
from app.core.validators import validate_identifier, validate_proxy_path, validate_http_url, InputValidationError
from typing import Optional

logger = get_logger(__name__)
router = APIRouter(
    prefix="/api/proxy",
    tags=["代理服务"],
    dependencies=[Depends(require_api_key)],
)

# Prefer ConfigService(CONFIG_PATH) at runtime; ConfigManager may be initialized with a different path
# in some deployment setups.
config = get_config()
config_service = get_config_service()


def _get_quark_cookie_from_config() -> str:
    try:
        cfg = config_service.get_config()
        quark_cfg = getattr(cfg, "quark", None)
        cookie = (getattr(quark_cfg, "cookie", "") or "").strip()
        if cookie:
            return cookie
    except Exception as exc:
        logger.warning(f"Failed to read quark cookie from ConfigService: {exc}")
    return (config.get_quark_cookie() or "").strip()


@router.get("/stream/test")
async def test_stream_endpoint():
    """
    测试代理流端点

    用于集成测试
    """
    try:
        # 返回测试数据
        return {
            "status": "ok",
            "message": "Test stream endpoint",
            "url": "http://example.com/test.mp4",
            "test": True
        }
    except Exception as e:
        logger.error(f"Failed to test stream endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stream/{file_id}")
async def proxy_stream(
    request: Request,
    file_id: str,
    range_header: str = None,
    source: str = Query("transcoding", description="上游源: transcoding 或 download"),
):
    """
    代理视频流 (Stream Mode)

    通过服务器中转流量，适用于不支持302重定向的场景。
    使用 StreamingResponse 实现流式传输。

    Args:
        request: FastAPI请求对象
        file_id: 文件ID
        range_header: Range请求头

    Returns:
        StreamingResponse
    """
    import aiohttp
    from fastapi.responses import StreamingResponse
    
    cookie = _get_quark_cookie_from_config()

    if not cookie:
        raise HTTPException(status_code=400, detail="Cookie not configured")

    try:
        file_id = validate_identifier(file_id, "file_id")
        
        # 1. 获取上游 URL 和请求头（优先转码，卡顿时更稳定）
        service = QuarkService(cookie=cookie)
        try:
            selected_source = (source or "transcoding").strip().lower()
            if selected_source not in {"transcoding", "download"}:
                selected_source = "transcoding"

            if selected_source == "download":
                link = await service.get_download_link(file_id)
            else:
                try:
                    link = await service.get_transcoding_link(file_id)
                except Exception:
                    # 转码链路不可用时回退下载直链
                    link = await service.get_download_link(file_id)
        finally:
            await service.close()

        redirect_url = link.url if link else None
        if not redirect_url:
            raise HTTPException(status_code=502, detail="Failed to resolve download URL")
             
        # 2. 准备请求头
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://pan.quark.cn/",
        }
        if link and link.headers:
            for header_name in ("Cookie", "Referer", "User-Agent"):
                header_value = link.headers.get(header_name)
                if header_value:
                    headers[header_name] = header_value
        
        # 优先使用 header 中的 Range，其次查找 query param (某些播放器可能不传 header)
        if not range_header:
            range_header = request.headers.get("Range")
            
        if range_header:
            headers["Range"] = range_header
            
        logger.info(f"Stream proxy for {file_id}, source: {source}, range: {range_header}")

        # 3. 创建生成器与响应
        # 注意: 我们需要在生成器内部管理 session 生命周期
        
        # 预先发起请求获取响应头 (HEAD or GET stream)
        # 为了简单且减少请求次数，我们直接开始 GET 请求，并利用 aiohttp 的 response
        # 但是 StreamingResponse 需要先知道 Content-Type 等信息吗？ 
        # StreamingResponse(content, status_code=200, headers=...)
        # 如果我们等到 generator start 才知道 headers，那 fastAPI 已经把 response headers 发送出去了（默认 200/chunked）。
        # 对于视频流，正确传递 Content-Type, Content-Length, Content-Range 至关重要。
        # 因此，我们需要先建立连接，拿到 headers，然后构建 StreamingResponse。
        
        # 定义一个 holder 类来传递资源所有权
        class StreamContext:
            def __init__(self):
                self.session = aiohttp.ClientSession()
                self.resp = None
                
            async def setup(self, url, headers):
                self.resp = await self.session.get(url, headers=headers, allow_redirects=True)
                return self.resp
                
            async def close(self):
                if self.resp:
                    self.resp.close()
                if self.session:
                    await self.session.close()

        stream_ctx = StreamContext()
        upstream_resp = await stream_ctx.setup(redirect_url, headers)
        
        # 检查上游状态
        if upstream_resp.status not in [200, 206]:
            await stream_ctx.close()
            # 尝试读取错误信息
            # err_text = await upstream_resp.text()
            raise HTTPException(status_code=upstream_resp.status, detail="Upstream error")

        # 提取关键响应头
        response_headers = {}
        for k in ["Content-Type", "Content-Length", "Content-Range", "Accept-Ranges", "Last-Modified", "ETag"]:
            if k in upstream_resp.headers:
                response_headers[k] = upstream_resp.headers[k]
        
        # 定义生成器
        async def iter_stream():
            try:
                # 64KB chunks
                async for chunk in upstream_resp.content.iter_chunked(64 * 1024):
                    yield chunk
            except Exception as e:
                logger.error(f"Stream interrupted: {e}")
                raise
            finally:
                # 确保资源释放
                logger.debug(f"Closing stream session for {file_id}")
                await stream_ctx.close()

        # 返回 StreamingResponse
        # 注意: status_code 应跟随上游 (200 or 206)
        return StreamingResponse(
            iter_stream(),
            status_code=upstream_resp.status,
            headers=response_headers,
            media_type=response_headers.get("Content-Type", "application/octet-stream")
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to proxy stream: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/redirect/{file_id}")
async def redirect_302(
    file_id: str,
    path: Optional[str] = Query(None, description="文件路径，用于WebDAV兜底")
):
    """
    302重定向到夸克直链（支持智能兜底）。
    """
    cookie = _get_quark_cookie_from_config()

    if not cookie:
        raise HTTPException(status_code=400, detail="Cookie not configured")

    try:
        file_id = validate_identifier(file_id, "file_id")

        from app.services.quark_service import QuarkService

        service = QuarkService(cookie=cookie)
        resolver = LinkResolver(quark_service=service)
        fallback = WebDAVFallback()

        redirect_url: Optional[str] = None
        error_msg: Optional[str] = None

        async def _is_playable_without_quark_headers(url: str) -> bool:
            """检查 URL 在无夸克 Cookie/Referer 前提下是否可直接拉流。"""
            import aiohttp

            headers = {
                "User-Agent": "Mozilla/5.0",
                "Range": "bytes=0-1",
            }
            timeout = aiohttp.ClientTimeout(total=8)
            try:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(url, headers=headers, allow_redirects=True) as resp:
                        return resp.status in (200, 206)
            except Exception:
                return False

        try:
            # 1) 优先解析下载直链
            redirect_url = await resolver.resolve(file_id, path)
            logger.info(f"Resolved direct link for {file_id}")

            # 2) 若直链依赖夸克请求头导致播放器不可播，则回退到转码直链
            if redirect_url and not await _is_playable_without_quark_headers(redirect_url):
                logger.warning(f"Resolved direct link is not directly playable, fallback to transcoding: {file_id}")
                try:
                    trans_link = await service.get_transcoding_link(file_id)
                    if trans_link and trans_link.url:
                        redirect_url = trans_link.url
                        logger.info(f"Using transcoding link for redirect fallback: {file_id}")
                except Exception as trans_exc:
                    logger.warning(f"Transcoding fallback failed for {file_id}: {trans_exc}")
        except Exception as e:
            logger.warning(f"Link resolution failed: {e}")
            error_msg = str(e)

        # 3) 若仍失败，尝试 WebDAV 兜底
        if not redirect_url and path:
            logger.info(f"Attempting WebDAV fallback for path: {path}")
            redirect_url = fallback.get_fallback_url(path)
            if redirect_url:
                logger.warning(f"Using WebDAV fallback for {file_id}")

        await service.close()

        if redirect_url:
            logger.info(f"302 redirect to: {redirect_url[:60]}... (Total len: {len(redirect_url)})")
            return RedirectResponse(url=redirect_url, status_code=302)

        raise HTTPException(status_code=502, detail=f"Failed to resolve link: {error_msg}")

    except InputValidationError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get redirect URL: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.head("/redirect/{file_id}")
async def redirect_302_head(
    file_id: str,
    path: Optional[str] = Query(None, description="文件路径，用于WebDAV兜底"),
):
    # Some clients and validators send HEAD requests before GET.
    return await redirect_302(file_id=file_id, path=path)


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
    cookie = _get_quark_cookie_from_config()

    if not cookie:
        raise HTTPException(status_code=400, detail="Cookie not configured")

    try:
        file_id = validate_identifier(file_id, "file_id")
        service = QuarkService(cookie=cookie)
        link = await service.get_transcoding_link(file_id)
        await service.close()

        logger.info(f"302 redirect to transcoding link: {link.url[:100]}...")
        return RedirectResponse(url=link.url, status_code=302)
    except InputValidationError:
        raise
    except Exception as e:
        logger.error(f"Failed to get transcoding link: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


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
        # 从配置获取Emby服务器地址
        app_config = config_service.get_config()
        emby_url = app_config.endpoints[0].emby_url if app_config.endpoints else "http://localhost:8096"
        if emby_url:
            validate_http_url(emby_url, "emby_url")

        # 构建目标URL
        target_url = f"{emby_url}/{path}"
        query_string = str(request.query_params)
        if query_string:
            target_url = f"{target_url}?{query_string}"

        logger.debug(f"Proxying Emby request to: {target_url}")

        # 这里可以实现完整的Emby反代逻辑
        # 包括PlaybackInfo Hook等

        return {
            "message": "Emby proxy endpoint",
            "target_url": target_url,
            "path": path
        }
    except InputValidationError:
        raise
    except Exception as e:
        logger.error(f"Failed to proxy Emby request: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cache/clear")
async def clear_cache():
    """
    清除缓存
    """
    cookie = _get_quark_cookie_from_config()

    if not cookie:
        raise HTTPException(status_code=400, detail="Cookie not configured")

    try:
        async with ProxyService(cookie=cookie) as service:
            await service.clear_cache()
            return {"status": "ok", "message": "Cache cleared"}
    except InputValidationError:
        raise
    except Exception as e:
        logger.error(f"Failed to clear cache: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cache/stats")
async def get_cache_stats():
    """
    获取缓存统计
    """
    cookie = _get_quark_cookie_from_config()

    if not cookie:
        raise HTTPException(status_code=400, detail="Cookie not configured")

    try:
        async with ProxyService(cookie=cookie) as service:
            stats = await service.get_cache_stats()
            return {"status": "ok", "stats": stats}
    except InputValidationError:
        raise
    except Exception as e:
        logger.error(f"Failed to get cache stats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

