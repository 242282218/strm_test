"""
Emby API路由

参考: go-emby2openlist internal/service/emby/playbackinfo.go
支持PlaybackInfo Hook和302重定向
"""

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import RedirectResponse, JSONResponse
from app.services.emby_proxy_service import EmbyProxyService
from app.services.proxy_service import ProxyService
from app.core.config_manager import get_config
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/emby", tags=["Emby服务"])

# 获取配置管理器
config = get_config()


@router.get("/items/{item_id}/PlaybackInfo")
async def get_playback_info(
    item_id: str,
    request: Request,
    user_id: str = None,
    media_source_id: str = None
):
    """
    获取播放信息（Hook版本）

    参考: go-emby2openlist internal/service/emby/playbackinfo.go TransferPlaybackInfo

    功能:
    1. 拦截Emby PlaybackInfo请求
    2. 修改响应，强制DirectPlay/DirectStream
    3. 将DirectStreamUrl指向代理服务

    Args:
        item_id: 项目ID
        request: FastAPI请求对象
        user_id: 用户ID
        media_source_id: 媒体源ID

    Returns:
        Hook后的PlaybackInfo响应
    """
    try:
        # 从请求头获取API Key
        api_key = request.headers.get("X-Emby-Token")
        if not api_key:
            api_key = request.query_params.get("api_key")

        if not api_key:
            raise HTTPException(status_code=401, detail="Missing API key")

        # 获取Emby服务器地址
        emby_base_url = request.headers.get(
            "X-Emby-Server-Url",
            config.get("endpoints.0.emby_url", "http://localhost:8096")
        )

        # 获取代理服务基础URL
        proxy_base_url = request.headers.get(
            "X-Proxy-Server-Url",
            f"http://{request.headers.get('host', 'localhost:8000')}"
        )

        # 获取Cookie
        cookie = config.get_quark_cookie()
        if not cookie:
            raise HTTPException(status_code=400, detail="Cookie not configured")

        # 使用Emby代理服务
        async with EmbyProxyService(
            emby_base_url=emby_base_url,
            api_key=api_key,
            cookie=cookie,
            proxy_base_url=proxy_base_url
        ) as proxy_service:
            playback_info = await proxy_service.proxy_playback_info(
                item_id=item_id,
                user_id=user_id or "",
                media_source_id=media_source_id
            )

            return playback_info

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get playback info: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/items/{item_id}")
async def get_item(
    item_id: str,
    request: Request,
    user_id: str = None
):
    """
    获取项目信息

    参考: go-emby2openlist internal/service/emby/items.go

    Args:
        item_id: 项目ID
        request: FastAPI请求对象
        user_id: 用户ID

    Returns:
        项目信息
    """
    try:
        # 从请求头获取API Key
        api_key = request.headers.get("X-Emby-Token")
        if not api_key:
            api_key = request.query_params.get("api_key")

        if not api_key:
            raise HTTPException(status_code=401, detail="Missing API key")

        # 获取Emby服务器地址
        emby_base_url = request.headers.get(
            "X-Emby-Server-Url",
            config.get("endpoints.0.emby_url", "http://localhost:8096")
        )

        # 获取Cookie
        cookie = config.get_quark_cookie()
        if not cookie:
            raise HTTPException(status_code=400, detail="Cookie not configured")

        # 使用Emby代理服务
        async with EmbyProxyService(
            emby_base_url=emby_base_url,
            api_key=api_key,
            cookie=cookie
        ) as proxy_service:
            item_info = await proxy_service.proxy_items_request(
                item_id=item_id,
                user_id=user_id
            )

            return item_info

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get item info: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/videos/{item_id}/stream")
async def stream_video(
    item_id: str,
    request: Request,
    media_source_id: str = None,
    static: bool = False,
    filename: str = None
):
    """
    视频流端点（302重定向）

    参考: go-emby2openlist internal/service/emby/redirect.go

    功能:
    1. 接收Emby的视频流请求
    2. 解析STRM文件获取文件ID
    3. 获取夸克直链
    4. 302重定向到直链

    Args:
        item_id: 项目ID
        request: FastAPI请求对象
        media_source_id: 媒体源ID
        static: 是否静态文件
        filename: 文件名

    Returns:
        302重定向响应
    """
    try:
        # 获取Cookie
        cookie = config.get_quark_cookie()
        if not cookie:
            raise HTTPException(status_code=400, detail="Cookie not configured")

        # 从media_source_id提取文件ID
        # 假设media_source_id就是夸克文件ID
        file_id = media_source_id

        if not file_id:
            raise HTTPException(status_code=400, detail="Missing media_source_id")

        # 获取直链并302重定向
        async with ProxyService(cookie=cookie) as service:
            redirect_url = await service.redirect_302(file_id)
            logger.info(f"302 redirect for item {item_id} to: {redirect_url[:100]}...")
            return RedirectResponse(url=redirect_url, status_code=302)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to stream video: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/videos/{item_id}/master.m3u8")
async def get_master_playlist(
    item_id: str,
    request: Request,
    media_source_id: str = None
):
    """
    获取主播放列表（M3U8）

    用于转码播放

    Args:
        item_id: 项目ID
        request: FastAPI请求对象
        media_source_id: 媒体源ID

    Returns:
        M3U8播放列表
    """
    try:
        # 获取Cookie
        cookie = config.get_quark_cookie()
        if not cookie:
            raise HTTPException(status_code=400, detail="Cookie not configured")

        # 从media_source_id提取文件ID
        file_id = media_source_id

        if not file_id:
            raise HTTPException(status_code=400, detail="Missing media_source_id")

        # 返回M3U8播放列表
        # 这里可以实现更复杂的逻辑，如代理夸克的转码M3U8
        playlist = f"""#EXTM3U
#EXT-X-VERSION:3
#EXT-X-STREAM-INF:BANDWIDTH=8000000,RESOLUTION=1920x1080
/api/proxy/transcoding/{file_id}
"""

        return Response(
            content=playlist,
            media_type="application/vnd.apple.mpegurl",
            headers={
                "Content-Type": "application/vnd.apple.mpegurl",
                "Cache-Control": "no-cache"
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get master playlist: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy_emby_request(request: Request, path: str):
    """
    Emby反代（通用）

    将所有Emby请求转发到实际Emby服务器

    Args:
        request: FastAPI请求对象
        path: Emby路径

    Returns:
        Emby响应
    """
    try:
        # 获取Emby服务器地址
        emby_base_url = request.headers.get(
            "X-Emby-Server-Url",
            config.get("endpoints.0.emby_url", "http://localhost:8096")
        )

        # 构建目标URL
        target_url = f"{emby_base_url}/{path}"
        query_string = str(request.query_params)
        if query_string:
            target_url = f"{target_url}?{query_string}"

        logger.debug(f"Proxying Emby request: {request.method} {target_url}")

        # 这里可以实现完整的Emby反代逻辑
        # 包括请求转发、响应处理等

        return {
            "message": "Emby proxy endpoint",
            "method": request.method,
            "target_url": target_url,
            "path": path
        }

    except Exception as e:
        logger.error(f"Failed to proxy Emby request: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
