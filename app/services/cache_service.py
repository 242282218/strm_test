"""
缓存服务模块

提供统一的缓存接口,支持:
- 内存缓存(默认)
- Redis缓存(可选)
- TTL过期机制
- LRU淘汰策略
- 缓存统计
- Legacy/Unified 双模式

参考: QMediaSync 缓存设计

重构说明:
- 支持两种模式：Legacy（独立实现）和 Unified（使用 CacheManager）
- 默认使用 Unified 模式，通过环境变量 CACHE_LEGACY_MODE=true 切换
- 统一 TTL 配置从 CacheManager 读取

统一缓存接口说明:
- 推荐直接使用 app.core.cache_manager.CacheManager
- 本模块提供向后兼容的 CacheService 接口
- 新代码应使用 CacheManager，旧代码可继续使用 CacheService

迁移指南:
    # 旧代码
    from app.services.cache_service import get_cache_service
    cache = get_cache_service()
    await cache.set("key", "value", ttl=600)

    # 新代码（推荐）
    from app.core.cache_manager import get_cache_manager, CacheNamespace
    cache = get_cache_manager()
    await cache.set(CacheNamespace.GENERAL, "key", "value", ttl=600)
"""

import asyncio
import os
import time
from collections.abc import Callable
from typing import Any

# 重导出统一接口（推荐使用）
from app.core.cache_interface import (
    CacheBackendType,
    CacheProtocol,
    CacheStats,
    ManagedCacheProtocol,
)
from app.core.cache_manager import (
    BackendType,
    CacheManager,
    CacheNamespace,
    LegacyCacheAdapter,
    get_cache_manager,
)
from app.core.logging import get_logger
from app.core.lru_cache import LRUCache as CustomLRUCache


logger = get_logger(__name__)

# 是否使用 Legacy 模式
CACHE_LEGACY_MODE = os.getenv("CACHE_LEGACY_MODE", "false").lower() == "true"


class CacheEntry:
    """缓存条目"""

    def __init__(self, value: Any, ttl: int | None = None):
        self.value = value
        self.created_at = time.time()
        self.ttl = ttl
        self.access_count = 0
        self.last_access = time.time()

    def is_expired(self) -> bool:
        """检查是否过期"""
        if self.ttl is None:
            return False
        return time.time() - self.created_at > self.ttl

    def access(self):
        """记录访问"""
        self.access_count += 1
        self.last_access = time.time()


class MemoryCache:
    """内存缓存实现（基于LRU）"""

    def __init__(self, max_size: int = 1000, default_ttl: int = 600):
        """
        初始化内存缓存

        Args:
            max_size: 最大缓存条目数
            default_ttl: 默认TTL(秒)
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        # 使用自定义LRU缓存替换原来的实现
        self._cache = CustomLRUCache(maxsize=max_size, ttl=default_ttl, enable_stats=True)
        self._lock = asyncio.Lock()

        logger.info(f"MemoryCache (LRU) initialized: max_size={max_size}, default_ttl={default_ttl}s")

    async def get(self, key: str) -> Any | None:
        """获取缓存值"""
        async with self._lock:
            value = self._cache.get(key)
            return value

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """设置缓存值"""
        async with self._lock:
            # LRU缓存会自动处理容量限制和淘汰
            self._cache.set(key, value, ttl)

    async def delete(self, key: str) -> bool:
        """删除缓存"""
        async with self._lock:
            return self._cache.delete(key)

    async def clear(self) -> None:
        """清空缓存"""
        async with self._lock:
            self._cache.clear()

    async def cleanup_expired(self) -> int:
        """清理过期条目"""
        async with self._lock:
            return self._cache.cleanup_expired()

    def get_stats(self) -> dict:
        """获取统计信息"""
        # 使用LRU缓存的内置统计
        lru_stats = self._cache.get_stats()

        # 补充缓存服务特有的信息
        return {**lru_stats, "max_size": self.max_size, "default_ttl": self.default_ttl}


class CacheServiceLegacy:
    """
    统一缓存服务 (Legacy 实现)

    支持内存缓存和Redis缓存
    """

    def __init__(
        self, backend: str = "memory", max_size: int = 1000, default_ttl: int = 600, redis_url: str | None = None
    ):
        """
        初始化缓存服务

        Args:
            backend: 缓存后端 ('memory' 或 'redis')
            max_size: 最大缓存条目数
            default_ttl: 默认TTL(秒)
            redis_url: Redis连接URL (backend='redis'时需要)
        """
        self.backend = backend
        self.default_ttl = default_ttl

        if backend == "memory":
            self._cache = MemoryCache(max_size, default_ttl)
        elif backend == "redis":
            from app.services.redis_cache import get_redis_cache_service

            try:
                self._cache = get_redis_cache_service(redis_url or "redis://localhost:6379")
                logger.info("Redis cache backend initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Redis cache, falling back to memory: {e}")
                self._cache = MemoryCache(max_size, default_ttl)
        else:
            raise ValueError(f"Unsupported cache backend: {backend}")

        self._cleanup_task: asyncio.Task | None = None
        logger.info(f"CacheService (Legacy) initialized with backend: {backend}")

    async def start(self):
        """启动缓存服务"""
        # 启动定期清理任务
        self._cleanup_task = asyncio.create_task(self._periodic_cleanup())
        logger.info("CacheService (Legacy) started")

    async def stop(self):
        """停止缓存服务"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        logger.info("CacheService (Legacy) stopped")

    async def _periodic_cleanup(self):
        """定期清理过期条目"""
        while True:
            try:
                await asyncio.sleep(60)  # 每分钟清理一次
                if isinstance(self._cache, MemoryCache):
                    await self._cache.cleanup_expired()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup error: {e}")

    async def get(self, key: str) -> Any | None:
        """获取缓存值"""
        return await self._cache.get(key)

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """设置缓存值"""
        await self._cache.set(key, value, ttl)

    async def delete(self, key: str) -> bool:
        """删除缓存"""
        return await self._cache.delete(key)

    async def clear(self) -> None:
        """清空缓存"""
        await self._cache.clear()

    def get_stats(self) -> dict:
        """获取统计信息"""
        stats = self._cache.get_stats()
        stats["mode"] = "legacy"
        return stats

    async def get_or_set(self, key: str, factory: Callable, ttl: int | None = None) -> Any:
        """
        获取缓存值,如果不存在则调用factory函数生成并缓存

        Args:
            key: 缓存键
            factory: 生成值的函数(可以是async)
            ttl: TTL(秒)

        Returns:
            缓存值或新生成的值
        """
        # 如果底层缓存支持批量操作，使用优化版本
        if hasattr(self._cache, "get_or_set"):
            return await self._cache.get_or_set(key, factory, ttl)

        # 回退到基础实现
        value = await self.get(key)

        if value is not None:
            return value

        # 调用factory生成值
        if asyncio.iscoroutinefunction(factory):
            value = await factory()
        else:
            value = factory()

        await self.set(key, value, ttl)
        return value


class CacheServiceUnified:
    """
    统一缓存服务 (Unified 实现)

    使用 CacheManager 作为底层实现
    """

    def __init__(
        self, backend: str = "memory", max_size: int = 1000, default_ttl: int = 600, redis_url: str | None = None
    ):
        """
        初始化缓存服务

        Args:
            backend: 缓存后端 (Unified 模式下忽略，由 CacheManager 管理)
            max_size: 最大缓存条目数 (从 CacheManager 读取)
            default_ttl: 默认TTL(秒) (从 CacheManager 读取)
            redis_url: Redis连接URL (Unified 模式下忽略)
        """
        from app.core.cache_manager import CacheNamespace, get_cache_manager

        self._cache_manager = get_cache_manager()
        self._namespace = CacheNamespace.GENERAL

        # 从 CacheManager 获取配置
        config = self._cache_manager.get_namespace_config(self._namespace)
        self.default_ttl = config.get("default_ttl", default_ttl)
        self.max_size = config.get("max_size", max_size)

        logger.info(f"CacheService (Unified) initialized: default_ttl={self.default_ttl}s")

    async def start(self):
        """启动缓存服务"""
        # CacheManager 由 main.py 统一启动
        logger.info("CacheService (Unified) started")

    async def stop(self):
        """停止缓存服务"""
        # CacheManager 由 main.py 统一停止
        logger.info("CacheService (Unified) stopped")

    async def get(self, key: str) -> Any | None:
        """获取缓存值"""
        return await self._cache_manager.get(self._namespace, key)

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """设置缓存值"""
        await self._cache_manager.set(self._namespace, key, value, ttl)

    async def delete(self, key: str) -> bool:
        """删除缓存"""
        return await self._cache_manager.delete(self._namespace, key)

    async def clear(self) -> None:
        """清空缓存"""
        await self._cache_manager.clear_namespace(self._namespace)

    def get_stats(self) -> dict:
        """获取统计信息"""
        stats = self._cache_manager.get_namespace_stats(self._namespace) or {}
        stats["mode"] = "unified"
        return stats

    async def get_or_set(self, key: str, factory: Callable, ttl: int | None = None) -> Any:
        """
        获取缓存值,如果不存在则调用factory函数生成并缓存

        Args:
            key: 缓存键
            factory: 生成值的函数(可以是async)
            ttl: TTL(秒)

        Returns:
            缓存值或新生成的值
        """
        return await self._cache_manager.get_or_set(self._namespace, key, factory, ttl)


# 全局缓存实例
_global_cache: Any | None = None


def get_cache_service(max_size: int = 1000, default_ttl: int = 600) -> Any:
    """
    获取全局缓存服务实例

    根据环境变量 CACHE_LEGACY_MODE 选择实现：
    - true: 使用 Legacy 实现（独立缓存）
    - false: 使用 Unified 实现（CacheManager）
    """
    global _global_cache

    if _global_cache is None:
        if CACHE_LEGACY_MODE:
            _global_cache = CacheServiceLegacy(backend="memory", max_size=max_size, default_ttl=default_ttl)
            logger.info("Using CacheService Legacy mode")
        else:
            _global_cache = CacheServiceUnified(backend="memory", max_size=max_size, default_ttl=default_ttl)
            logger.info("Using CacheService Unified mode (CacheManager)")

    return _global_cache


# 为了向后兼容，保留 CacheService 别名
CacheService = CacheServiceLegacy if CACHE_LEGACY_MODE else CacheServiceUnified


# ==================== 废弃警告和迁移指南 ====================


def get_unified_cache() -> CacheManager:
    """
    获取统一缓存管理器（推荐使用）

    这是获取缓存实例的推荐方式。

    Returns:
        CacheManager 实例

    使用示例:
        from app.services.cache_service import get_unified_cache, CacheNamespace

        cache = get_unified_cache()
        await cache.set(CacheNamespace.GENERAL, "key", "value", ttl=600)
        value = await cache.get(CacheNamespace.GENERAL, "key")
    """
    return get_cache_manager()


def get_namespaced_cache(namespace: CacheNamespace) -> LegacyCacheAdapter:
    """
    获取命名空间缓存适配器

    Args:
        namespace: 缓存命名空间

    Returns:
        LegacyCacheAdapter 实例，提供简化的接口

    使用示例:
        from app.services.cache_service import get_namespaced_cache, CacheNamespace

        cache = get_namespaced_cache(CacheNamespace.LINK)
        await cache.set("file_id", "link_value", ttl=600)
        value = await cache.get("file_id")
    """
    manager = get_cache_manager()
    return LegacyCacheAdapter(manager, namespace.value)


# 导出所有公共接口
__all__ = [
    # 统一接口（推荐）
    "CacheProtocol",
    "CacheStats",
    "CacheBackendType",
    "ManagedCacheProtocol",
    "CacheManager",
    "CacheNamespace",
    "get_cache_manager",
    "get_unified_cache",
    "get_namespaced_cache",
    "LegacyCacheAdapter",
    "BackendType",
    # Legacy 接口（向后兼容）
    "CacheService",
    "CacheServiceLegacy",
    "CacheServiceUnified",
    "get_cache_service",
    "MemoryCache",
]
