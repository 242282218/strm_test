"""
基于SDK的夸克API路由（新API）

提供与现有API兼容的接口，同时支持SDK新功能
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional
from app.services.quark_sdk_service import QuarkSDKService
from app.core.dependencies import get_quark_cookie, require_api_key
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/quark-sdk", tags=["夸克SDK服务"])


async def get_service(cookie: str = Depends(get_quark_cookie)):
    """获取服务实例"""
    service = QuarkSDKService(cookie=cookie)
    try:
        yield service
    finally:
        await service.close()


@router.get("/files/{parent}")
async def get_files(
    parent: str,
    page_size: int = Query(100, ge=1, le=500),
    only_video: bool = False,
    service: QuarkSDKService = Depends(get_service)
):
    """
    获取文件列表（SDK版本）

    Args:
        parent: 父目录ID
        page_size: 每页大小
        only_video: 是否只获取视频文件
    """
    try:
        files = await service.get_files(
            parent=parent,
            page_size=page_size,
            only_video=only_video
        )
        return {"files": files, "count": len(files)}
    except Exception as e:
        logger.error(f"SDK获取文件列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/link/{file_id}")
async def get_download_link(
    file_id: str,
    service: QuarkSDKService = Depends(get_service)
):
    """
    获取下载直链（SDK版本）

    Args:
        file_id: 文件ID
    """
    try:
        link = await service.get_download_link(file_id)
        if link is None:
            raise HTTPException(status_code=404, detail="无法获取下载链接")
        return link
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"SDK获取下载链接失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/transcoding/{file_id}")
async def get_transcoding_link(
    file_id: str,
    service: QuarkSDKService = Depends(get_service)
):
    """
    获取转码直链（SDK版本）

    Args:
        file_id: 文件ID
    """
    try:
        link = await service.get_transcoding_link(file_id)
        if link is None:
            raise HTTPException(status_code=404, detail="无法获取转码链接")
        return link
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"SDK获取转码链接失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/share")
async def create_share(
    file_ids: List[str],
    title: Optional[str] = None,
    password: Optional[str] = None,
    _auth: None = Depends(require_api_key),
    service: QuarkSDKService = Depends(get_service)
):
    """
    创建分享（新功能）

    Args:
        file_ids: 文件ID列表
        title: 分享标题
        password: 分享密码
    """
    try:
        result = await service.create_share(file_ids, title, password)
        if result is None:
            raise HTTPException(status_code=500, detail="创建分享失败")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"SDK创建分享失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/transfer")
async def save_share(
    share_key: str,
    file_ids: List[str],
    target_folder: str = "0",
    password: Optional[str] = None,
    _auth: None = Depends(require_api_key),
    service: QuarkSDKService = Depends(get_service)
):
    """
    转存分享文件（新功能）

    Args:
        share_key: 分享key
        file_ids: 要转存的文件ID列表
        target_folder: 目标文件夹ID
        password: 分享密码
    """
    try:
        result = await service.save_share(share_key, file_ids, target_folder, password)
        if result is None:
            raise HTTPException(status_code=500, detail="转存失败")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"SDK转存分享失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search")
async def search_files(
    keyword: str,
    parent: str = "0",
    page_size: int = Query(50, ge=1, le=100),
    service: QuarkSDKService = Depends(get_service)
):
    """
    搜索文件（新功能）

    Args:
        keyword: 搜索关键词
        parent: 父目录ID
        page_size: 每页大小
    """
    try:
        files = await service.search_files(keyword, parent, page_size)
        return {"files": files, "count": len(files)}
    except Exception as e:
        logger.error(f"SDK搜索文件失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_sdk_status():
    """
    获取SDK状态

    返回SDK是否可用
    """
    from app.core.sdk_config import sdk_config
    return {
        "available": sdk_config.is_available(),
        "sdk_path": str(sdk_config.__class__.__module__)
    }
