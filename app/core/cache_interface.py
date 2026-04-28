"""
统一缓存抽象接口

定义缓存系统的标准接口规范，所有缓存实现都应遵循此接口。
支持：
- 基础 CRUD 操作
- 批量操作
- 统计信息
- 生命周期管理

设计原则：
- Protocol 定义接口契约
- 最小化接口集，保证兼容性
- 扩展接口通过 Mixin 实现
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import Enum
from typing import (
    Any,
    Protocol,
    runtime_checkable,
)


class CacheBackendType(Enum):
    """缓存后端类型"""

    MEMORY = "memory"
    REDIS = "redis"
    DISK = "disk"
    TIERED = "tiered"


@dataclass
class CacheStats:
    """缓存统计信息"""

    hits: int = 0
    misses: int = 0
    sets: int = 0
    deletes: int = 0
    total_entries: int = 0
    max_size: int = 0

    @property
    def hit_rate(self) -> float:
        """命中率"""
        total = self.hits + self.misses
        return (self.hits / total * 100) if total > 0 else 0.0

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "hits": self.hits,
            "misses": self.misses,
            "sets": self.sets,
            "deletes": self.deletes,
            "total_entries": self.total_entries,
            "max_size": self.max_size,
            "hit_rate": f"{self.hit_rate:.2f}%",
        }


@runtime_checkable
class CacheProtocol(Protocol):
    """
    统一缓存接口协议

    所有缓存实现必须遵循此接口。
    使用 Protocol 实现结构化子类型（鸭子类型）。
    """

    async def get(self, key: str) -> Any | None:
        """
        获取缓存值

        Args:
            key: 缓存键

        Returns:
            缓存值，不存在返回 None
        """
        ...

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """
        设置缓存值

        Args:
            key: 缓存键
            value: 缓存值
            ttl: 过期时间（秒），None 表示使用默认 TTL
        """
        ...

    async def delete(self, key: str) -> bool:
        """
        删除缓存

        Args:
            key: 缓存键

        Returns:
            是否成功删除
        """
        ...

    async def clear(self) -> None:
        """清空所有缓存"""
        ...

    async def get_or_set(self, key: str, factory: Callable[[], Awaitable[Any]], ttl: int | None = None) -> Any:
        """
        获取缓存值，如果不存在则调用工厂函数生成

        Args:
            key: 缓存键
            factory: 生成值的异步函数
            ttl: 过期时间（秒）

        Returns:
            缓存值或新生成的值
        """
        ...

    def get_stats(self) -> dict[str, Any]:
        """
        获取缓存统计信息

        Returns:
            统计信息字典
        """
        ...


@runtime_checkable
class BatchCacheProtocol(CacheProtocol, Protocol):
    """
    批量操作缓存接口

    扩展基础接口，支持批量操作
    """

    async def get_many(self, keys: list[str]) -> dict[str, Any]:
        """
        批量获取缓存值

        Args:
            keys: 缓存键列表

        Returns:
            {key: value} 字典，不存在的键不会包含在结果中
        """
        ...

    async def set_many(self, items: dict[str, Any], ttl: int | None = None) -> int:
        """
        批量设置缓存值

        Args:
            items: {key: value} 字典
            ttl: 过期时间（秒）

        Returns:
            成功设置的键数量
        """
        ...

    async def delete_many(self, keys: list[str]) -> int:
        """
        批量删除缓存

        Args:
            keys: 缓存键列表

        Returns:
            成功删除的键数量
        """
        ...


@runtime_checkable
class NamespacedCacheProtocol(CacheProtocol, Protocol):
    """
    命名空间缓存接口

    扩展基础接口，支持命名空间隔离
    """

    async def get(self, namespace: str, key: str) -> Any | None:
        """
        获取缓存值

        Args:
            namespace: 命名空间
            key: 缓存键

        Returns:
            缓存值，不存在返回 None
        """
        ...

    async def set(self, namespace: str, key: str, value: Any, ttl: int | None = None) -> None:
        """
        设置缓存值

        Args:
            namespace: 命名空间
            key: 缓存键
            value: 缓存值
            ttl: 过期时间（秒）
        """
        ...

    async def delete(self, namespace: str, key: str) -> bool:
        """
        删除缓存

        Args:
            namespace: 命名空间
            key: 缓存键

        Returns:
            是否成功删除
        """
        ...

    async def clear_namespace(self, namespace: str) -> None:
        """
        清空指定命名空间

        Args:
            namespace: 命名空间
        """
        ...

    async def invalidate_related(self, namespace: str, key: str | None = None, cascade: bool = True) -> dict[str, Any]:
        """
        失效缓存并级联失效关联命名空间

        Args:
            namespace: 命名空间
            key: 可选的特定键，None 表示失效整个命名空间
            cascade: 是否级联失效

        Returns:
            失效结果信息
        """
        ...


@runtime_checkable
class TieredCacheProtocol(CacheProtocol, Protocol):
    """
    多级缓存接口

    扩展基础接口，支持多级缓存操作
    """

    async def get(self, key: str, levels: list[str] | None = None) -> Any | None:
        """
        获取缓存值（按层级顺序）

        Args:
            key: 缓存键
            levels: 指定查询的层级，None 表示所有层级

        Returns:
            缓存值，不存在返回 None
        """
        ...

    async def set(self, key: str, value: Any, ttl: int | None = None, persist: bool = True) -> None:
        """
        设置缓存值

        Args:
            key: 缓存键
            value: 缓存值
            ttl: 过期时间（秒）
            persist: 是否持久化到下层缓存
        """
        ...

    async def warmup(self, keys: list[str]) -> int:
        """
        缓存预热 - 从下层缓存加载到上层

        Args:
            keys: 需要预热的键列表

        Returns:
            成功预热的键数量
        """
        ...

    def get_level_stats(self) -> dict[str, dict[str, Any]]:
        """
        获取各层级缓存统计信息

        Returns:
            {level: stats} 字典
        """
        ...


@runtime_checkable
class ManagedCacheProtocol(CacheProtocol, Protocol):
    """
    可管理缓存接口

    扩展基础接口，支持生命周期管理
    """

    async def start(self) -> None:
        """启动缓存服务"""
        ...

    async def stop(self) -> None:
        """停止缓存服务"""
        ...

    @property
    def is_running(self) -> bool:
        """是否正在运行"""
        ...

    async def cleanup_expired(self) -> int:
        """
        清理过期条目

        Returns:
            清理的条目数量
        """
        ...


# 类型别名
CacheBackend = CacheProtocol
NamespacedCacheBackend = NamespacedCacheProtocol
TieredCacheBackend = TieredCacheProtocol
ManagedCacheBackend = ManagedCacheProtocol
