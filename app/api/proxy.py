"""
代理API路由

参考: go-emby2openlist internal/service/emby/redirect.go
支持302重定向和Emby反代
"""

from fastapi import APIRouter, HTTPException, Request, Response, Query
from fastapi.responses import RedirectResponse
from app.services.proxy_service import ProxyService
from app.services.quark_service import QuarkService
from app.services.link_resolver import LinkResolver
from app.services.webdav_fallback import WebDAVFallback
from app.core.config_manager import get_config
from app.services.config_service import get_config_service
from app.core.logging import get_logger
from app.core.dependencies import get_quark_cookie
from app.core.validators import validate_identifier, validate_proxy_path, validate_http_url, InputValidationError
from typing import Optional

logger = get_logger(__name__)
router = APIRouter(prefix="/api/proxy", tags=["代理服务"])

# 获取配置管理器
config = get_config()
config_service = get_config_service()


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
    redirect: bool = True
):
    """
    代理视频流

    参考: go-emby2openlist internal/service/emby/redirect.go

    支持两种模式:
    1. 302重定向模式 (redirect=true): 返回302重定向到夸克直链
    2. 代理模式 (redirect=false): 代理视频流数据

    Args:
        request: FastAPI请求对象
        file_id: 文件ID
        range_header: Range请求头
        redirect: 是否使用302重定向

    Returns:
        302重定向响应或代理流响应
    """
    cookie = config.get_quark_cookie()

    if not cookie:
        raise HTTPException(status_code=400, detail="Cookie not configured")

    try:
        file_id = validate_identifier(file_id, "file_id")
        if redirect:
            # 302重定向模式
            async with ProxyService(cookie=cookie) as service:
                redirect_url = await service.redirect_302(file_id)
                logger.info(f"302 redirect to: {redirect_url[:100]}...")
                return RedirectResponse(url=redirect_url, status_code=302)
        else:
            # 代理模式
            async with ProxyService(cookie=cookie) as service:
                response, headers = await service.proxy_stream(file_id, range_header)
                return Response(
                    content=response.content,
                    status_code=response.status,
                    headers=headers,
                    media_type=headers.get("Content-Type", "video/mp4")
                )
    except InputValidationError:
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
    302重定向到夸克直链 (支持智能兜底)

    Args:
        file_id: 文件ID
        path: 文件路径 (可选)

    Returns:
        302重定向响应
    """
    cookie = config.get_quark_cookie()

    if not cookie:
        raise HTTPException(status_code=400, detail="Cookie not configured")

    try:
        file_id = validate_identifier(file_id, "file_id")
        
        # 初始化服务
        # 注意: 这里仍然使用 ProxyService 来管理 QuarkService 的生命周期
        # 或者我们直接实例化 QuarkService
        from app.services.quark_service import QuarkService
        
        service = QuarkService(cookie=cookie)
        resolver = LinkResolver(quark_service=service)
        fallback = WebDAVFallback()
        
        redirect_url = None
        error_msg = None
        
        try:
            # 1. 尝试解析直链 (Quark ID -> AList Path)
            redirect_url = await resolver.resolve(file_id, path)
            logger.info(f"Resolved direct link for {file_id}")
            
        except Exception as e:
            logger.warning(f"Link resolution failed: {e}")
            error_msg = str(e)
            
            # 2. 尝试 WebDAV 兜底
            if path:
                logger.info(f"Attempting WebDAV fallback for path: {path}")
                redirect_url = fallback.get_fallback_url(path)
                if redirect_url:
                    logger.warning(f"Using WebDAV fallback for {file_id}")
            else:
                logger.warning(f"No path provided, cannot use WebDAV fallback for {file_id}")

        # 关闭服务
        await service.close()
        
        if redirect_url:
            # 记录最终跳转
            logger.info(f"302 redirect to: {redirect_url[:60]}... (Total len: {len(redirect_url)})")
            return RedirectResponse(url=redirect_url, status_code=302)
        else:
            raise HTTPException(status_code=502, detail=f"Failed to resolve link: {error_msg}")

    except InputValidationError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get redirect URL: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


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
    cookie = config.get_quark_cookie()

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
    cookie = config.get_quark_cookie()

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
