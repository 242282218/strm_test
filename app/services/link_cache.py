"""
直链缓存与刷新机制

参考: go-emby2openlist internal/web/cache/cache.go

重构说明:
- 支持两种模式：Legacy（独立实现）和 Unified（使用 CacheManager）
- 默认使用 Unified 模式，通过环境变量 CACHE_LEGACY_MODE=true 切换
- 统一 TTL 配置从 CacheManager 读取

统一缓存接口说明:
- 推荐直接使用 app.core.cache_manager.CacheManager
- 本模块提供向后兼容的 LinkCache 接口
- 新代码应使用 CacheManager，旧代码可继续使用 LinkCache

迁移指南:
    # 旧代码
    from app.services.link_cache import get_link_cache_service
    cache = get_link_cache_service()
    await cache.set("file_id", "link_value", ttl=600)

    # 新代码（推荐）
    from app.core.cache_manager import get_cache_manager, CacheNamespace
    cache = get_cache_manager()
    await cache.set(CacheNamespace.LINK, "file_id", "link_value", ttl=600)
"""

import asyncio
import os
import time
from datetime import datetime
from typing import Any

# 重导出统一接口（推荐使用）
from app.core.cache_interface import (
    CacheProtocol,
    CacheStats,
)
from app.core.cache_manager import (
    CacheManager,
    CacheNamespace,
    LegacyCacheAdapter,
    get_cache_manager,
)
from app.core.logging import get_logger


logger = get_logger(__name__)

# 是否使用 Legacy 模式
CACHE_LEGACY_MODE = os.getenv("CACHE_LEGACY_MODE", "false").lower() == "true"


class CacheEntry:
    """缓存条目"""

    def __init__(self, key: str, value: Any, headers: dict[str, str] | None = None, ttl: int = 600):
        """
        初始化缓存条目

        Args:
            key: 缓存键
            value: 缓存值
            headers: 响应头
            ttl: 生存时间（秒）
        """
        self.key = key
        self.value = value
        self.headers = headers or {}
        self.ttl = ttl
        self.created_at = time.time()
        self.expires_at = self.created_at + ttl
        self.access_count = 0
        self.last_accessed_at = self.created_at

    def is_expired(self) -> bool:
        """检查是否过期"""
        return time.time() > self.expires_at

    def touch(self):
        """更新访问时间"""
        self.access_count += 1
        self.last_accessed_at = time.time()

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "key": self.key,
            "value": self.value,
            "headers": self.headers,
            "ttl": self.ttl,
            "created_at": datetime.fromtimestamp(self.created_at).isoformat(),
            "expires_at": datetime.fromtimestamp(self.expires_at).isoformat(),
            "access_count": self.access_count,
            "last_accessed_at": datetime.fromtimestamp(self.last_accessed_at).isoformat(),
        }


class LinkCacheLegacy:
    """
    直链缓存服务 (Legacy 实现)

    独立的缓存实现，不依赖 CacheManager
    """

    def __init__(self, default_ttl: int = 600, max_size: int = 1000, cleanup_interval: int = 300):
        """
        初始化直链缓存服务

        参考: go-emby2openlist internal/web/cache/cache.go

        Args:
            default_ttl: 默认TTL（秒）
            max_size: 最大缓存条目数
            cleanup_interval: 清理间隔（秒）
        """
        self.default_ttl = default_ttl
        self.max_size = max_size
        self.cleanup_interval = cleanup_interval
        self._cache: dict[str, CacheEntry] = {}
        self._lock = asyncio.Lock()
        self._cleanup_task: asyncio.Task | None = None
        self._running = False
        logger.info(f"LinkCache (Legacy) initialized: default_ttl={default_ttl}s, max_size={max_size}")

    def _generate_cache_key(self, file_id: str, range_header: str | None = None, **kwargs) -> str:
        """
        生成缓存键

        参考: go-emby2openlist internal/web/cache/cache.go

        Args:
            file_id: 文件ID
            range_header: Range请求头
            **kwargs: 其他参数

        Returns:
            缓存键
        """
        # 忽略Range等易变Header
        key_parts = [file_id]

        # 添加其他稳定参数
        for k, v in sorted(kwargs.items()):
            if v is not None:
                key_parts.append(f"{k}={v}")

        return ":".join(key_parts)

    async def get(self, file_id: str, range_header: str | None = None, **kwargs) -> CacheEntry | None:
        """
        获取缓存

        Args:
            file_id: 文件ID
            range_header: Range请求头
            **kwargs: 其他参数

        Returns:
            缓存条目
        """
        cache_key = self._generate_cache_key(file_id, range_header, **kwargs)

        async with self._lock:
            entry = self._cache.get(cache_key)

            if entry:
                if entry.is_expired():
                    logger.debug(f"Cache entry expired: {cache_key}")
                    del self._cache[cache_key]
                    return None

                entry.touch()
                logger.debug(f"Cache hit: {cache_key}")
                return entry

            logger.debug(f"Cache miss: {cache_key}")
            return None

    async def set(
        self,
        file_id: str,
        value: Any,
        headers: dict[str, str] | None = None,
        ttl: int | None = None,
        range_header: str | None = None,
        **kwargs,
    ) -> None:
        """
        设置缓存

        Args:
            file_id: 文件ID
            value: 缓存值
            headers: 响应头
            ttl: 生存时间（秒）
            range_header: Range请求头
            **kwargs: 其他参数
        """
        cache_key = self._generate_cache_key(file_id, range_header, **kwargs)
        cache_ttl = ttl or self.default_ttl

        async with self._lock:
            # 检查缓存大小
            if len(self._cache) >= self.max_size:
                await self._cleanup_expired()
                # 如果仍然超过，删除最旧的条目
                if len(self._cache) >= self.max_size:
                    await self._evict_oldest()

            entry = CacheEntry(key=cache_key, value=value, headers=headers, ttl=cache_ttl)
            self._cache[cache_key] = entry
            logger.debug(f"Cache set: {cache_key}, ttl={cache_ttl}s")

    async def delete(self, file_id: str, range_header: str | None = None, **kwargs) -> bool:
        """
        删除缓存

        Args:
            file_id: 文件ID
            range_header: Range请求头
            **kwargs: 其他参数

        Returns:
            是否删除成功
        """
        cache_key = self._generate_cache_key(file_id, range_header, **kwargs)

        async with self._lock:
            if cache_key in self._cache:
                del self._cache[cache_key]
                logger.debug(f"Cache deleted: {cache_key}")
                return True
            return False

    async def _cleanup_expired(self):
        """清理过期缓存"""
        expired_keys = []

        for key, entry in self._cache.items():
            if entry.is_expired():
                expired_keys.append(key)

        for key in expired_keys:
            del self._cache[key]

        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")

    async def _evict_oldest(self):
        """驱逐最旧的缓存条目"""
        if not self._cache:
            return

        # 按最后访问时间排序
        sorted_entries = sorted(self._cache.items(), key=lambda x: x[1].last_accessed_at)

        # 删除最旧的10%条目
        evict_count = max(1, len(sorted_entries) // 10)
        for key, _ in sorted_entries[:evict_count]:
            del self._cache[key]

        logger.debug(f"Evicted {evict_count} oldest cache entries")

    async def _cleanup_loop(self):
        """清理循环"""
        while self._running:
            await asyncio.sleep(self.cleanup_interval)
            async with self._lock:
                await self._cleanup_expired()
                # 检查缓存大小
                if len(self._cache) > self.max_size:
                    await self._evict_oldest()

    async def start(self):
        """启动缓存服务"""
        if self._running:
            logger.warning("LinkCache is already running")
            return

        self._running = True
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("LinkCache (Legacy) started")

    async def stop(self):
        """停止缓存服务"""
        if not self._running:
            logger.warning("LinkCache is not running")
            return

        self._running = False

        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        logger.info("LinkCache (Legacy) stopped")

    async def clear(self):
        """清空缓存"""
        async with self._lock:
            self._cache.clear()
            logger.info("LinkCache cleared")

    def get_stats(self) -> dict[str, Any]:
        """
        获取缓存统计信息

        Returns:
            统计信息字典
        """
        total_entries = len(self._cache)
        expired_entries = sum(1 for entry in self._cache.values() if entry.is_expired())
        total_access_count = sum(entry.access_count for entry in self._cache.values())

        return {
            "total_entries": total_entries,
            "expired_entries": expired_entries,
            "valid_entries": total_entries - expired_entries,
            "total_access_count": total_access_count,
            "max_size": self.max_size,
            "default_ttl": self.default_ttl,
            "cleanup_interval": self.cleanup_interval,
            "running": self._running,
            "mode": "legacy",
        }


class LinkCacheUnified:
    """
    直链缓存服务 (Unified 实现)

    使用 CacheManager 作为底层实现，支持命名空间隔离和统一 TTL 配置
    """

    def __init__(self, default_ttl: int = 600, max_size: int = 1000, cleanup_interval: int = 300):
        """
        初始化直链缓存服务

        Args:
            default_ttl: 默认TTL（秒）- 从 CacheManager 读取
            max_size: 最大缓存条目数 - 从 CacheManager 读取
            cleanup_interval: 清理间隔（秒）- 由 CacheManager 管理
        """
        from app.core.cache_manager import CacheNamespace, get_cache_manager

        self._cache_manager = get_cache_manager()
        self._namespace = CacheNamespace.LINK

        # 从 CacheManager 获取配置
        config = self._cache_manager.get_namespace_config(self._namespace)
        self.default_ttl = config.get("default_ttl", default_ttl)
        self.max_size = config.get("max_size", max_size)

        self._running = False
        logger.info(f"LinkCache (Unified) initialized: default_ttl={self.default_ttl}s, max_size={self.max_size}")

    def _generate_cache_key(self, file_id: str, range_header: str | None = None, **kwargs) -> str:
        """生成缓存键"""
        key_parts = [file_id]
        for k, v in sorted(kwargs.items()):
            if v is not None:
                key_parts.append(f"{k}={v}")
        return ":".join(key_parts)

    async def get(self, file_id: str, range_header: str | None = None, **kwargs) -> CacheEntry | None:
        """获取缓存"""
        cache_key = self._generate_cache_key(file_id, range_header, **kwargs)

        # 从 CacheManager 获取
        value = await self._cache_manager.get(self._namespace, cache_key)

        if value is not None:
            # 如果值是 CacheEntry，直接返回
            if isinstance(value, CacheEntry):
                value.touch()
                return value
            # 否则包装成 CacheEntry
            return CacheEntry(key=cache_key, value=value, ttl=self.default_ttl)

        return None

    async def set(
        self,
        file_id: str,
        value: Any,
        headers: dict[str, str] | None = None,
        ttl: int | None = None,
        range_header: str | None = None,
        **kwargs,
    ) -> None:
        """设置缓存"""
        cache_key = self._generate_cache_key(file_id, range_header, **kwargs)
        cache_ttl = ttl or self.default_ttl

        # 如果有 headers，包装成 CacheEntry
        if headers:
            entry = CacheEntry(key=cache_key, value=value, headers=headers, ttl=cache_ttl)
            await self._cache_manager.set(self._namespace, cache_key, entry, cache_ttl)
        else:
            await self._cache_manager.set(self._namespace, cache_key, value, cache_ttl)

        logger.debug(f"Cache set: {cache_key}, ttl={cache_ttl}s")

    async def delete(self, file_id: str, range_header: str | None = None, **kwargs) -> bool:
        """删除缓存"""
        cache_key = self._generate_cache_key(file_id, range_header, **kwargs)
        return await self._cache_manager.delete(self._namespace, cache_key)

    async def start(self):
        """启动缓存服务"""
        if self._running:
            return
        self._running = True
        logger.info("LinkCache (Unified) started")

    async def stop(self):
        """停止缓存服务"""
        self._running = False
        logger.info("LinkCache (Unified) stopped")

    async def clear(self):
        """清空缓存"""
        await self._cache_manager.clear_namespace(self._namespace)
        logger.info("LinkCache (Unified) cleared")

    def get_stats(self) -> dict[str, Any]:
        """获取缓存统计信息"""
        stats = self._cache_manager.get_namespace_stats(self._namespace) or {}
        stats["mode"] = "unified"
        stats["default_ttl"] = self.default_ttl
        stats["max_size"] = self.max_size
        return stats


# 根据配置选择实现
_global_link_cache: Any | None = None


def get_link_cache_service(default_ttl: int = 600, max_size: int = 1000, cleanup_interval: int = 300) -> Any:
    """
    获取直链缓存服务实例

    根据环境变量 CACHE_LEGACY_MODE 选择实现：
    - true: 使用 Legacy 实现（独立缓存）
    - false: 使用 Unified 实现（CacheManager）
    """
    global _global_link_cache

    if _global_link_cache is None:
        if CACHE_LEGACY_MODE:
            _global_link_cache = LinkCacheLegacy(
                default_ttl=default_ttl, max_size=max_size, cleanup_interval=cleanup_interval
            )
            logger.info("Using LinkCache Legacy mode")
        else:
            _global_link_cache = LinkCacheUnified(
                default_ttl=default_ttl, max_size=max_size, cleanup_interval=cleanup_interval
            )
            logger.info("Using LinkCache Unified mode (CacheManager)")

    return _global_link_cache


# 为了向后兼容，保留 LinkCache 别名
LinkCache = LinkCacheLegacy if CACHE_LEGACY_MODE else LinkCacheUnified


# ==================== 便捷函数 ====================


def get_link_cache() -> LegacyCacheAdapter:
    """
    获取直链缓存适配器（推荐使用）

    这是获取直链缓存实例的推荐方式。

    Returns:
        LegacyCacheAdapter 实例

    使用示例:
        from app.services.link_cache import get_link_cache

        cache = get_link_cache()
        await cache.set("file_id", "link_value", ttl=600)
        value = await cache.get("file_id")
    """
    manager = get_cache_manager()
    return LegacyCacheAdapter(manager, "link")


# 导出所有公共接口
__all__ = [
    # 统一接口（推荐）
    "CacheProtocol",
    "CacheStats",
    "CacheManager",
    "CacheNamespace",
    "get_cache_manager",
    "get_link_cache",
    "LegacyCacheAdapter",
    # Legacy 接口（向后兼容）
    "LinkCache",
    "LinkCacheLegacy",
    "LinkCacheUnified",
    "get_link_cache_service",
    "CacheEntry",
]
