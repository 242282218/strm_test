"""
资源搜索API（新功能）

集成search包的资源搜索功能
"""

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.core.logging import get_logger
from app.services.search_service import ResourceSearchService


logger = get_logger(__name__)
router = APIRouter(prefix="/api/search", tags=["资源搜索"])


def _normalize_search_error(result: dict[str, Any], page: int, page_size: int) -> dict[str, Any]:
    """Keep third-party search failures recoverable for the UI."""
    if "error" not in result:
        return result

    normalized: dict[str, Any] = {
        "results": result.get("results", []),
        "total": result.get("total", 0),
        "page": result.get("page", page),
        "page_size": result.get("page_size", page_size),
        "has_more": result.get("has_more", False),
        "error": result["error"],
    }

    if "merged_by_type" in result:
        normalized["merged_by_type"] = result["merged_by_type"]
    if "filters" in result:
        normalized["filters"] = result["filters"]

    return normalized


@router.get("")
async def search_resources(
    keyword: str = Query(..., description="搜索关键词"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=500, description="每页大小"),
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
            sort_order="desc",  # 固定降序
        )

        return _normalize_search_error(result, page, page_size)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"搜索失败: {e}")
        raise HTTPException(status_code=500, detail="搜索失败")


@router.get("/filtered")
async def search_resources_filtered(
    keyword: str = Query(..., description="搜索关键词"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=500, description="每页大小"),
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
            sort_order="desc",  # 固定降序
        )

        return _normalize_search_error(result, page, page_size)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"过滤搜索失败: {e}")
        raise HTTPException(status_code=500, detail="过滤搜索失败")


@router.get("/status")
async def get_search_status():
    """
    获取搜索服务状态

    返回搜索服务是否可用
    """
    from app.core.sdk_config import sdk_config

    return {"available": sdk_config.is_available(), "search_service": sdk_config.create_search_service() is not None}
