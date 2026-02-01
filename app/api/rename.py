"""
媒体重命名API（新功能）

集成rename包的媒体重命名功能
"""

from fastapi import APIRouter, HTTPException, Body
from typing import List, Optional
from app.services.rename_service import MediaRenameService
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/rename", tags=["媒体重命名"])


@router.post("/preview")
async def preview_rename(
    path: str = Body(..., description="媒体文件或目录路径"),
    recursive: bool = Body(True, description="是否递归处理子目录")
):
    """
    预览重命名

    分析媒体文件并生成重命名预览，不会实际执行重命名操作

    Args:
        path: 媒体文件或目录路径
        recursive: 是否递归处理子目录

    Returns:
        重命名任务列表和进度信息
    """
    try:
        service = MediaRenameService()
        result = await service.preview_rename(path, recursive)

        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"预览重命名失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/execute")
async def execute_rename(
    path: str = Body(..., description="媒体文件或目录路径"),
    selected_tasks: Optional[List[str]] = Body(None, description="要执行的任务源路径列表，None表示全部"),
    recursive: bool = Body(True, description="是否递归处理子目录")
):
    """
    执行重命名

    实际执行媒体文件重命名操作

    Args:
        path: 媒体文件或目录路径
        selected_tasks: 要执行的任务源路径列表，None表示全部执行
        recursive: 是否递归处理子目录

    Returns:
        执行结果，包含成功和失败的任务列表
    """
    try:
        service = MediaRenameService()
        result = await service.execute_rename(path, selected_tasks, recursive)

        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"执行重命名失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/info")
async def get_media_info(
    file_path: str = Body(..., description="媒体文件路径")
):
    """
    获取媒体文件信息

    解析单个媒体文件并返回详细信息

    Args:
        file_path: 媒体文件路径

    Returns:
        媒体文件信息，包括类型、标题、年份、分辨率等
    """
    try:
        service = MediaRenameService()
        result = await service.get_media_info(file_path)

        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取媒体信息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_rename_status():
    """
    获取重命名服务状态

    返回重命名服务是否可用
    """
    from app.core.sdk_config import sdk_config
    return {
        "available": sdk_config.is_available(),
        "rename_service": sdk_config.create_rename_engine() is not None
    }
