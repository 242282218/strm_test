"""
直链缓存与刷新机制

参考: go-emby2openlist internal/web/cache/cache.go
"""

import time
import asyncio
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from app.core.logging import get_logger

logger = get_logger(__name__)


class CacheEntry:
    """缓存条目"""

    def __init__(
        self,
        key: str,
        value: Any,
        headers: Optional[Dict[str, str]] = None,
        ttl: int = 600
    ):
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

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "key": self.key,
            "value": self.value,
            "headers": self.headers,
            "ttl": self.ttl,
            "created_at": datetime.fromtimestamp(self.created_at).isoformat(),
            "expires_at": datetime.fromtimestamp(self.expires_at).isoformat(),
            "access_count": self.access_count,
            "last_accessed_at": datetime.fromtimestamp(self.last_accessed_at).isoformat()
        }


class LinkCache:
    """直链缓存服务"""

    def __init__(
        self,
        default_ttl: int = 600,
        max_size: int = 1000,
        cleanup_interval: int = 300
    ):
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
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = asyncio.Lock()
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False
        logger.info(f"LinkCache initialized: default_ttl={default_ttl}s, max_size={max_size}")

    def _generate_cache_key(
        self,
        file_id: str,
        range_header: Optional[str] = None,
        **kwargs
    ) -> str:
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

    async def get(
        self,
        file_id: str,
        range_header: Optional[str] = None,
        **kwargs
    ) -> Optional[CacheEntry]:
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
        headers: Optional[Dict[str, str]] = None,
        ttl: Optional[int] = None,
        range_header: Optional[str] = None,
        **kwargs
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

            entry = CacheEntry(
                key=cache_key,
                value=value,
                headers=headers,
                ttl=cache_ttl
            )
            self._cache[cache_key] = entry
            logger.debug(f"Cache set: {cache_key}, ttl={cache_ttl}s")

    async def delete(
        self,
        file_id: str,
        range_header: Optional[str] = None,
        **kwargs
    ) -> bool:
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
        sorted_entries = sorted(
            self._cache.items(),
            key=lambda x: x[1].last_accessed_at
        )

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
        logger.info("LinkCache started")

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

        logger.info("LinkCache stopped")

    async def clear(self):
        """清空缓存"""
        async with self._lock:
            self._cache.clear()
            logger.info("LinkCache cleared")

    def get_stats(self) -> Dict[str, Any]:
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
            "running": self._running
        }

_global_link_cache: Optional["LinkCache"] = None


def get_link_cache_service(
    default_ttl: int = 600,
    max_size: int = 1000,
    cleanup_interval: int = 300
) -> "LinkCache":
    """
    Return a process-wide singleton LinkCache service.
    """
    global _global_link_cache
    if _global_link_cache is None:
        _global_link_cache = LinkCache(
            default_ttl=default_ttl,
            max_size=max_size,
            cleanup_interval=cleanup_interval
        )
    return _global_link_cache
