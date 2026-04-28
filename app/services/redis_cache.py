"""
Redis缓存后端实现

提供高性能的Redis缓存支持，包括连接池管理、序列化、过期策略等

统一缓存接口说明:
- 本模块实现 CacheProtocol 接口
- 可作为 CacheManager 的可选后端使用
- 推荐通过 CacheManager.get_backend_adapter(BackendType.REDIS) 使用

使用示例:
    from app.core.cache_manager import get_cache_manager, BackendType

    cache = get_cache_manager()
    adapter = cache.get_backend_adapter(BackendType.REDIS)
    await adapter.set("key", "value", ttl=600)
"""

import asyncio
import json
import pickle
from typing import Any

import aioredis

# 重导出统一接口
from app.core.cache_interface import (
    CacheProtocol,
    CacheStats,
)
from app.core.logging import get_logger
from app.core.lru_cache import LRUCache


logger = get_logger(__name__)


class RedisCacheBackend:
    """
    Redis缓存后端实现

    特性：
    - 异步Redis连接支持
    - 本地L1缓存加速
    - 智能序列化/反序列化
    - 连接池管理
    - 自动重连机制
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        local_cache_size: int = 1000,
        default_ttl: int = 3600,
        connection_pool_size: int = 20,
    ):
        """
        初始化Redis缓存后端

        Args:
            redis_url: Redis连接URL
            local_cache_size: 本地L1缓存大小
            default_ttl: 默认过期时间（秒）
            connection_pool_size: 连接池大小
        """
        self.redis_url = redis_url
        self.default_ttl = default_ttl
        self.connection_pool_size = connection_pool_size

        # 本地L1缓存（快速访问）
        self.local_cache = LRUCache(maxsize=local_cache_size, ttl=default_ttl, enable_stats=True)

        # Redis客户端
        self.redis_client: aioredis.Redis | None = None
        self._connection_lock = asyncio.Lock()
        self._connected = False

        logger.info(f"RedisCacheBackend initialized: url={redis_url}, local_cache_size={local_cache_size}")

    async def connect(self) -> bool:
        """
        建立Redis连接

        Returns:
            连接是否成功
        """
        async with self._connection_lock:
            if self._connected and self.redis_client:
                return True

            try:
                self.redis_client = aioredis.from_url(
                    self.redis_url, encoding="utf-8", decode_responses=False, max_connections=self.connection_pool_size
                )

                # 测试连接
                await self.redis_client.ping()
                self._connected = True

                logger.info(f"Redis connected successfully: {self.redis_url}")
                return True

            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
                self._connected = False
                return False

    async def disconnect(self):
        """断开Redis连接"""
        async with self._connection_lock:
            if self.redis_client:
                await self.redis_client.close()
                self.redis_client = None
                self._connected = False
                logger.info("Redis disconnected")

    def _serialize(self, value: Any) -> bytes:
        """
        序列化值为字节

        Args:
            value: 要序列化的值

        Returns:
            序列化后的字节数据
        """
        try:
            # 尝试JSON序列化（人类可读）
            return json.dumps(value, ensure_ascii=False).encode("utf-8")
        except (TypeError, ValueError):
            # 回退到pickle序列化（二进制）
            return pickle.dumps(value)

    def _deserialize(self, data: bytes) -> Any:
        """
        反序列化字节数据

        Args:
            data: 要反序列化的字节数据

        Returns:
            反序列化后的值
        """
        if not data:
            return None

        try:
            # 尝试JSON反序列化
            return json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            # 回退到pickle反序列化
            return pickle.loads(data)

    async def get(self, key: str) -> Any | None:
        """
        获取缓存值

        Args:
            key: 缓存键

        Returns:
            缓存值，不存在返回None
        """
        # 1. 先查本地L1缓存
        local_result = self.local_cache.get(key)
        if local_result is not None:
            return local_result

        # 2. 再查Redis
        if not await self.connect():
            return None

        try:
            data = await self.redis_client.get(key)
            if data is None:
                return None

            value = self._deserialize(data)

            # 提升到本地缓存
            self.local_cache.set(key, value)

            return value

        except Exception as e:
            logger.error(f"Redis GET failed for key {key}: {e}")
            return None

    async def set(self, key: str, value: Any, ttl: int | None = None) -> bool:
        """
        设置缓存值

        Args:
            key: 缓存键
            value: 缓存值
            ttl: 过期时间（秒），None使用默认值

        Returns:
            设置是否成功
        """
        # 同时设置到本地缓存和Redis
        self.local_cache.set(key, value)

        if not await self.connect():
            return False

        try:
            data = self._serialize(value)
            expire_time = ttl if ttl is not None else self.default_ttl

            result = await self.redis_client.set(key, data, ex=expire_time)

            return result is True

        except Exception as e:
            logger.error(f"Redis SET failed for key {key}: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """
        删除缓存项

        Args:
            key: 缓存键

        Returns:
            删除是否成功
        """
        # 同时从本地缓存和Redis删除
        self.local_cache.delete(key)

        if not await self.connect():
            return False

        try:
            result = await self.redis_client.delete(key)
            return result > 0

        except Exception as e:
            logger.error(f"Redis DELETE failed for key {key}: {e}")
            return False

    async def exists(self, key: str) -> bool:
        """
        检查键是否存在

        Args:
            key: 缓存键

        Returns:
            键是否存在
        """
        # 先检查本地缓存
        if key in self.local_cache:
            return True

        if not await self.connect():
            return False

        try:
            return await self.redis_client.exists(key) > 0
        except Exception as e:
            logger.error(f"Redis EXISTS failed for key {key}: {e}")
            return False

    async def expire(self, key: str, ttl: int) -> bool:
        """
        设置键的过期时间

        Args:
            key: 缓存键
            ttl: 过期时间（秒）

        Returns:
            设置是否成功
        """
        if not await self.connect():
            return False

        try:
            return await self.redis_client.expire(key, ttl)
        except Exception as e:
            logger.error(f"Redis EXPIRE failed for key {key}: {e}")
            return False

    async def get_stats(self) -> dict[str, Any]:
        """
        获取缓存统计信息

        Returns:
            统计信息字典
        """
        # 获取本地缓存统计
        local_stats = self.local_cache.get_stats()

        # 获取Redis统计
        redis_stats = {}
        if await self.connect():
            try:
                info = await self.redis_client.info()
                redis_stats = {
                    "redis_version": info.get("redis_version"),
                    "used_memory": info.get("used_memory_human"),
                    "connected_clients": info.get("connected_clients"),
                    "total_commands_processed": info.get("total_commands_processed"),
                }
            except Exception as e:
                logger.error(f"Failed to get Redis stats: {e}")

        return {"local_cache": local_stats, "redis": redis_stats, "backend_type": "redis_with_local_cache"}

    async def flush_all(self) -> bool:
        """
        清空所有缓存

        Returns:
            清空是否成功
        """
        # 清空本地缓存
        self.local_cache.clear()

        if not await self.connect():
            return False

        try:
            await self.redis_client.flushall()
            return True
        except Exception as e:
            logger.error(f"Redis FLUSHALL failed: {e}")
            return False

    async def keys(self, pattern: str = "*") -> list:
        """
        获取匹配模式的键列表

        Args:
            pattern: 键模式

        Returns:
            匹配的键列表
        """
        if not await self.connect():
            return []

        try:
            return await self.redis_client.keys(pattern)
        except Exception as e:
            logger.error(f"Redis KEYS failed for pattern {pattern}: {e}")
            return []


class RedisCacheService:
    """
    Redis缓存服务封装

    提供更高层次的缓存操作接口
    """

    def __init__(self, redis_backend: RedisCacheBackend):
        """
        初始化Redis缓存服务

        Args:
            redis_backend: Redis缓存后端实例
        """
        self.backend = redis_backend
        self._lock = asyncio.Lock()

        logger.info("RedisCacheService initialized")

    async def get_or_set(self, key: str, factory, ttl: int | None = None) -> Any:
        """
        获取缓存值，如果不存在则调用工厂函数生成并缓存

        Args:
            key: 缓存键
            factory: 生成值的函数（可以是异步函数）
            ttl: 过期时间

        Returns:
            缓存值或新生成的值
        """
        async with self._lock:
            # 先尝试获取缓存
            value = await self.backend.get(key)
            if value is not None:
                return value

            # 缓存未命中，生成新值
            if asyncio.iscoroutinefunction(factory):
                value = await factory()
            else:
                value = factory()

            # 缓存新值
            await self.backend.set(key, value, ttl)

            return value

    async def batch_get(self, keys: list) -> dict[str, Any]:
        """
        批量获取缓存值

        Args:
            keys: 键列表

        Returns:
            {key: value} 字典
        """
        results = {}
        missing_keys = []

        # 先从本地缓存获取
        for key in keys:
            local_value = self.backend.local_cache.get(key)
            if local_value is not None:
                results[key] = local_value
            else:
                missing_keys.append(key)

        # 从Redis批量获取剩余的键
        if missing_keys and await self.backend.connect():
            try:
                # Redis MGET操作
                values = await self.backend.redis_client.mget(missing_keys)

                for key, value_data in zip(missing_keys, values):
                    if value_data is not None:
                        value = self.backend._deserialize(value_data)
                        results[key] = value
                        # 提升到本地缓存
                        self.backend.local_cache.set(key, value)

            except Exception as e:
                logger.error(f"Batch GET failed: {e}")

        return results

    async def batch_set(self, items: dict[str, Any], ttl: int | None = None) -> int:
        """
        批量设置缓存值

        Args:
            items: {key: value} 字典
            ttl: 过期时间

        Returns:
            成功设置的键数量
        """
        if not items:
            return 0

        success_count = 0

        # 同时设置到本地缓存
        for key, value in items.items():
            self.backend.local_cache.set(key, value)

        # 批量设置到Redis
        if await self.backend.connect():
            try:
                pipe = self.backend.redis_client.pipeline()

                for key, value in items.items():
                    data = self.backend._serialize(value)
                    expire_time = ttl if ttl is not None else self.backend.default_ttl
                    pipe.setex(key, expire_time, data)

                results = await pipe.execute()
                success_count = sum(1 for result in results if result)

            except Exception as e:
                logger.error(f"Batch SET failed: {e}")

        return success_count


# 全局实例管理
_global_redis_backend: RedisCacheBackend | None = None
_global_redis_service: RedisCacheService | None = None


def get_redis_cache_backend(
    redis_url: str = "redis://localhost:6379", local_cache_size: int = 1000, default_ttl: int = 3600
) -> RedisCacheBackend:
    """
    获取全局Redis缓存后端实例

    Args:
        redis_url: Redis连接URL
        local_cache_size: 本地缓存大小
        default_ttl: 默认过期时间

    Returns:
        Redis缓存后端实例
    """
    global _global_redis_backend

    if _global_redis_backend is None:
        _global_redis_backend = RedisCacheBackend(
            redis_url=redis_url, local_cache_size=local_cache_size, default_ttl=default_ttl
        )

    return _global_redis_backend


def get_redis_cache_service(redis_url: str = "redis://localhost:6379") -> RedisCacheService:
    """
    获取全局Redis缓存服务实例

    Args:
        redis_url: Redis连接URL

    Returns:
        Redis缓存服务实例
    """
    global _global_redis_service

    if _global_redis_service is None:
        backend = get_redis_cache_backend(redis_url)
        _global_redis_service = RedisCacheService(backend)

    return _global_redis_service


# 导出所有公共接口
__all__ = [
    # 统一接口
    "CacheProtocol",
    "CacheStats",
    # 本地接口
    "RedisCacheBackend",
    "RedisCacheService",
    "get_redis_cache_backend",
    "get_redis_cache_service",
]
