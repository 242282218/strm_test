"""
统一缓存管理器

提供统一的缓存管理接口，支持：
- 命名空间隔离
- 统一 TTL 配置
- 缓存统计
- 单例模式
- 跨命名空间失效机制
- 缓存版本号支持
- Legacy 模式兼容
- 可选后端支持（Redis、Tiered）
- 批量操作

解决问题：
- 多个独立缓存实现（CacheService、LinkCache、TieredCache）缺乏统一管理
- TTL 配置分散，缺乏命名空间级别的 TTL 控制
- 缓存统计不统一，难以监控整体缓存性能
- 缓存一致性问题：数据变更时无法自动失效相关缓存

接口实现：
- 实现 NamespacedCacheProtocol 接口
- 实现 ManagedCacheProtocol 接口
"""

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from app.core.logging import get_logger
from app.core.lru_cache import LRUCache


logger = get_logger(__name__)


class CacheNamespace(Enum):
    """缓存命名空间枚举"""

    LINK = "link"  # 直链缓存
    FILE_SIZE = "file_size"  # 文件大小缓存
    TMDB = "tmdb"  # TMDB API 缓存
    QUARK_API = "quark_api"  # 夸克 API 缓存
    STRM = "strm"  # STRM 相关缓存
    EMBY = "emby"  # Emby 相关缓存
    PROXY = "proxy"  # 代理缓存
    RENAME = "rename"  # 重命名缓存
    SCRAPE = "scrape"  # 刮削缓存
    GENERAL = "general"  # 通用缓存


# 命名空间默认 TTL 配置（秒）
DEFAULT_NAMESPACE_TTLS = {
    CacheNamespace.LINK: 600,  # 直链缓存 10 分钟
    CacheNamespace.FILE_SIZE: 3600,  # 文件大小缓存 1 小时
    CacheNamespace.TMDB: 86400,  # TMDB 缓存 24 小时
    CacheNamespace.QUARK_API: 300,  # 夸克 API 缓存 5 分钟
    CacheNamespace.STRM: 3600,  # STRM 缓存 1 小时
    CacheNamespace.EMBY: 600,  # Emby 缓存 10 分钟
    CacheNamespace.PROXY: 600,  # 代理缓存 10 分钟
    CacheNamespace.RENAME: 1800,  # 重命名缓存 30 分钟
    CacheNamespace.SCRAPE: 3600,  # 刮削缓存 1 小时
    CacheNamespace.GENERAL: 600,  # 通用缓存 10 分钟
}

# 命名空间默认大小配置
DEFAULT_NAMESPACE_SIZES = {
    CacheNamespace.LINK: 2000,  # 直链缓存较大
    CacheNamespace.FILE_SIZE: 1000,  # 文件大小缓存
    CacheNamespace.TMDB: 500,  # TMDB 缓存
    CacheNamespace.QUARK_API: 1000,  # 夸克 API 缓存
    CacheNamespace.STRM: 500,  # STRM 缓存
    CacheNamespace.EMBY: 500,  # Emby 缓存
    CacheNamespace.PROXY: 1000,  # 代理缓存
    CacheNamespace.RENAME: 500,  # 重命名缓存
    CacheNamespace.SCRAPE: 500,  # 刮削缓存
    CacheNamespace.GENERAL: 1000,  # 通用缓存
}

# 命名空间关联关系：当某个命名空间失效时，同时失效关联的命名空间
# 例如：当文件信息变更时，直链缓存和文件大小缓存都需要失效
NAMESPACE_DEPENDENCIES: dict[CacheNamespace, set[CacheNamespace]] = {
    CacheNamespace.QUARK_API: {CacheNamespace.LINK, CacheNamespace.FILE_SIZE, CacheNamespace.PROXY},
    CacheNamespace.LINK: {CacheNamespace.PROXY},
    CacheNamespace.TMDB: {CacheNamespace.RENAME, CacheNamespace.SCRAPE},
    CacheNamespace.EMBY: {CacheNamespace.STRM},
}


class BackendType(Enum):
    """缓存后端类型"""

    MEMORY = "memory"
    REDIS = "redis"
    TIERED = "tiered"


@dataclass
class CacheConfig:
    """缓存配置"""

    # 各命名空间的默认 TTL
    default_ttls: dict[CacheNamespace, int] = field(default_factory=lambda: DEFAULT_NAMESPACE_TTLS.copy())
    # 各命名空间的最大大小
    namespace_sizes: dict[CacheNamespace, int] = field(default_factory=lambda: DEFAULT_NAMESPACE_SIZES.copy())
    # 全局默认 TTL（未配置的命名空间使用）
    global_default_ttl: int = 600
    # 全局默认大小
    global_default_size: int = 1000
    # 是否启用统计
    enable_stats: bool = True
    # 清理间隔（秒）
    cleanup_interval: int = 60
    # 是否启用版本控制
    enable_versioning: bool = True
    # 是否启用跨命名空间失效
    enable_cross_namespace_invalidation: bool = True
    # 是否使用 Legacy 模式（兼容旧缓存实现）
    legacy_mode: bool = False
    # 后端类型
    backend_type: BackendType = BackendType.MEMORY
    # Redis 配置（当 backend_type 为 REDIS 时使用）
    redis_url: str = "redis://localhost:6379"
    # Tiered 缓存配置（当 backend_type 为 TIERED 时使用）
    enable_disk_cache: bool = False
    disk_cache_path: str = "cache/cache.db"


# 特殊标记：使用默认 TTL
_USE_DEFAULT_TTL = object()

# 永不过期的 TTL 值（10 年）
_TTL_NEVER_EXPIRE = 10 * 365 * 24 * 3600


@dataclass
class CacheVersion:
    """缓存版本信息"""

    namespace: CacheNamespace
    version: int
    updated_at: float

    def to_dict(self) -> dict[str, Any]:
        return {"namespace": self.namespace.value, "version": self.version, "updated_at": self.updated_at}


class NamespacedCache:
    """
    带命名空间的缓存包装器

    为每个命名空间提供独立的 LRU 缓存实例，支持版本控制
    """

    def __init__(
        self,
        namespace: CacheNamespace,
        max_size: int = 1000,
        default_ttl: int = 600,
        enable_stats: bool = True,
        enable_versioning: bool = True,
    ):
        self.namespace = namespace
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.enable_versioning = enable_versioning
        self._cache = LRUCache(maxsize=max_size, ttl=default_ttl, enable_stats=enable_stats)

        # 版本控制
        self._version = 1
        self._version_updated_at = time.time()

        # 键前缀（用于版本控制）
        self._key_prefix = ""

    def _get_versioned_key(self, key: str) -> str:
        """获取带版本前缀的键"""
        if self.enable_versioning:
            return f"v{self._version}:{key}"
        return key

    def _strip_version_prefix(self, key: str) -> str:
        """移除版本前缀"""
        if self.enable_versioning and key.startswith(f"v{self._version}:"):
            return key[len(f"v{self._version}:") :]
        return key

    def increment_version(self) -> int:
        """
        递增版本号，使旧缓存自动失效

        Returns:
            新版本号
        """
        self._version += 1
        self._version_updated_at = time.time()
        logger.info(f"Cache version incremented for {self.namespace.value}: v{self._version}")
        return self._version

    def get_version(self) -> CacheVersion:
        """获取当前版本信息"""
        return CacheVersion(namespace=self.namespace, version=self._version, updated_at=self._version_updated_at)

    def get(self, key: str) -> Any | None:
        """获取缓存值"""
        versioned_key = self._get_versioned_key(key)
        return self._cache.get(versioned_key)

    def set(self, key: str, value: Any, ttl: Any = _USE_DEFAULT_TTL) -> None:
        """
        设置缓存值

        Args:
            key: 缓存键
            value: 缓存值
            ttl: 过期时间（秒）
                - 不传参数：使用命名空间默认 TTL
                - None：永不过期
                - 具体数值：使用指定 TTL
        """
        if ttl is _USE_DEFAULT_TTL:
            effective_ttl = self.default_ttl
        elif ttl is None:
            # None 表示永不过期，使用一个非常大的值
            effective_ttl = _TTL_NEVER_EXPIRE
        else:
            effective_ttl = ttl

        versioned_key = self._get_versioned_key(key)
        self._cache.set(versioned_key, value, effective_ttl)

    def delete(self, key: str) -> bool:
        """删除缓存"""
        versioned_key = self._get_versioned_key(key)
        return self._cache.delete(versioned_key)

    def clear(self) -> None:
        """清空缓存"""
        self._cache.clear()

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息"""
        stats = self._cache.get_stats()
        stats["version"] = self._version
        stats["version_updated_at"] = self._version_updated_at
        return stats

    def cleanup_expired(self) -> int:
        """清理过期条目"""
        return self._cache.cleanup_expired()

    def __len__(self) -> int:
        return len(self._cache)


class CacheManager:
    """
    统一缓存管理器

    特性：
    - 单例模式，全局唯一实例
    - 命名空间隔离，不同业务使用不同命名空间
    - 统一 TTL 配置，支持命名空间级别配置
    - 统一统计信息，便于监控
    - 跨命名空间失效机制
    - 缓存版本号支持
    - Legacy 模式兼容
    """

    _instance: Optional["CacheManager"] = None
    _lock = asyncio.Lock()

    def __new__(cls, *args, **kwargs):
        """确保单例"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, config: CacheConfig | None = None):
        """初始化缓存管理器"""
        if self._initialized:
            return

        self.config = config or CacheConfig()
        self._namespaces: dict[CacheNamespace, NamespacedCache] = {}
        self._running = False
        self._cleanup_task: asyncio.Task | None = None

        # 全局统计
        self._global_stats = {
            "total_hits": 0,
            "total_misses": 0,
            "total_sets": 0,
            "total_deletes": 0,
            "total_invalidations": 0,
        }

        # 失效事件记录（用于调试和监控）
        self._invalidation_log: list[dict[str, Any]] = []
        self._max_invalidation_log_size = 100

        # 初始化所有命名空间
        self._init_namespaces()

        self._initialized = True
        logger.info(
            f"CacheManager initialized with {len(self._namespaces)} namespaces, "
            f"versioning={self.config.enable_versioning}, "
            f"cross_namespace={self.config.enable_cross_namespace_invalidation}"
        )

    def _init_namespaces(self):
        """初始化所有命名空间"""
        for namespace in CacheNamespace:
            ttl = self.config.default_ttls.get(namespace, self.config.global_default_ttl)
            size = self.config.namespace_sizes.get(namespace, self.config.global_default_size)

            self._namespaces[namespace] = NamespacedCache(
                namespace=namespace,
                max_size=size,
                default_ttl=ttl,
                enable_stats=self.config.enable_stats,
                enable_versioning=self.config.enable_versioning,
            )

            logger.debug(f"Initialized namespace {namespace.value}: size={size}, ttl={ttl}s")

    @classmethod
    def get_instance(cls, config: CacheConfig | None = None) -> "CacheManager":
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = cls(config)
        return cls._instance

    @classmethod
    def reset_instance(cls):
        """重置单例（主要用于测试）"""
        if cls._instance is not None:
            # 清理资源
            if cls._instance._running:
                # 注意：这里不能调用 async 方法，需要在 async 上下文中调用 stop
                pass
            cls._instance = None

    async def start(self):
        """启动缓存管理器"""
        if self._running:
            logger.warning("CacheManager is already running")
            return

        self._running = True
        self._cleanup_task = asyncio.create_task(self._periodic_cleanup())
        logger.info("CacheManager started")

    async def stop(self):
        """停止缓存管理器"""
        if not self._running:
            logger.warning("CacheManager is not running")
            return

        self._running = False

        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        logger.info("CacheManager stopped")

    async def _periodic_cleanup(self):
        """定期清理过期条目"""
        while self._running:
            try:
                await asyncio.sleep(self.config.cleanup_interval)

                total_cleaned = 0
                for namespace, cache in self._namespaces.items():
                    cleaned = cache.cleanup_expired()
                    if cleaned > 0:
                        total_cleaned += cleaned
                        logger.debug(f"Cleaned {cleaned} expired entries in namespace {namespace.value}")

                if total_cleaned > 0:
                    logger.info(f"Periodic cleanup: removed {total_cleaned} expired entries")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Periodic cleanup error: {e}")

    def _get_namespace_cache(self, namespace: CacheNamespace) -> NamespacedCache:
        """获取命名空间缓存"""
        if namespace not in self._namespaces:
            raise ValueError(f"Unknown namespace: {namespace}")
        return self._namespaces[namespace]

    async def get(self, namespace: CacheNamespace, key: str) -> Any | None:
        """
        获取缓存值

        Args:
            namespace: 命名空间
            key: 缓存键

        Returns:
            缓存值，不存在返回 None
        """
        cache = self._get_namespace_cache(namespace)
        value = cache.get(key)

        if value is not None:
            self._global_stats["total_hits"] += 1
        else:
            self._global_stats["total_misses"] += 1

        return value

    async def set(self, namespace: CacheNamespace, key: str, value: Any, ttl: Any = _USE_DEFAULT_TTL) -> None:
        """
        设置缓存值

        Args:
            namespace: 命名空间
            key: 缓存键
            value: 缓存值
            ttl: 过期时间（秒）
                - 不传参数：使用命名空间默认 TTL
                - None：永不过期
                - 具体数值：使用指定 TTL
        """
        cache = self._get_namespace_cache(namespace)
        cache.set(key, value, ttl)
        self._global_stats["total_sets"] += 1

    async def delete(self, namespace: CacheNamespace, key: str) -> bool:
        """
        删除缓存

        Args:
            namespace: 命名空间
            key: 缓存键

        Returns:
            是否成功删除
        """
        cache = self._get_namespace_cache(namespace)
        result = cache.delete(key)

        if result:
            self._global_stats["total_deletes"] += 1

        return result

    async def clear_namespace(self, namespace: CacheNamespace) -> None:
        """清空指定命名空间的缓存"""
        cache = self._get_namespace_cache(namespace)
        cache.clear()
        logger.info(f"Cleared namespace: {namespace.value}")

    async def invalidate_related(
        self, namespace: CacheNamespace, key: str | None = None, cascade: bool = True
    ) -> dict[str, Any]:
        """
        失效指定命名空间的缓存，并可选地失效关联命名空间

        Args:
            namespace: 要失效的命名空间
            key: 可选的特定键，None 表示失效整个命名空间
            cascade: 是否级联失效关联命名空间

        Returns:
            失效结果信息
        """
        result = {
            "primary_namespace": namespace.value,
            "invalidated_keys": [],
            "cascaded_namespaces": [],
            "version_incremented": False,
        }

        # 记录失效事件
        invalidation_event = {"timestamp": time.time(), "namespace": namespace.value, "key": key, "cascade": cascade}

        # 失效主命名空间
        cache = self._get_namespace_cache(namespace)

        if key:
            # 失效特定键
            if cache.delete(key):
                result["invalidated_keys"].append(key)
                self._global_stats["total_invalidations"] += 1
        else:
            # 失效整个命名空间（通过递增版本号）
            if self.config.enable_versioning:
                new_version = cache.increment_version()
                result["version_incremented"] = True
                result["new_version"] = new_version
            else:
                cache.clear()
            self._global_stats["total_invalidations"] += 1

        # 级联失效关联命名空间
        if cascade and self.config.enable_cross_namespace_invalidation:
            dependent_namespaces = NAMESPACE_DEPENDENCIES.get(namespace, set())

            for dep_namespace in dependent_namespaces:
                dep_cache = self._get_namespace_cache(dep_namespace)

                if self.config.enable_versioning:
                    dep_cache.increment_version()
                else:
                    dep_cache.clear()

                result["cascaded_namespaces"].append(dep_namespace.value)
                self._global_stats["total_invalidations"] += 1

                logger.debug(f"Cascaded invalidation: {namespace.value} -> {dep_namespace.value}")

        # 记录失效事件
        invalidation_event["result"] = result
        self._add_invalidation_log(invalidation_event)

        logger.info(
            f"Cache invalidation: namespace={namespace.value}, key={key}, "
            f"cascaded={len(result['cascaded_namespaces'])} namespaces"
        )

        return result

    def _add_invalidation_log(self, event: dict[str, Any]):
        """添加失效事件到日志"""
        self._invalidation_log.append(event)

        # 保持日志大小限制
        if len(self._invalidation_log) > self._max_invalidation_log_size:
            self._invalidation_log = self._invalidation_log[-self._max_invalidation_log_size :]

    def get_invalidation_log(self, limit: int = 20) -> list[dict[str, Any]]:
        """获取失效事件日志"""
        return self._invalidation_log[-limit:]

    async def increment_namespace_version(self, namespace: CacheNamespace, cascade: bool = True) -> dict[str, Any]:
        """
        递增命名空间版本号，使旧缓存自动失效

        Args:
            namespace: 命名空间
            cascade: 是否级联失效关联命名空间

        Returns:
            版本更新信息
        """
        cache = self._get_namespace_cache(namespace)
        new_version = cache.increment_version()

        result = {"namespace": namespace.value, "new_version": new_version, "cascaded_namespaces": []}

        # 级联更新关联命名空间
        if cascade and self.config.enable_cross_namespace_invalidation:
            dependent_namespaces = NAMESPACE_DEPENDENCIES.get(namespace, set())

            for dep_namespace in dependent_namespaces:
                dep_cache = self._get_namespace_cache(dep_namespace)
                dep_cache.increment_version()
                result["cascaded_namespaces"].append(dep_namespace.value)

        self._global_stats["total_invalidations"] += 1 + len(result["cascaded_namespaces"])

        logger.info(
            f"Version incremented: {namespace.value} -> v{new_version}, "
            f"cascaded={len(result['cascaded_namespaces'])} namespaces"
        )

        return result

    def get_namespace_version(self, namespace: CacheNamespace) -> CacheVersion:
        """获取命名空间当前版本"""
        cache = self._get_namespace_cache(namespace)
        return cache.get_version()

    def get_all_versions(self) -> dict[str, CacheVersion]:
        """获取所有命名空间的版本信息"""
        return {namespace.value: cache.get_version() for namespace, cache in self._namespaces.items()}

    async def clear_all(self) -> None:
        """清空所有缓存"""
        for namespace in self._namespaces:
            self._namespaces[namespace].clear()

        logger.info("Cleared all namespaces")

    async def get_or_set(
        self, namespace: CacheNamespace, key: str, factory: Callable, ttl: Any = _USE_DEFAULT_TTL
    ) -> Any:
        """
        获取缓存值，如果不存在则调用工厂函数生成

        Args:
            namespace: 命名空间
            key: 缓存键
            factory: 生成值的函数（可以是异步函数）
            ttl: 过期时间（秒）
                - 不传参数：使用命名空间默认 TTL
                - None：永不过期
                - 具体数值：使用指定 TTL

        Returns:
            缓存值或新生成的值
        """
        value = await self.get(namespace, key)

        if value is not None:
            return value

        # 调用工厂函数生成值
        if asyncio.iscoroutinefunction(factory):
            value = await factory()
        else:
            value = factory()

        await self.set(namespace, key, value, ttl)

        return value

    def get_stats(self) -> dict[str, Any]:
        """
        获取全局统计信息

        Returns:
            统计信息字典
        """
        total_requests = self._global_stats["total_hits"] + self._global_stats["total_misses"]
        hit_rate = self._global_stats["total_hits"] / total_requests * 100 if total_requests > 0 else 0

        namespace_stats = {}
        for namespace, cache in self._namespaces.items():
            namespace_stats[namespace.value] = cache.get_stats()

        return {
            **self._global_stats,
            "hit_rate": f"{hit_rate:.2f}%",
            "total_requests": total_requests,
            "running": self._running,
            "config": {
                "versioning_enabled": self.config.enable_versioning,
                "cross_namespace_invalidation_enabled": self.config.enable_cross_namespace_invalidation,
                "legacy_mode": self.config.legacy_mode,
            },
            "namespaces": namespace_stats,
        }

    def get_namespace_stats(self, namespace: CacheNamespace) -> dict[str, Any] | None:
        """获取指定命名空间的统计信息"""
        cache = self._get_namespace_cache(namespace)
        return cache.get_stats()

    def get_namespace_config(self, namespace: CacheNamespace) -> dict[str, Any]:
        """获取命名空间配置"""
        cache = self._get_namespace_cache(namespace)
        return {
            "namespace": namespace.value,
            "max_size": cache.max_size,
            "default_ttl": cache.default_ttl,
            "version": cache._version if hasattr(cache, "_version") else 1,
        }

    def get_dependency_graph(self) -> dict[str, list[str]]:
        """
        获取命名空间依赖关系图

        Returns:
            命名空间依赖关系字典
        """
        return {
            namespace.value: [dep.value for dep in dependencies]
            for namespace, dependencies in NAMESPACE_DEPENDENCIES.items()
        }

    # ==================== 批量操作方法 ====================

    async def get_many(self, namespace: CacheNamespace, keys: list[str]) -> dict[str, Any]:
        """
        批量获取缓存值

        Args:
            namespace: 命名空间
            keys: 缓存键列表

        Returns:
            {key: value} 字典，不存在的键不会包含在结果中
        """
        cache = self._get_namespace_cache(namespace)
        results = {}

        for key in keys:
            value = cache.get(key)
            if value is not None:
                results[key] = value
                self._global_stats["total_hits"] += 1
            else:
                self._global_stats["total_misses"] += 1

        return results

    async def set_many(self, namespace: CacheNamespace, items: dict[str, Any], ttl: Any = _USE_DEFAULT_TTL) -> int:
        """
        批量设置缓存值

        Args:
            namespace: 命名空间
            items: {key: value} 字典
            ttl: 过期时间（秒）

        Returns:
            成功设置的键数量
        """
        cache = self._get_namespace_cache(namespace)
        success_count = 0

        for key, value in items.items():
            cache.set(key, value, ttl)
            success_count += 1
            self._global_stats["total_sets"] += 1

        return success_count

    async def delete_many(self, namespace: CacheNamespace, keys: list[str]) -> int:
        """
        批量删除缓存

        Args:
            namespace: 命名空间
            keys: 缓存键列表

        Returns:
            成功删除的键数量
        """
        cache = self._get_namespace_cache(namespace)
        success_count = 0

        for key in keys:
            if cache.delete(key):
                success_count += 1
                self._global_stats["total_deletes"] += 1

        return success_count

    # ==================== 后端适配器方法 ====================

    def get_backend_adapter(self, backend_type: BackendType) -> "BackendAdapter":
        """
        获取后端适配器

        Args:
            backend_type: 后端类型

        Returns:
            后端适配器实例
        """
        return BackendAdapter(self, backend_type)

    @property
    def is_running(self) -> bool:
        """是否正在运行"""
        return self._running

    # ==================== Legacy 兼容方法 ====================
    # 以下方法提供与旧缓存实现的兼容性

    def get_legacy_cache_adapter(self, cache_type: str) -> "LegacyCacheAdapter":
        """
        获取 Legacy 缓存适配器

        Args:
            cache_type: 缓存类型 ('link', 'general', 'tmdb')

        Returns:
            Legacy 缓存适配器实例
        """
        return LegacyCacheAdapter(self, cache_type)


class LegacyCacheAdapter:
    """
    Legacy 缓存适配器

    提供与旧缓存实现兼容的接口，内部使用 CacheManager
    """

    # 缓存类型到命名空间的映射
    CACHE_TYPE_MAPPING = {
        "link": CacheNamespace.LINK,
        "general": CacheNamespace.GENERAL,
        "tmdb": CacheNamespace.TMDB,
        "quark_api": CacheNamespace.QUARK_API,
        "proxy": CacheNamespace.PROXY,
    }

    def __init__(self, cache_manager: CacheManager, cache_type: str):
        self.cache_manager = cache_manager
        self.cache_type = cache_type
        self.namespace = self.CACHE_TYPE_MAPPING.get(cache_type, CacheNamespace.GENERAL)

    async def get(self, key: str) -> Any | None:
        """获取缓存值"""
        return await self.cache_manager.get(self.namespace, key)

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """设置缓存值"""
        await self.cache_manager.set(self.namespace, key, value, ttl)

    async def delete(self, key: str) -> bool:
        """删除缓存"""
        return await self.cache_manager.delete(self.namespace, key)

    async def clear(self) -> None:
        """清空缓存"""
        await self.cache_manager.clear_namespace(self.namespace)

    async def get_or_set(self, key: str, factory: Callable, ttl: int | None = None) -> Any:
        """获取或设置缓存"""
        return await self.cache_manager.get_or_set(self.namespace, key, factory, ttl)

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息"""
        return self.cache_manager.get_namespace_stats(self.namespace) or {}


# 便捷函数
def get_cache_manager(config: CacheConfig | None = None) -> CacheManager:
    """获取缓存管理器实例"""
    return CacheManager.get_instance(config)


def get_legacy_cache_adapter(cache_type: str) -> LegacyCacheAdapter:
    """
    获取 Legacy 缓存适配器

    用于兼容旧代码，内部使用统一的 CacheManager

    Args:
        cache_type: 缓存类型 ('link', 'general', 'tmdb')

    Returns:
        Legacy 缓存适配器
    """
    manager = get_cache_manager()
    return manager.get_legacy_cache_adapter(cache_type)


def reset_instance():
    """
    重置 CacheManager 单例（主要用于测试）

    注意：调用此函数后，需要重新获取 CacheManager 实例
    """
    CacheManager.reset_instance()


class BackendAdapter:
    """
    后端适配器

    提供对不同缓存后端的统一访问接口
    """

    def __init__(self, cache_manager: CacheManager, backend_type: BackendType):
        self.cache_manager = cache_manager
        self.backend_type = backend_type
        self._backend: Any | None = None

    async def _init_backend(self) -> Any:
        """初始化后端"""
        if self._backend is not None:
            return self._backend

        if self.backend_type == BackendType.REDIS:
            try:
                from app.services.redis_cache import get_redis_cache_backend

                self._backend = get_redis_cache_backend(redis_url=self.cache_manager.config.redis_url)
                await self._backend.connect()
            except Exception as e:
                logger.error(f"Failed to initialize Redis backend: {e}")
                raise

        elif self.backend_type == BackendType.TIERED:
            try:
                from app.services.tiered_cache import get_tiered_cache

                self._backend = get_tiered_cache()
                await self._backend.start()
            except Exception as e:
                logger.error(f"Failed to initialize Tiered backend: {e}")
                raise

        else:
            # 默认使用内存后端（即 CacheManager 本身）
            self._backend = self.cache_manager

        return self._backend

    async def get(self, key: str) -> Any | None:
        """获取缓存值"""
        backend = await self._init_backend()
        return await backend.get(key)

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """设置缓存值"""
        backend = await self._init_backend()
        await backend.set(key, value, ttl)

    async def delete(self, key: str) -> bool:
        """删除缓存"""
        backend = await self._init_backend()
        return await backend.delete(key)

    async def close(self) -> None:
        """关闭后端连接"""
        if self._backend is None:
            return

        if self.backend_type == BackendType.REDIS:
            await self._backend.disconnect()
        elif self.backend_type == BackendType.TIERED:
            await self._backend.stop()

        self._backend = None
