# -*- coding: utf-8 -*-
"""
缓存服务模块

提供统一的缓存接口,支持:
- 内存缓存(默认)
- Redis缓存(可选)
- TTL过期机制
- LRU淘汰策略
- 缓存统计

参考: QMediaSync 缓存设计
"""

import asyncio
import time
from typing import Any, Optional, Dict
from app.core.lru_cache import LRUCache as CustomLRUCache
from app.core.logging import get_logger

logger = get_logger(__name__)


class CacheEntry:
    """缓存条目"""
    
    def __init__(self, value: Any, ttl: Optional[int] = None):
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
    
    def __init__(
        self,
        max_size: int = 1000,
        default_ttl: int = 600
    ):
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
    
    async def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        async with self._lock:
            value = self._cache.get(key)
            return value
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> None:
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
        return {
            **lru_stats,
            'max_size': self.max_size,
            'default_ttl': self.default_ttl
        }


class CacheService:
    """
    统一缓存服务
    
    支持内存缓存和Redis缓存
    """
    
    def __init__(
        self,
        backend: str = "memory",
        max_size: int = 1000,
        default_ttl: int = 600,
        redis_url: Optional[str] = None
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
        
        self._cleanup_task: Optional[asyncio.Task] = None
        logger.info(f"CacheService initialized with backend: {backend}")
    
    async def start(self):
        """启动缓存服务"""
        # 启动定期清理任务
        self._cleanup_task = asyncio.create_task(self._periodic_cleanup())
        logger.info("CacheService started")
    
    async def stop(self):
        """停止缓存服务"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        logger.info("CacheService stopped")
    
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
    
    async def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        return await self._cache.get(key)
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> None:
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
        return self._cache.get_stats()
    
    async def get_or_set(
        self,
        key: str,
        factory,
        ttl: Optional[int] = None
    ) -> Any:
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
        if hasattr(self._cache, 'get_or_set'):
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


# 全局缓存实例
_global_cache: Optional[CacheService] = None


def get_cache_service(
    max_size: int = 1000,
    default_ttl: int = 600
) -> CacheService:
    """获取全局缓存服务实例"""
    global _global_cache
    
    if _global_cache is None:
        _global_cache = CacheService(
            backend="memory",
            max_size=max_size,
            default_ttl=default_ttl
        )
    
    return _global_cache
