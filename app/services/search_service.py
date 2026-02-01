"""
资源搜索服务

集成search包的资源搜索功能
"""

from typing import List, Dict, Any, Optional
from app.core.sdk_config import sdk_config
from app.core.logging import get_logger

logger = get_logger(__name__)


class ResourceSearchService:
    """资源搜索服务"""

    def __init__(self):
        self._search_service = None

    def _check_sdk(self) -> bool:
        """检查SDK是否可用"""
        if not sdk_config.is_available():
            logger.error("search SDK不可用，请检查SDK路径配置")
            return False
        return True

    def _get_service(self):
        """获取搜索服务实例"""
        if self._search_service is None:
            self._search_service = sdk_config.create_search_service()
        return self._search_service

    async def search(
        self,
        keyword: str,
        cloud_types: Optional[List[str]] = None,
        sources: Optional[List[str]] = None,
        page: int = 1,
        page_size: int = 20,
        sort_by: Optional[str] = None,
        sort_order: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        搜索资源

        Args:
            keyword: 搜索关键词
            cloud_types: 网盘类型列表 ['quark', 'baidu', 'ali']
            sources: 搜索源列表 ['telegram', 'quark_api', 'net_search']
            page: 页码
            page_size: 每页大小
            sort_by: 排序方式
            sort_order: 排序顺序

        Returns:
            搜索结果
        """
        if not self._check_sdk():
            return {
                "results": [],
                "total": 0,
                "page": page,
                "page_size": page_size,
                "has_more": False,
                "error": "SDK不可用"
            }

        try:
            from packages.search.core.models import SearchQuery, CloudType

            service = self._get_service()
            if service is None:
                return {
                    "results": [],
                    "total": 0,
                    "page": page,
                    "page_size": page_size,
                    "has_more": False,
                    "error": "搜索服务初始化失败"
                }

            # 构建查询
            query = SearchQuery(
                keyword=keyword,
                cloud_types=[CloudType(ct) for ct in cloud_types] if cloud_types else None,
                sources=sources,
                page=page,
                page_size=page_size,
                sort_by=sort_by or 'time',
                sort_order=sort_order or 'desc',
                enable_scoring=True,
                enable_cache=True
            )

            response = await service.search(query)

            logger.info(f"搜索响应: total={response.total}, page={response.page}, results_count={len(response.results)}")

            # 转换结果格式
            results = []
            for item in response.results:
                results.append({
                    "id": item.id,
                    "title": item.title,
                    "content": item.content,
                    "source": item.source,
                    "channel": item.channel,
                    "pub_date": item.pub_date.isoformat() if item.pub_date else None,
                    "cloud_links": [
                        {
                            "type": link.cloud_type.value,
                            "url": link.url,
                            "password": link.extraction_code,
                            "title": item.title
                        }
                        for link in item.cloud_links
                    ],
                    "score": item.score,
                    "confidence": item.confidence,
                    "quality": item.quality,
                    "popularity": item.popularity,
                    "freshness": item.freshness
                })

            return {
                "results": results,
                "total": response.total,
                "page": response.page,
                "page_size": response.page_size,
                "has_more": response.page < response.total_pages
            }

        except Exception as e:
            logger.error(f"搜索失败: {e}")
            return {
                "results": [],
                "total": 0,
                "page": page,
                "page_size": page_size,
                "has_more": False,
                "error": str(e)
            }

    async def search_with_filters(
        self,
        keyword: str,
        min_score: float = 0.5,
        min_confidence: float = 0.6,
        cloud_types: Optional[List[str]] = None,
        page: int = 1,
        page_size: int = 20,
        sort_by: Optional[str] = None,
        sort_order: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        带过滤条件的搜索

        Args:
            keyword: 搜索关键词
            min_score: 最低综合评分
            min_confidence: 最低置信度
            cloud_types: 网盘类型列表
            page: 页码
            page_size: 每页大小
            sort_by: 排序方式
            sort_order: 排序顺序

        Returns:
            过滤后的搜索结果
        """
        result = await self.search(
            keyword=keyword,
            cloud_types=cloud_types,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order
        )

        if "error" in result:
            return result

        # 过滤结果
        filtered_results = [
            r for r in result["results"]
            if (r.get("score", 0) >= min_score and
                r.get("confidence", 0) >= min_confidence)
        ]

        return {
            "results": filtered_results,
            "total": len(filtered_results),
            "page": page,
            "page_size": page_size,
            "has_more": result.get("has_more", False),
            "filters": {
                "min_score": min_score,
                "min_confidence": min_confidence
            }
        }
