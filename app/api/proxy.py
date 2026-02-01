"""
代理API路由

参考: go-emby2openlist internal/service/emby/redirect.go
支持302重定向和Emby反代
"""

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from app.services.proxy_service import ProxyService
from app.services.quark_service import QuarkService
from app.core.config_manager import get_config
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/proxy", tags=["代理服务"])

# 获取配置管理器
config = get_config()


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
    except Exception as e:
        logger.error(f"Failed to proxy stream: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/redirect/{file_id}")
async def redirect_302(file_id: str):
    """
    302重定向到夸克直链

    Args:
        file_id: 文件ID

    Returns:
        302重定向响应
    """
    cookie = config.get_quark_cookie()

    if not cookie:
        raise HTTPException(status_code=400, detail="Cookie not configured")

    try:
        async with ProxyService(cookie=cookie) as service:
            redirect_url = await service.redirect_302(file_id)
            logger.info(f"302 redirect to: {redirect_url[:100]}...")
            return RedirectResponse(url=redirect_url, status_code=302)
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
        service = QuarkService(cookie=cookie)
        link = await service.get_transcoding_link(file_id)
        await service.close()

        logger.info(f"302 redirect to transcoding link: {link.url[:100]}...")
        return RedirectResponse(url=link.url, status_code=302)
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
        # 从配置获取Emby服务器地址
        emby_url = config.get("endpoints.0.emby_url", "http://localhost:8096")

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
    except Exception as e:
        logger.error(f"Failed to get cache stats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
