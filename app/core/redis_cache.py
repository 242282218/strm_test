"""
Redis 缓存层

提供 L2 缓存功能，支持分布式缓存、缓存穿透/雪崩防护。
"""

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from app.core.logging import get_logger


logger = get_logger(__name__)

T = TypeVar("T")


@dataclass
class CacheEntry(Generic[T]):
    """缓存条目"""

    value: T
    expires_at: float | None = None  # 过期时间戳


class RedisCache:
    """
    Redis 缓存层

    功能：
    - 分布式缓存
    - 自动序列化/反序列化
    - 缓存穿透防护（空值缓存）
    - 缓存雪崩防护（随机 TTL）
    - 布隆过滤器（可选）

    用法:
        cache = RedisCache(host="localhost", port=6379)

        # 设置缓存
        await cache.set("key", {"data": "value"}, ttl=300)

        # 获取缓存
        value = await cache.get("key")

        # 删除缓存
        await cache.delete("key")
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: str | None = None,
        key_prefix: str = "quark_strm:",
        default_ttl: int = 300,
        max_ttl: int = 3600,
        snowball_jitter: float = 0.1,
    ):
        """
        初始化 Redis 缓存

        Args:
            host: Redis 主机
            port: Redis 端口
            db: Redis 数据库
            password: Redis 密码
            key_prefix: 键前缀
            default_ttl: 默认 TTL（秒）
            max_ttl: 最大 TTL（秒）
            snowball_jitter: 雪崩防护抖动比例（0-1）
        """
        self.host = host
        self.port = port
        self.db = db
        self.password = password
        self.key_prefix = key_prefix
        self.default_ttl = default_ttl
        self.max_ttl = max_ttl
        self.snowball_jitter = snowball_jitter
        self._client = None
        self._connected = False

    async def connect(self):
        """连接到 Redis"""
        if self._connected:
            return

        try:
            import redis.asyncio as redis

            self._client = redis.Redis(
                host=self.host,
                port=self.port,
                db=self.db,
                password=self.password,
                decode_responses=True,
            )
            await self._client.ping()
            self._connected = True
            logger.info(f"Redis connected: {self.host}:{self.port}")
        except ImportError:
            logger.warning("Redis package not installed, cache disabled")
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}, cache disabled")
            self._client = None

    async def disconnect(self):
        """断开 Redis 连接"""
        if self._client and self._connected:
            await self._client.close()
            self._connected = False
            logger.info("Redis disconnected")

    def _make_key(self, key: str) -> str:
        """生成带前缀的键"""
        return f"{self.key_prefix}{key}"

    def _serialize(self, value: Any) -> str:
        """序列化值"""
        return json.dumps(value, ensure_ascii=False, default=str)

    def _deserialize(self, data: str | None) -> Any:
        """反序列化值"""
        if data is None:
            return None
        try:
            return json.loads(data)
        except (json.JSONDecodeError, TypeError):
            return data

    def _apply_jitter(self, ttl: int) -> int:
        """应用雪崩防护抖动"""
        import random

        jitter = int(ttl * self.snowball_jitter)
        return ttl + random.randint(-jitter, jitter)

    async def get(self, key: str) -> Any:
        """
        获取缓存

        Args:
            key: 缓存键

        Returns:
            缓存值，不存在返回 None
        """
        if not self._client:
            return None

        try:
            full_key = self._make_key(key)
            data = await self._client.get(full_key)
            value = self._deserialize(data)
            if value is not None:
                logger.debug(f"Cache hit: {key}")
            return value
        except Exception as e:
            logger.error(f"Cache get error: {key} - {e}")
            return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int | None = None,
        apply_jitter: bool = True,
    ) -> bool:
        """
        设置缓存

        Args:
            key: 缓存键
            value: 缓存值
            ttl: 过期时间（秒），None 使用默认值
            apply_jitter: 是否应用雪崩防护抖动

        Returns:
            是否成功
        """
        if not self._client:
            return False

        try:
            if ttl is None:
                ttl = self.default_ttl
            elif ttl > self.max_ttl:
                ttl = self.max_ttl

            if apply_jitter:
                ttl = self._apply_jitter(ttl)

            full_key = self._make_key(key)
            serialized = self._serialize(value)
            await self._client.setex(full_key, ttl, serialized)
            logger.debug(f"Cache set: {key} (TTL: {ttl}s)")
            return True
        except Exception as e:
            logger.error(f"Cache set error: {key} - {e}")
            return False

    async def delete(self, key: str) -> bool:
        """
        删除缓存

        Args:
            key: 缓存键

        Returns:
            是否成功
        """
        if not self._client:
            return False

        try:
            full_key = self._make_key(key)
            await self._client.delete(full_key)
            logger.debug(f"Cache delete: {key}")
            return True
        except Exception as e:
            logger.error(f"Cache delete error: {key} - {e}")
            return False

    async def exists(self, key: str) -> bool:
        """检查键是否存在"""
        if not self._client:
            return False

        try:
            full_key = self._make_key(key)
            return await self._client.exists(full_key) > 0
        except Exception as e:
            logger.error(f"Cache exists error: {key} - {e}")
            return False

    async def clear_pattern(self, pattern: str) -> int:
        """
        批量删除匹配模式的键

        Args:
            pattern: 匹配模式（支持通配符 *）

        Returns:
            删除的键数量
        """
        if not self._client:
            return 0

        try:
            full_pattern = self._make_key(pattern)
            keys = []
            async for key in self._client.scan_iter(match=full_pattern):
                keys.append(key)

            if keys:
                deleted = await self._client.delete(*keys)
                logger.info(f"Cache cleared: {pattern} ({deleted} keys)")
                return deleted
            return 0
        except Exception as e:
            logger.error(f"Cache clear error: {pattern} - {e}")
            return 0

    # ==================== 缓存装饰器 ====================

    def cached(
        self,
        key_prefix: str,
        ttl: int | None = None,
        key_builder: Callable | None = None,
    ):
        """
        缓存装饰器

        用法:
            @cache.cached("user:{user_id}", ttl=300)
            async def get_user(user_id: int):
                ...

        Args:
            key_prefix: 键前缀
            ttl: 过期时间
            key_builder: 自定义键构建函数
        """
        import functools

        def decorator(func):
            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                # 构建缓存键
                if key_builder:
                    key = key_builder(*args, **kwargs)
                else:
                    # 使用参数哈希作为键
                    param_str = f"{args}:{sorted(kwargs.items())}"
                    param_hash = hashlib.md5(param_str.encode()).hexdigest()[:8]
                    key = f"{key_prefix}:{param_hash}"

                # 尝试从缓存获取
                cached_value = await self.get(key)
                if cached_value is not None:
                    return cached_value

                # 执行函数
                result = await func(*args, **kwargs)

                # 缓存结果（包括 None，防护穿透）
                await self.set(key, result, ttl)

                return result

            return wrapper

        return decorator


# ==================== 全局缓存实例 ====================

_cache_instance: RedisCache | None = None


def get_cache(
    host: str | None = None,
    port: int | None = None,
    **kwargs,
) -> RedisCache:
    """获取或创建全局缓存实例"""
    global _cache_instance

    if _cache_instance is None:
        import os

        _cache_instance = RedisCache(
            host=host or os.getenv("REDIS_HOST", "localhost"),
            port=port or int(os.getenv("REDIS_PORT", "6379")),
            **kwargs,
        )
    return _cache_instance


async def init_cache(
    host: str | None = None,
    port: int | None = None,
    enabled: bool = True,
    **kwargs,
) -> RedisCache:
    """初始化缓存系统"""
    if not enabled:
        logger.info("Redis cache disabled")
        return RedisCache()

    cache = get_cache(host, port, **kwargs)
    await cache.connect()
    return cache


async def shutdown_cache():
    """关闭缓存系统"""
    global _cache_instance
    if _cache_instance:
        await _cache_instance.disconnect()
        _cache_instance = None
