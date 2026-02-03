"""
资源搜索API（新功能）

集成search包的资源搜索功能
"""

from fastapi import APIRouter, HTTPException, Query
from app.services.search_service import ResourceSearchService
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/search", tags=["资源搜索"])


@router.get("")
async def search_resources(
    keyword: str = Query(..., description="搜索关键词"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=500, description="每页大小")
):
    """
    搜索资源

    仅搜索夸克网盘资源，按评分降序排序

    Args:
        keyword: 搜索关键词
        page: 页码
        page_size: 每页大小

    Returns:
        搜索结果列表（仅夸克网盘资源，按评分排序）
    """
    try:
        logger.info(f"[DEBUG] 搜索请求: keyword={keyword}")
        service = ResourceSearchService()
        result = await service.search(
            keyword=keyword,
            cloud_types=["quark"],  # 固定只搜索夸克网盘
            page=page,
            page_size=page_size,
            sort_by="score",  # 固定按评分排序
            sort_order="desc"  # 固定降序
        )

        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"搜索失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/filtered")
async def search_resources_filtered(
    keyword: str = Query(..., description="搜索关键词"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=500, description="每页大小")
):
    """
    带过滤条件的资源搜索（已简化）

    仅搜索夸克网盘资源，按评分降序排序

    Args:
        keyword: 搜索关键词
        page: 页码
        page_size: 每页大小

    Returns:
        搜索结果列表（仅夸克网盘资源，按评分排序）
    """
    try:
        service = ResourceSearchService()
        result = await service.search(
            keyword=keyword,
            cloud_types=["quark"],  # 固定只搜索夸克网盘
            page=page,
            page_size=page_size,
            sort_by="score",  # 固定按评分排序
            sort_order="desc"  # 固定降序
        )

        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"过滤搜索失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_search_status():
    """
    获取搜索服务状态

    返回搜索服务是否可用
    """
    from app.core.sdk_config import sdk_config
    return {
        "available": sdk_config.is_available(),
        "search_service": sdk_config.create_search_service() is not None
    }
