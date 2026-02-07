# -*- coding: utf-8 -*-
"""
多级缓存服务 - L1内存 + L2磁盘 + L3Redis

提供高性能、持久化的缓存解决方案：
- L1: 内存缓存（最快，重启丢失）
- L2: 磁盘缓存（SQLite，持久化，服务重启保留）
- L3: Redis缓存（分布式，可选）

读取顺序: L1 -> L2 -> L3
写入顺序: L1 -> L2 -> L3（异步）
"""

import asyncio
from typing import Any, Optional, Dict, List, Callable
from dataclasses import dataclass
from enum import Enum
from app.core.logging import get_logger
from app.services.cache_service import MemoryCache
from app.services.disk_cache import DiskCache

logger = get_logger(__name__)


class CacheLevel(Enum):
    """缓存级别"""
    L1_MEMORY = "memory"      # 内存缓存
    L2_DISK = "disk"          # 磁盘缓存
    L3_REDIS = "redis"        # Redis缓存


@dataclass
class CacheConfig:
    """缓存配置"""
    enable_l1: bool = True                    # 启用内存缓存
    enable_l2: bool = True                    # 启用磁盘缓存
    enable_l3: bool = False                   # 启用Redis缓存
    l1_max_size: int = 1000                   # L1最大条目数
    l1_default_ttl: int = 600                 # L1默认TTL（秒）
    l2_db_path: str = "cache/cache.db"        # L2数据库路径
    l2_default_ttl: int = 3600                # L2默认TTL（秒）
    l3_redis_url: str = "redis://localhost:6379"  # L3 Redis URL
    l3_default_ttl: int = 7200                # L3默认TTL（秒）


class TieredCache:
    """
    多级缓存实现
    
    自动管理 L1/L2/L3 三级缓存，提供最优的性能和持久化平衡
    """
    
    def __init__(self, config: CacheConfig = None):
        """
        初始化多级缓存
        
        Args:
            config: 缓存配置
        """
        self.config = config or CacheConfig()
        
        # 初始化各级缓存
        self._l1_cache: Optional[MemoryCache] = None
        self._l2_cache: Optional[DiskCache] = None
        self._l3_cache: Optional[Any] = None
        
        self._init_caches()
        
        # 异步写入队列（用于L2/L3的异步写入）
        self._write_queue: asyncio.Queue = asyncio.Queue()
        self._write_task: Optional[asyncio.Task] = None
        
        logger.info(f"TieredCache initialized: L1={self.config.enable_l1}, L2={self.config.enable_l2}, L3={self.config.enable_l3}")
    
    def _init_caches(self):
        """初始化各级缓存实例"""
        if self.config.enable_l1:
            self._l1_cache = MemoryCache(
                max_size=self.config.l1_max_size,
                default_ttl=self.config.l1_default_ttl
            )
        
        if self.config.enable_l2:
            self._l2_cache = DiskCache(
                db_path=self.config.l2_db_path,
                default_ttl=self.config.l2_default_ttl
            )
        
        if self.config.enable_l3:
            try:
                from app.services.redis_cache import get_redis_cache_backend
                self._l3_cache = get_redis_cache_backend(
                    redis_url=self.config.l3_redis_url,
                    default_ttl=self.config.l3_default_ttl
                )
            except Exception as e:
                logger.warning(f"Failed to initialize L3 Redis cache: {e}")
                self.config.enable_l3 = False
    
    async def start(self):
        """启动多级缓存服务"""
        # 启动L2磁盘缓存
        if self._l2_cache:
            await self._l2_cache.start()
        
        # 启动异步写入任务
        self._write_task = asyncio.create_task(self._async_write_worker())
        
        logger.info("TieredCache started")
    
    async def stop(self):
        """停止多级缓存服务"""
        # 停止异步写入任务
        if self._write_task:
            self._write_task.cancel()
            try:
                await self._write_task
            except asyncio.CancelledError:
                pass
        
        # 停止L2磁盘缓存
        if self._l2_cache:
            await self._l2_cache.stop()
        
        logger.info("TieredCache stopped")
    
    async def _async_write_worker(self):
        """异步写入工作线程（用于L2/L3的异步写入）"""
        while True:
            try:
                key, value, ttl = await self._write_queue.get()
                
                # 写入L2
                if self._l2_cache:
                    try:
                        await self._l2_cache.set(key, value, ttl)
                    except Exception as e:
                        logger.warning(f"L2 cache write failed for key {key}: {e}")
                
                # 写入L3
                if self._l3_cache:
                    try:
                        await self._l3_cache.set(key, value, ttl)
                    except Exception as e:
                        logger.warning(f"L3 cache write failed for key {key}: {e}")
                
                self._write_queue.task_done()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Async write worker error: {e}")
    
    async def get(self, key: str) -> Optional[Any]:
        """
        获取缓存值（按 L1 -> L2 -> L3 顺序）
        
        Args:
            key: 缓存键
            
        Returns:
            缓存值，不存在返回 None
        """
        # 1. 尝试从L1获取
        if self._l1_cache:
            value = await self._l1_cache.get(key)
            if value is not None:
                logger.debug(f"L1 cache hit for key: {key}")
                return value
        
        # 2. 尝试从L2获取
        if self._l2_cache:
            value = await self._l2_cache.get(key)
            if value is not None:
                logger.debug(f"L2 cache hit for key: {key}")
                # 回填到L1
                if self._l1_cache:
                    await self._l1_cache.set(key, value)
                return value
        
        # 3. 尝试从L3获取
        if self._l3_cache:
            value = await self._l3_cache.get(key)
            if value is not None:
                logger.debug(f"L3 cache hit for key: {key}")
                # 回填到L1和L2
                if self._l1_cache:
                    await self._l1_cache.set(key, value)
                if self._l2_cache:
                    await self._l2_cache.set(key, value)
                return value
        
        logger.debug(f"Cache miss for key: {key}")
        return None
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        persist: bool = True
    ) -> bool:
        """
        设置缓存值
        
        Args:
            key: 缓存键
            value: 缓存值
            ttl: 过期时间（秒）
            persist: 是否持久化到L2/L3
            
        Returns:
            设置是否成功
        """
        success = True
        
        # 1. 写入L1（同步）
        if self._l1_cache:
            try:
                await self._l1_cache.set(key, value, ttl)
            except Exception as e:
                logger.warning(f"L1 cache write failed for key {key}: {e}")
                success = False
        
        # 2. 写入L2/L3（异步或同步）
        if persist:
            if self._l2_cache or self._l3_cache:
                # 使用异步队列写入，避免阻塞主线程
                try:
                    self._write_queue.put_nowait((key, value, ttl))
                except asyncio.QueueFull:
                    # 队列满时同步写入
                    if self._l2_cache:
                        await self._l2_cache.set(key, value, ttl)
                    if self._l3_cache:
                        await self._l3_cache.set(key, value, ttl)
        
        return success
    
    async def delete(self, key: str) -> bool:
        """删除缓存（所有层级）"""
        results = []
        
        if self._l1_cache:
            results.append(await self._l1_cache.delete(key))
        
        if self._l2_cache:
            results.append(await self._l2_cache.delete(key))
        
        if self._l3_cache:
            results.append(await self._l3_cache.delete(key))
        
        return any(results)
    
    async def clear(self) -> bool:
        """清空所有缓存"""
        results = []
        
        if self._l1_cache:
            results.append(await self._l1_cache.clear())
        
        if self._l2_cache:
            results.append(await self._l2_cache.clear())
        
        if self._l3_cache:
            results.append(await self._l3_cache.flush_all())
        
        return all(results)
    
    async def get_or_set(
        self,
        key: str,
        factory: Callable,
        ttl: Optional[int] = None,
        persist: bool = True
    ) -> Any:
        """
        获取缓存值，如果不存在则调用工厂函数生成
        
        Args:
            key: 缓存键
            factory: 生成值的函数（可以是异步函数）
            ttl: 过期时间（秒）
            persist: 是否持久化
            
        Returns:
            缓存值或新生成的值
        """
        # 尝试获取缓存
        value = await self.get(key)
        if value is not None:
            return value
        
        # 缓存未命中，生成新值
        if asyncio.iscoroutinefunction(factory):
            value = await factory()
        else:
            value = factory()
        
        # 写入缓存
        await self.set(key, value, ttl, persist)
        
        return value
    
    async def get_stats(self) -> Dict[str, Any]:
        """获取各级缓存统计信息"""
        stats = {
            'tiered_cache': {
                'l1_enabled': self.config.enable_l1,
                'l2_enabled': self.config.enable_l2,
                'l3_enabled': self.config.enable_l3,
            }
        }
        
        if self._l1_cache:
            stats['l1_memory'] = self._l1_cache.get_stats()
        
        if self._l2_cache:
            stats['l2_disk'] = await self._l2_cache.get_stats()
        
        if self._l3_cache:
            stats['l3_redis'] = await self._l3_cache.get_stats()
        
        return stats
    
    async def warmup(self, keys: List[str]) -> int:
        """
        缓存预热 - 从L2/L3加载到L1
        
        Args:
            keys: 需要预热的键列表
            
        Returns:
            成功预热的键数量
        """
        if not self._l1_cache or not keys:
            return 0
        
        warmed = 0
        
        # 从L2批量获取
        if self._l2_cache:
            l2_values = await self._l2_cache.get_many(keys)
            for key, value in l2_values.items():
                await self._l1_cache.set(key, value)
                warmed += 1
        
        # 从L3获取剩余的键
        remaining_keys = [k for k in keys if k not in (l2_values if self._l2_cache else {})]
        if self._l3_cache and remaining_keys:
            for key in remaining_keys:
                value = await self._l3_cache.get(key)
                if value is not None:
                    await self._l1_cache.set(key, value)
                    if self._l2_cache:
                        await self._l2_cache.set(key, value)
                    warmed += 1
        
        logger.info(f"Cache warmup completed: {warmed}/{len(keys)} keys warmed")
        return warmed


# 全局实例
_global_tiered_cache: Optional[TieredCache] = None


def get_tiered_cache(config: CacheConfig = None) -> TieredCache:
    """获取全局多级缓存实例"""
    global _global_tiered_cache
    
    if _global_tiered_cache is None:
        _global_tiered_cache = TieredCache(config or CacheConfig())
    
    return _global_tiered_cache
