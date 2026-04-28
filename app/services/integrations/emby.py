import asyncio
import os
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.core.db_utils import AsyncBatchProcessor, batch_get_models_by_ids
from app.core.http_pool import ClientType, get_http_pool
from app.core.logging import get_logger
from app.models.emby import EmbyLibrary, EmbyMediaItem
from app.services.config_service import get_config_service
from app.services.cron_service import get_cron_service
from app.services.emby_api_client import EmbyAPIClient
from app.services.notification_service import NotificationType, get_notification_service
from app.utils.strm_url import (
    extract_file_id_from_proxy_url,
    extract_file_id_from_strm_content,
    read_strm_file_content,
)


logger = get_logger(__name__)
config_service = get_config_service()


def _resolve_legacy_endpoint_emby_field(app_config: object, field_name: str) -> str:
    endpoints = getattr(app_config, "endpoints", None) or []
    if not endpoints:
        return ""
    return str(getattr(endpoints[0], field_name, "") or "").strip()


def _resolve_effective_settings(app_config: object) -> dict[str, Any]:
    emby_cfg = getattr(app_config, "emby", None)
    refresh_cfg = getattr(emby_cfg, "refresh", None)

    global_enabled = bool(getattr(emby_cfg, "enabled", False))
    global_url = str(getattr(emby_cfg, "url", "") or "").strip()
    global_api_key = str(getattr(emby_cfg, "api_key", "") or "").strip()
    global_timeout = int(getattr(emby_cfg, "timeout", getattr(app_config, "timeout", 30)) or 30)
    notify_on_complete = bool(getattr(emby_cfg, "notify_on_complete", True))

    refresh_on_strm = bool(getattr(refresh_cfg, "on_strm_generate", True))
    refresh_on_rename = bool(getattr(refresh_cfg, "on_rename", True))
    refresh_cron = getattr(refresh_cfg, "cron", None)
    if isinstance(refresh_cron, str) and not refresh_cron.strip():
        refresh_cron = None
    library_ids = getattr(refresh_cfg, "library_ids", []) or []
    if not isinstance(library_ids, list):
        library_ids = []

    legacy_url = _resolve_legacy_endpoint_emby_field(app_config, "emby_url")
    legacy_api_key = _resolve_legacy_endpoint_emby_field(app_config, "emby_api_key")
    has_global_credentials = bool(global_url and global_api_key)
    has_legacy_credentials = bool(legacy_url and legacy_api_key)

    if global_enabled and has_global_credentials:
        enabled = True
        url = global_url
        api_key = global_api_key
    elif has_legacy_credentials and not has_global_credentials:
        enabled = True
        url = legacy_url
        api_key = legacy_api_key
    else:
        enabled = False
        url = global_url or legacy_url
        api_key = global_api_key or legacy_api_key

    return {
        "enabled": enabled,
        "url": url.rstrip("/"),
        "api_key": api_key,
        "timeout": global_timeout,
        "notify_on_complete": notify_on_complete,
        "refresh": {
            "on_strm_generate": refresh_on_strm,
            "on_rename": refresh_on_rename,
            "cron": refresh_cron.strip() if isinstance(refresh_cron, str) else None,
            "library_ids": [str(item) for item in library_ids if str(item).strip()],
        },
    }


@dataclass
class RefreshResult:
    success: bool
    library_id: str | None
    message: str
    timestamp: datetime


class EmbyService:
    """Emby集成服务"""

    _instance = None

    def __init__(self):
        self.notification_service = get_notification_service()
        self._sync_lock = asyncio.Lock()
        self._refresh_lock = asyncio.Lock()
        self._refresh_history = deque(maxlen=100)
        # 连接池客户端
        self._pool = None
        self._httpx_client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """获取 HTTP 客户端（来自连接池）"""
        if self._httpx_client is None or self._httpx_client.is_closed:
            if self._pool is None:
                self._pool = await get_http_pool()
            self._httpx_client = await self._pool.get_client(ClientType.EMBY)
        return self._httpx_client

    @property
    def is_enabled(self) -> bool:
        """检查Emby服务是否启用"""
        settings = self._get_effective_settings()
        return bool(settings["enabled"] and settings["url"] and settings["api_key"])

    @classmethod
    def get_instance(cls):
        if not cls._instance:
            cls._instance = EmbyService()
        return cls._instance

    def _get_effective_settings(self) -> dict[str, Any]:
        """
        获取Emby有效配置（兼容旧版 endpoints.0.emby_url / emby_api_key）
        """
        return _resolve_effective_settings(config_service.get_config())

    def _get_candidate_api_base_urls(self, url: str) -> list[str]:
        """
        返回可能的Emby API base url列表：
        - 对于 http://host:port 这种，优先尝试 host:port，再尝试 host:port/emby
        - 如果配置已包含 /emby，则仅使用配置值
        """
        base = (url or "").rstrip("/")
        if not base:
            return []
        # 已显式包含 /emby 路径则不再追加
        if base.lower().endswith("/emby") or "/emby/" in base.lower():
            return [base]
        return [base, f"{base}/emby"]

    async def _request_json(
        self, method: str, endpoint: str, *, url: str, api_key: str, timeout: int
    ) -> dict[str, Any]:
        """使用连接池发送 HTTP 请求"""
        if not endpoint.startswith("/"):
            endpoint = f"/{endpoint}"

        last_error: Exception | None = None
        client = await self._get_client()

        for base in self._get_candidate_api_base_urls(url):
            try:
                params = {"api_key": api_key}
                headers = {"Accept": "application/json", "Content-Type": "application/json"}

                if method.upper() == "GET":
                    response = await client.get(f"{base}{endpoint}", params=params, headers=headers, timeout=timeout)
                elif method.upper() == "POST":
                    response = await client.post(f"{base}{endpoint}", params=params, headers=headers, timeout=timeout)
                else:
                    response = await client.request(
                        method, f"{base}{endpoint}", params=params, headers=headers, timeout=timeout
                    )

                if response.status_code in (200, 204):
                    content = response.content
                    if content:
                        return response.json()
                    return {"status": "ok"}
                text = response.text
                raise RuntimeError(f"Emby API error [{response.status_code}]: {text[:200]}")
            except Exception as e:
                last_error = e
                continue

        raise last_error or RuntimeError("Emby API request failed")

    def _get_api_client(self) -> EmbyAPIClient:
        """获取API客户端"""
        settings = self._get_effective_settings()
        return EmbyAPIClient(
            settings["url"] or "http://localhost:8096", settings["api_key"], timeout=settings["timeout"]
        )

    async def test_connection(
        self, *, url: str | None = None, api_key: str | None = None, timeout: int | None = None
    ) -> dict[str, Any]:
        """测试Emby连接，返回服务器信息"""
        settings = self._get_effective_settings()
        test_url = (url or settings["url"] or "").strip()
        test_key = (api_key or settings["api_key"] or "").strip()
        request_timeout = int(timeout or settings["timeout"] or 30)

        if not test_url or not test_key:
            return {"success": False, "message": "Emby配置不完整", "server_info": None}

        try:
            data = await self._request_json(
                "GET",
                "/System/Info",
                url=test_url,
                api_key=test_key,
                timeout=request_timeout,
            )
            return {
                "success": True,
                "message": "连接成功",
                "server_info": {
                    "server_name": data.get("ServerName", "Unknown"),
                    "version": data.get("Version", "Unknown"),
                    "operating_system": data.get("OperatingSystem", "Unknown"),
                },
            }
        except Exception as e:
            return {"success": False, "message": f"连接失败: {e!s}", "server_info": None}

    async def get_libraries(self) -> list[dict[str, Any]]:
        """获取媒体库列表（用于前端选择刷新范围）"""
        settings = self._get_effective_settings()
        if not settings["enabled"]:
            return []

        data = await self._request_json(
            "GET",
            "/Library/MediaFolders",
            url=settings["url"],
            api_key=settings["api_key"],
            timeout=int(settings["timeout"] or 30),
        )
        items = data.get("Items", []) or []
        libraries = []
        for item in items:
            libraries.append(
                {
                    "id": item.get("Id", ""),
                    "name": item.get("Name", ""),
                    "collection_type": item.get("CollectionType"),
                }
            )
        return libraries

    async def _refresh_library(self, library_id: str | None = None) -> RefreshResult:
        """刷新指定媒体库（或全库），返回详细结果（内部方法）。"""
        settings = self._get_effective_settings()
        if not settings["enabled"]:
            return RefreshResult(
                success=False,
                library_id=library_id,
                message="Emby集成未启用或配置不完整",
                timestamp=datetime.now(),
            )

        try:
            endpoint = f"/Items/{library_id}/Refresh" if library_id else "/Library/Refresh"
            await self._request_json(
                "POST",
                endpoint,
                url=settings["url"],
                api_key=settings["api_key"],
                timeout=int(settings["timeout"] or 30),
            )
            msg = f"Emby库刷新已触发: {library_id or '全部'}"
            return RefreshResult(success=True, library_id=library_id, message=msg, timestamp=datetime.now())
        except Exception as e:
            return RefreshResult(
                success=False,
                library_id=library_id,
                message=f"Emby刷新失败: {e!s}",
                timestamp=datetime.now(),
            )

    async def refresh_library(self, library_id: str | None = None) -> bool:
        """
        触发Emby库刷新

        调用Emby API的POST /Library/Refresh接口刷新媒体库。
        如果指定了library_id，则刷新特定库；否则刷新所有库。

        Args:
            library_id: Emby媒体库ID，如果为None则刷新所有库

        Returns:
            bool: 是否成功触发刷新
        """
        result = await self._refresh_library(library_id)
        self._refresh_history.append(result)

        if result.success:
            logger.info(result.message)
            try:
                await self.notification_service.send_notification(
                    type=NotificationType.TASK_COMPLETED,
                    title="Emby库刷新已触发",
                    content=f"库ID: {library_id or '全部'}",
                )
            except Exception:
                pass
        else:
            logger.warning(result.message)
        return result.success

    async def refresh_configured_libraries(self, library_ids: list[str] | None = None) -> list[RefreshResult]:
        """
        刷新配置指定的媒体库（或全部），带并发控制。
        """
        settings = self._get_effective_settings()
        if not settings["enabled"]:
            return []

        if self._refresh_lock.locked():
            logger.warning("Emby refresh already in progress")
            return []

        async with self._refresh_lock:
            ids = library_ids if library_ids is not None else settings["refresh"]["library_ids"]
            ids = [str(x) for x in (ids or []) if str(x).strip()]

            results: list[RefreshResult] = []
            if not ids:
                results.append(await self._refresh_library(None))
            else:
                for lib_id in ids:
                    results.append(await self._refresh_library(lib_id))
                    await asyncio.sleep(0.2)

            for r in results:
                self._refresh_history.append(r)

            if settings.get("notify_on_complete", True):
                try:
                    ok = sum(1 for r in results if r.success)
                    fail = len(results) - ok
                    await self.notification_service.send_notification(
                        type=NotificationType.TASK_COMPLETED if fail == 0 else NotificationType.TASK_FAILED,
                        title="Emby刷新完成" if fail == 0 else "Emby刷新部分失败",
                        content=f"成功: {ok}, 失败: {fail}",
                    )
                except Exception:
                    pass

            return results

    async def trigger_refresh_on_event(self, event_type: str) -> bool:
        """根据事件类型触发刷新（异步执行，不阻塞主流程）。"""
        settings = self._get_effective_settings()
        if not settings["enabled"]:
            return False

        refresh_cfg = settings["refresh"]
        should_refresh = False
        if (event_type == "strm_generate" and refresh_cfg.get("on_strm_generate", True)) or (
            event_type == "rename" and refresh_cfg.get("on_rename", True)
        ):
            should_refresh = True

        if not should_refresh:
            return False

        logger.info(f"Emby refresh triggered by event: {event_type}")
        asyncio.create_task(self.refresh_configured_libraries())
        return True

    def get_refresh_history(self, limit: int = 20) -> list[dict[str, Any]]:
        history = list(self._refresh_history)[-limit:]
        return [
            {
                "success": r.success,
                "library_id": r.library_id,
                "message": r.message,
                "timestamp": r.timestamp.isoformat(),
            }
            for r in reversed(history)
        ]

    def configure_cron(self):
        """
        根据当前配置设置/更新Emby定时刷新任务。

        注意：此方法为同步方法，可在FastAPI请求中调用。
        """
        cron_service = get_cron_service()
        settings = self._get_effective_settings()
        cron_expr = settings["refresh"].get("cron")

        # 注册handler（幂等）
        async def _handler(**_params):
            await self.refresh_configured_libraries()

        cron_service.register_handler("emby_refresh", _handler)

        job_id = "emby_refresh_job"
        if settings["enabled"] and cron_expr:
            try:
                cron_service.add_cron_job(job_id=job_id, cron_expression=cron_expr, task_type="emby_refresh")
            except Exception as e:
                logger.error(f"Failed to configure Emby cron job: {e}")
        elif cron_service.get_job(job_id):
            cron_service.remove_job(job_id)

    async def sync_library(self):
        """全量同步媒体库"""
        if self._sync_lock.locked():
            logger.warning("Emby sync already in progress")
            return

        async with self._sync_lock:
            logger.info("Starting Emby library sync...")
            await self.notification_service.send_notification(
                type=NotificationType.TASK_STARTED, title="Emby同步开始", content="开始同步Emby媒体库信息"
            )

            client = self._get_api_client()
            stats = {"libraries": 0, "items": 0, "new": 0, "updated": 0, "failed": 0}

            try:
                async with client:
                    # 1. 获取所有视图（媒体库）
                    views = await client.get_views()
                    stats["libraries"] = len(views)

                    db = SessionLocal()
                    try:
                        for view in views:
                            await self._sync_single_library(client, db, view, stats)
                    finally:
                        db.close()

                logger.info(f"Emby sync finished: {stats}")
                await self.notification_service.send_notification(
                    type=NotificationType.SYNC_FINISHED,
                    title="Emby同步完成",
                    content=f"处理库: {stats['libraries']}\n项目: {stats['items']}\n新增: {stats['new']}\n更新: {stats['updated']}\n失败: {stats['failed']}",
                )

            except Exception as e:
                logger.error(f"Emby sync failed: {e}")
                await self.notification_service.notify_sync_error("Emby Sync", str(e))

    async def _sync_single_library(self, client: EmbyAPIClient, db: Session, view: dict, stats: dict):
        """同步单个媒体库"""
        library_id_emby = view["Id"]
        library_name = view["Name"]

        # 1. 更新或创建库记录
        lib_record = db.query(EmbyLibrary).filter(EmbyLibrary.emby_id == library_id_emby).first()
        if not lib_record:
            lib_record = EmbyLibrary(emby_id=library_id_emby, name=library_name, path=view.get("Path"))
            db.add(lib_record)
            db.commit()
            db.refresh(lib_record)

        # 2. 获取库中所有项目
        items = await client.get_items_by_query(
            parent_id=library_id_emby, recursive=True, include_item_types="Movie,Episode", fields="Path,MediaSources"
        )

        # 3. 批量处理项目以优化性能
        batch_processor = AsyncBatchProcessor(batch_size=100, delay=0.05)

        async def process_item_batch(item_batch):
            """处理项目批次"""
            batch_stats = {"items": 0, "new": 0, "updated": 0, "failed": 0}

            # 批量获取已存在的项目（避免N+1查询）
            emby_ids = [item["Id"] for item in item_batch]
            existing_items_dict = batch_get_models_by_ids(db, EmbyMediaItem, emby_ids)

            for item in item_batch:
                batch_stats["items"] += 1
                try:
                    is_new = await self._process_item_optimized(
                        db, lib_record.id, item, existing_items_dict.get(item["Id"])
                    )
                    if is_new:
                        batch_stats["new"] += 1
                    else:
                        batch_stats["updated"] += 1
                except Exception as e:
                    logger.error(f"Failed to process item {item.get('Name')}: {e}")
                    batch_stats["failed"] += 1

            return batch_stats

        # 分批处理所有项目
        batch_results = await batch_processor.process_items_batched(items, process_item_batch)

        # 汇总统计信息
        for batch_stat in batch_results:
            stats["items"] += batch_stat["items"]
            stats["new"] += batch_stat["new"]
            stats["updated"] += batch_stat["updated"]
            stats["failed"] += batch_stat["failed"]

    async def _process_item_optimized(self, db: Session, library_id_db: int, item: dict, existing_item=None) -> bool:
        """优化的项目处理方法，支持批量操作"""
        emby_id = item["Id"]
        name = item.get("Name")
        path = item.get("Path", "")
        media_type = item.get("Type")

        # 提取Pickcode
        pickcode = await self._extract_pickcode(item)

        # 使用传入的已存在项目，避免重复查询
        item_record = existing_item
        is_new = False

        if not item_record:
            is_new = True
            item_record = EmbyMediaItem(
                emby_id=emby_id,
                library_id=library_id_db,
                name=name,
                type=media_type,
                path=path,
                pickcode=pickcode,
                is_strm=path.lower().endswith(".strm"),
            )
            db.add(item_record)
        else:
            # 更新字段
            item_record.name = name
            item_record.path = path
            item_record.pickcode = pickcode
            # 注意：需要导入func或使用datetime.now()
            from datetime import datetime

            item_record.updated_at = datetime.now()

        return is_new

    async def _process_item(self, db: Session, library_id_db: int, item: dict) -> bool:
        """处理单个项目，返回是否新增（保持向后兼容）"""
        emby_id = item["Id"]
        name = item.get("Name")
        path = item.get("Path", "")
        media_type = item.get("Type")

        # 提取Pickcode
        pickcode = await self._extract_pickcode(item)

        item_record = db.query(EmbyMediaItem).filter(EmbyMediaItem.emby_id == emby_id).first()
        is_new = False

        if not item_record:
            is_new = True
            item_record = EmbyMediaItem(
                emby_id=emby_id,
                library_id=library_id_db,
                name=name,
                type=media_type,
                path=path,
                pickcode=pickcode,
                is_strm=path.lower().endswith(".strm"),
            )
            db.add(item_record)
        else:
            # 更新字段
            item_record.name = name
            item_record.path = path
            item_record.pickcode = pickcode
            from datetime import datetime

            item_record.updated_at = datetime.now()

        db.commit()
        return is_new

    async def _extract_pickcode(self, item: dict) -> str | None:
        """提取Pickcode"""
        media_sources = item.get("MediaSources", [])
        path = item.get("Path", "")

        # 1. 尝试从Path解析 (如果是 strm 且包含 proxy url)
        # 例如: http://localhost:8000/api/proxy/video/{file_id}
        # file_id 通常就是 pickcode (对于v2 api)
        file_id = extract_file_id_from_proxy_url(path)
        if file_id:
            return file_id

        # 2. 如果是本地STRM文件，读取内容
        if path.lower().endswith(".strm") and os.path.exists(path):
            try:
                content = await read_strm_file_content(path)
                file_id = extract_file_id_from_strm_content(content)
                if file_id:
                    return file_id
            except Exception:
                pass

        # 3. 尝试从 MediaSources 路径解析
        for source in media_sources:
            s_path = source.get("Path", "")
            if "#pickcode=" in s_path:
                return s_path.split("#pickcode=")[-1].split("&")[0]

        return None

    async def link_media_to_sync_file(self, item: dict):
        """WebHook: 关联新媒体"""
        # 这是一个简化版，完整的需建立DB连接
        # 通常Webhook只给基本Item信息，我们可能需要重新查询完整信息
        client = self._get_api_client()
        async with client:
            full_item = await client.get_items(item["Id"])

            db = SessionLocal()
            try:
                # 需要找到对应的 Library ID，这里简化处理，如果没有就创建一个临时或默认的
                # 但最好是先执行一次全量同步
                # 如果找不到，我们尝试根据 item.ParentId 去找 Library? 比较复杂
                # 暂时只记录 EmbyMediaItem，如果 Library 未知则留空或设为 0 (需修改Model允许为空)

                # 实际上 Webhook 最重要的是触发 Pickcode 提取并保存，供 ProxyService 使用
                await self._process_item(db, 0, full_item)  # 0 as placeholder or unknown
            except Exception as e:
                logger.error(f"Link media failed: {e}")
            finally:
                db.close()

    async def handle_library_new(self, item: dict):
        """处理新增事件"""
        await self.notification_service.notify_media_added(item.get("Name", "Unknown"), item.get("Type", "Unknown"))
        await self.link_media_to_sync_file(item)

    async def handle_library_deleted(self, item: dict):
        """处理删除事件"""
        await self.notification_service.notify_media_removed(item.get("Name", "Unknown"))
        # 删除DB记录
        db = SessionLocal()
        try:
            db.query(EmbyMediaItem).filter(EmbyMediaItem.emby_id == item["Id"]).delete()
            db.commit()
        finally:
            db.close()


def get_emby_service():
    return EmbyService.get_instance()
