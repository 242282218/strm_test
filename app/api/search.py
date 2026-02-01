"""
资源搜索API（新功能）

集成search包的资源搜索功能
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from app.services.search_service import ResourceSearchService
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/search", tags=["资源搜索"])


@router.get("")
async def search_resources(
    keyword: str = Query(..., description="搜索关键词"),
    cloud_types: Optional[List[str]] = Query(None, description="网盘类型筛选，如: quark, baidu, ali"),
    sources: Optional[List[str]] = Query(None, description="搜索源筛选，如: telegram, quark_api, net_search"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页大小"),
    sort_by: Optional[str] = Query(None, description="排序方式: time, size, quality"),
    sort_order: Optional[str] = Query(None, description="排序顺序: asc, desc")
):
    """
    搜索资源

    支持多网盘类型和多搜索源的资源搜索

    Args:
        keyword: 搜索关键词
        cloud_types: 网盘类型筛选
        sources: 搜索源筛选
        page: 页码
        page_size: 每页大小
        sort_by: 排序方式
        sort_order: 排序顺序

    Returns:
        搜索结果列表
    """
    try:
        service = ResourceSearchService()
        result = await service.search(
            keyword=keyword,
            cloud_types=cloud_types,
            sources=sources,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order
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
    min_score: float = Query(0.5, ge=0, le=1, description="最低综合评分"),
    min_confidence: float = Query(0.6, ge=0, le=1, description="最低置信度"),
    cloud_types: Optional[List[str]] = Query(None, description="网盘类型筛选"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页大小"),
    sort_by: Optional[str] = Query(None, description="排序方式: time, size, quality"),
    sort_order: Optional[str] = Query(None, description="排序顺序: asc, desc")
):
    """
    带过滤条件的资源搜索

    支持按评分和置信度过滤搜索结果

    Args:
        keyword: 搜索关键词
        min_score: 最低综合评分 (0-1)
        min_confidence: 最低置信度 (0-1)
        cloud_types: 网盘类型筛选
        page: 页码
        page_size: 每页大小
        sort_by: 排序方式
        sort_order: 排序顺序

    Returns:
        过滤后的搜索结果
    """
    try:
        service = ResourceSearchService()
        result = await service.search_with_filters(
            keyword=keyword,
            min_score=min_score,
            min_confidence=min_confidence,
            cloud_types=cloud_types,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order
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
