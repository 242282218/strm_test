"""
夸克API路由
"""

from fastapi import APIRouter, HTTPException, Depends
from app.services.quark_service import QuarkService
from app.services.strm_generator import generate_strm_from_quark
from app.core.config_manager import get_config
from app.core.logging import get_logger
from app.core.dependencies import get_quark_cookie, get_only_video_flag, get_root_id

logger = get_logger(__name__)
router = APIRouter(prefix="/api/quark", tags=["夸克服务"])

# 获取配置管理器
config = get_config()


@router.get("/files/{parent}")
async def get_files(
    parent: str,
    cookie: str = None,
    only_video: bool = None,
    _cookie: str = Depends(get_quark_cookie),
    _only_video: bool = Depends(get_only_video_flag)
):
    """
    获取文件列表

    参考: OpenList quark_uc/util.go:69-111

    Args:
        parent: 父目录ID
        cookie: 夸克Cookie（可选，默认从配置文件读取）
        only_video: 是否只获取视频文件（可选，默认从配置文件读取）

    Returns:
        文件列表
    """
    try:
        service = QuarkService(cookie=_cookie)
        files = await service.get_files(parent, only_video=only_video or _only_video)
        await service.close()
        return {"files": files, "count": len(files)}
    except Exception as e:
        logger.error(f"Failed to get files: {str(e)}")
        raise


@router.get("/link/{file_id}")
async def get_download_link(
    file_id: str,
    cookie: str = None,
    _cookie: str = Depends(get_quark_cookie)
):
    """
    获取下载直链

    参考: OpenList quark_uc/util.go:113-137

    Args:
        file_id: 文件ID
        cookie: 夸克Cookie（可选，默认从配置文件读取）

    Returns:
        下载链接信息
    """
    try:
        service = QuarkService(cookie=_cookie)
        link = await service.get_download_link(file_id)
        await service.close()
        return {"url": link.url, "headers": link.headers}
    except Exception as e:
        logger.error(f"Failed to get download link: {str(e)}")
        raise


@router.get("/transcoding/{file_id}")
async def get_transcoding_link(file_id: str, cookie: str = None):
    """
    获取转码直链

    参考: OpenList quark_uc/util.go:139-168

    Args:
        file_id: 文件ID
        cookie: 夸克Cookie（可选，默认从配置文件读取）

    Returns:
        转码链接信息
    """
    cookie = cookie or config.get_quark_cookie()

    if not cookie:
        raise HTTPException(status_code=400, detail="Cookie is required. Please provide cookie parameter or set it in config.yaml")

    try:
        service = QuarkService(cookie=cookie)
        link = await service.get_transcoding_link(file_id)
        await service.close()
        return {"url": link.url, "headers": link.headers, "content_length": link.content_length}
    except Exception as e:
        logger.error(f"Failed to get transcoding link: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/link/test")
async def test_link_endpoint():
    """
    测试直链获取端点

    用于集成测试
    """
    try:
        # 返回测试数据
        return {
            "url": "http://example.com/test.mp4",
            "headers": {
                "Cookie": "test_cookie",
                "Referer": "https://pan.quark.cn/"
            },
            "test": True
        }
    except Exception as e:
        logger.error(f"Failed to test link endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/config")
async def get_quark_config():
    """
    获取夸克配置信息

    返回配置信息（不包含敏感数据）
    """
    try:
        quark_config = config.get_quark_config()
        # 隐藏敏感信息
        safe_config = {
            "referer": quark_config.get("referer", "https://pan.quark.cn/"),
            "root_id": quark_config.get("root_id", "0"),
            "only_video": quark_config.get("only_video", True),
            "cookie_configured": bool(quark_config.get("cookie", ""))
        }
        return safe_config
    except Exception as e:
        logger.error(f"Failed to get quark config: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sync")
async def sync_quark_files(
    cookie: str = None,
    root_id: str = None,
    output_dir: str = "./strm",
    only_video: bool = None
):
    """
    同步夸克文件到STRM

    扫描夸克网盘文件并生成STRM文件

    Args:
        cookie: 夸克Cookie（可选，默认从配置文件读取）
        root_id: 根目录ID（可选，默认从配置文件读取）
        output_dir: STRM文件输出目录（可选，默认./strm）
        only_video: 是否只处理视频文件（可选，默认从配置文件读取）

    Returns:
        同步结果
    """
    cookie = cookie or config.get_quark_cookie()
    root_id = root_id or config.get_quark_root_id()
    if only_video is None:
        only_video = config.get_quark_only_video()

    if not cookie:
        raise HTTPException(status_code=400, detail="Cookie is required. Please provide cookie parameter or set it in config.yaml")

    try:
        # 调用STRM生成器
        result = await generate_strm_from_quark(
            cookie=cookie,
            output_dir=output_dir,
            root_id=root_id,
            only_video=only_video
        )

        return {
            "message": "Sync completed",
            "root_id": root_id,
            "output_dir": output_dir,
            "result": result
        }
    except Exception as e:
        logger.error(f"Failed to sync quark files: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
