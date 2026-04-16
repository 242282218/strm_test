"""
资源搜索服务

集成pansou的HTTP API搜索功能，并应用quark_strm项目的评分系统
"""

import os
from typing import Any

import httpx

from app.core.logging import get_logger

from .quark_size_fetcher import get_size_fetcher
from .scoring import ScoringEngine


logger = get_logger(__name__)


class ResourceSearchService:
    """资源搜索服务 - 调用pansou HTTP API并应用评分"""

    def __init__(self):
        self._base_url = os.getenv("PANSOU_API_URL", "https://pansou.xzcccc.eu.org")
        self._timeout = 30.0
        self._scoring_engine = ScoringEngine()
        self._size_fetcher = get_size_fetcher()

    def _get_pansou_url(self, endpoint: str) -> str:
        """获取pansou API完整URL"""
        return f"{self._base_url}{endpoint}"

    def _transform_cloud_type(self, cloud_type: str) -> str:
        """转换网盘类型为pansou格式"""
        type_mapping = {
            "quark": "quark",
            "baidu": "baidu",
            "ali": "aliyun",
            "aliyun": "aliyun",
            "tianyi": "tianyi",
            "uc": "uc",
            "mobile": "mobile",
            "115": "115",
            "pikpak": "pikpak",
            "xunlei": "xunlei",
            "123": "123",
            "magnet": "magnet",
            "ed2k": "ed2k",
        }
        return type_mapping.get(cloud_type.lower(), cloud_type.lower())

    def _transform_pansou_result(self, pansou_data: dict[str, Any], keyword: str) -> dict[str, Any]:
        """将pansou返回结果转换为项目格式并计算评分"""
        merged_by_type = pansou_data.get("merged_by_type", {})
        results = []

        # 遍历按类型分组的链接
        for cloud_type, links in merged_by_type.items():
            for link in links:
                # 构建基础结果
                result_item = {
                    "id": f"{cloud_type}_{hash(link.get('url', ''))}",
                    "title": link.get("note", ""),
                    "content": link.get("note", ""),
                    "source": link.get("source", "unknown"),
                    "channel": "",
                    "pub_date": link.get("datetime"),
                    "cloud_type": cloud_type,
                    "cloud_links": [
                        {
                            "type": cloud_type,
                            "url": link.get("url", ""),
                            "password": link.get("password", ""),
                            "title": link.get("note", ""),
                        }
                    ],
                }

                # 使用评分引擎计算评分
                score_detail = self._scoring_engine.score(keyword, result_item)

                # 合并评分到结果
                result_item.update(
                    {
                        "score": score_detail["score"],
                        "confidence": score_detail["confidence"],
                        "quality": score_detail["quality"],
                        "popularity": score_detail["popularity"],
                        "freshness": score_detail["freshness"],
                        "tags": score_detail["tags"],
                    }
                )

                results.append(result_item)

        return {"results": results, "total": len(results), "merged_by_type": merged_by_type}

    async def _apply_size_filter(self, results: list[dict[str, Any]], min_size_bytes: int) -> list[dict[str, Any]]:
        """
        应用大小过滤（仅对评分前20的夸克网盘资源）

        Args:
            results: 结果列表
            min_size_bytes: 最小文件大小（字节）

        Returns:
            过滤后的结果
        """
        if min_size_bytes <= 0:
            return results

        # 按评分排序，只取前20个夸克资源获取大小
        quark_results = []
        for result in results:
            for link in result.get("cloud_links", []):
                if link.get("type") == "quark":
                    quark_results.append(result)
                    break

        # 按评分排序，取前20
        quark_results.sort(key=lambda x: x.get("score", 0), reverse=True)
        top_quark_results = quark_results[:20]

        # 收集前20个夸克资源的分享链接
        quark_items = []
        for result in top_quark_results:
            for link in result.get("cloud_links", []):
                if link.get("type") == "quark":
                    share_key = self._size_fetcher.extract_share_key(link.get("url", ""))
                    if share_key:
                        quark_items.append(
                            {
                                "url": link.get("url", ""),
                                "password": link.get("password", ""),
                                "result_id": result.get("id"),
                                "share_key": share_key,
                            }
                        )

        # 批量获取夸克分享的大小
        size_map = {}
        if quark_items:
            logger.info(f"正在获取评分前20的 {len(quark_items)} 个夸克分享的大小信息...")
            size_map = await self._size_fetcher.batch_get_sizes(quark_items, min_size_bytes)
            logger.info(f"成功获取 {len(size_map)} 个分享的大小")

        # 过滤结果
        filtered_results = []
        for result in results:
            # 非夸克资源直接保留
            cloud_types = {link.get("type") for link in result.get("cloud_links", [])}
            if "quark" not in cloud_types:
                filtered_results.append(result)
                continue

            # 检查是否在前20名内
            is_top20 = result in top_quark_results

            # 夸克资源检查大小
            has_valid_size = False
            result_size = 0

            for link in result.get("cloud_links", []):
                if link.get("type") == "quark":
                    share_key = self._size_fetcher.extract_share_key(link.get("url", ""))
                    if share_key and share_key in size_map:
                        size = size_map[share_key]
                        if size >= min_size_bytes:
                            has_valid_size = True
                            result_size = size
                            # 添加大小信息到链接
                            link["size"] = size
                            link["size_human"] = self._size_fetcher.format_size(size)

            if is_top20:
                # 前20名：成功获取大小且满足条件的保留
                if has_valid_size:
                    # 添加大小信息到结果
                    result["file_size"] = result_size
                    result["file_size_human"] = self._size_fetcher.format_size(result_size)
                    filtered_results.append(result)
                elif not size_map:
                    # 无法获取任何大小时，默认保留前20名
                    filtered_results.append(result)
                # 获取到大小但不满足1GB的，过滤掉
            else:
                # 非前20名默认保留（不过滤）
                filtered_results.append(result)

        return filtered_results

    def _sort_results(self, results: list[dict[str, Any]], sort_by: str | None = None) -> list[dict[str, Any]]:
        """
        排序结果

        Args:
            results: 结果列表
            sort_by: 排序方式 (score, confidence, quality, time, size)

        Returns:
            排序后的结果
        """
        if not sort_by or sort_by == "score":
            # 默认按综合评分排序
            return sorted(results, key=lambda x: x.get("score", 0), reverse=True)
        if sort_by == "confidence":
            return sorted(results, key=lambda x: x.get("confidence", 0), reverse=True)
        if sort_by == "quality":
            return sorted(results, key=lambda x: x.get("quality", 0), reverse=True)
        if sort_by == "time":
            return sorted(results, key=lambda x: x.get("pub_date", ""), reverse=True)
        if sort_by == "size":
            return sorted(results, key=lambda x: x.get("file_size", 0), reverse=True)
        return results

    async def search(
        self,
        keyword: str,
        cloud_types: list[str] | None = None,
        sources: list[str] | None = None,
        page: int = 1,
        page_size: int = 20,
        sort_by: str | None = None,
        sort_order: str | None = None,
        min_file_size: int = 0,
    ) -> dict[str, Any]:
        """
        搜索资源 - 调用pansou API并应用评分

        Args:
            keyword: 搜索关键词
            cloud_types: 网盘类型列表 ['quark', 'baidu', 'ali']，默认 ['quark']
            sources: 搜索源列表（pansou中对应channels）
            page: 页码
            page_size: 每页大小
            sort_by: 排序方式 (score, confidence, quality, time, size)
            sort_order: 排序顺序 (asc, desc)
            min_file_size: 最小文件大小（字节），默认0不过滤，建议1GB=1073741824

        Returns:
            搜索结果
        """
        try:
            if not keyword or not str(keyword).strip():
                return {
                    "results": [],
                    "total": 0,
                    "page": page,
                    "page_size": page_size,
                    "has_more": False,
                    "error": "keyword cannot be empty",
                }

            # 默认只搜索夸克网盘
            if cloud_types is None:
                cloud_types = ["quark"]

            # 构建pansou请求参数
            params = {
                "kw": keyword,
                "res": "merged_by_type",  # 返回按类型分组的结果
                "src": "all",  # 搜索所有来源
                "refresh": True,  # 强制刷新缓存，避免返回旧结果
            }

            # 添加频道参数（如果指定了sources）
            if sources:
                params["channels"] = ",".join(sources)

            # 添加网盘类型过滤
            pansou_types = [self._transform_cloud_type(ct) for ct in cloud_types]
            params["cloud_types"] = ",".join(pansou_types)

            async with httpx.AsyncClient(timeout=self._timeout, follow_redirects=True) as client:
                # 使用 GET 方式请求（POST 方式有 bug 会忽略 kw 参数）
                response = await client.get(self._get_pansou_url("/api/search"), params=params)
                response.raise_for_status()
                pansou_response = response.json()

            # 检查pansou响应
            if pansou_response.get("code") != 0:
                error_msg = pansou_response.get("message", "未知错误")
                logger.error(f"pansou搜索失败: {error_msg}")
                return {
                    "results": [],
                    "total": 0,
                    "page": page,
                    "page_size": page_size,
                    "has_more": False,
                    "error": f"pansou: {error_msg}",
                }

            # 转换结果并计算评分
            data = pansou_response.get("data", {})
            transformed = self._transform_pansou_result(data, keyword)

            # 应用大小过滤（仅对夷克网盘）
            all_results = await self._apply_size_filter(transformed["results"], min_file_size)

            # 排序结果
            all_results = self._sort_results(all_results, sort_by)

            # 分页处理
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size
            paginated_results = all_results[start_idx:end_idx]

            total = len(all_results)
            has_more = end_idx < total

            logger.info(f"搜索成功: keyword={keyword}, total={total}, page={page}")

            return {
                "results": paginated_results,
                "total": total,
                "page": page,
                "page_size": page_size,
                "has_more": has_more,
                "merged_by_type": transformed.get("merged_by_type", {}),
                "filters": {"cloud_types": cloud_types, "min_file_size": min_file_size if min_file_size > 0 else None},
            }

        except httpx.ConnectError as e:
            logger.error(f"无法连接到pansou服务: {e}")
            return {
                "results": [],
                "total": 0,
                "page": page,
                "page_size": page_size,
                "has_more": False,
                "error": "pansou服务未启动，请检查PANSOU_API_URL配置",
            }
        except Exception as e:
            import traceback

            logger.error(f"搜索失败: {e}\n{traceback.format_exc()}")
            return {"results": [], "total": 0, "page": page, "page_size": page_size, "has_more": False, "error": str(e)}

    async def search_with_filters(
        self,
        keyword: str,
        min_score: float = 0.5,
        min_confidence: float = 0.6,
        cloud_types: list[str] | None = None,
        page: int = 1,
        page_size: int = 20,
        sort_by: str | None = None,
        sort_order: str | None = None,
        min_file_size: int = 0,
    ) -> dict[str, Any]:
        """
        带过滤条件的搜索

        Args:
            keyword: 搜索关键词
            min_score: 最低综合评分
            min_confidence: 最低置信度
            cloud_types: 网盘类型列表，默认 ['quark']
            page: 页码
            page_size: 每页大小
            sort_by: 排序方式
            sort_order: 排序顺序
            min_file_size: 最小文件大小（字节）

        Returns:
            过滤后的搜索结果
        """
        # 默认只搜索夸克网盘
        if cloud_types is None:
            cloud_types = ["quark"]

        # 调用基础搜索
        result = await self.search(
            keyword=keyword,
            cloud_types=cloud_types,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
            min_file_size=min_file_size,
        )

        if "error" in result:
            return result

        # 过滤结果
        filtered_results = [
            r for r in result["results"] if r.get("score", 0) >= min_score and r.get("confidence", 0) >= min_confidence
        ]

        return {
            "results": filtered_results,
            "total": len(filtered_results),
            "page": result["page"],
            "page_size": result["page_size"],
            "has_more": result["has_more"],
            "merged_by_type": result.get("merged_by_type", {}),
            "filters": {
                "min_score": min_score,
                "min_confidence": min_confidence,
                "min_file_size": min_file_size if min_file_size > 0 else None,
                "cloud_types": cloud_types,
                "applied": True,
            },
        }
