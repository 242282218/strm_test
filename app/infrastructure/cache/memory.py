"""
Memory cache implementation.

Provides in-memory LRU cache with TTL support.
"""

import asyncio
import time
from collections import OrderedDict
from typing import Any, Optional, Dict

from app.infrastructure.cache.base import CacheInterface
from app.core.logging import get_logger

logger = get_logger(__name__)


class MemoryCache(CacheInterface):
    """
    In-memory LRU cache implementation.

    Features:
    - LRU eviction policy
    - TTL (time-to-live) support
    - Thread/coroutine safe
    - Detailed statistics
    """

    def __init__(
        self,
        maxsize: int = 1000,
        default_ttl: Optional[int] = 3600,
        enable_stats: bool = True
    ):
        """
        Initialize memory cache.

        Args:
            maxsize: Maximum number of entries
            default_ttl: Default TTL in seconds (None for no expiration)
            enable_stats: Enable statistics tracking
        """
        self.maxsize = maxsize
        self.default_ttl = default_ttl
        self.enable_stats = enable_stats

        self._cache: OrderedDict[str, tuple] = OrderedDict()
        self._lock = asyncio.Lock()

        self._stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "deletes": 0,
            "evictions": 0,
            "expirations": 0,
        }

        logger.info(
            f"MemoryCache initialized: maxsize={maxsize}, default_ttl={default_ttl}"
        )

    async def get(self, key: str) -> Optional[Any]:
        async with self._lock:
            if key not in self._cache:
                if self.enable_stats:
                    self._stats["misses"] += 1
                return None

            value, timestamp, entry_ttl = self._cache[key]

            effective_ttl = entry_ttl if entry_ttl is not None else self.default_ttl
            if effective_ttl is not None and (time.time() - timestamp) > effective_ttl:
                del self._cache[key]
                if self.enable_stats:
                    self._stats["expirations"] += 1
                    self._stats["misses"] += 1
                return None

            self._cache.move_to_end(key)

            if self.enable_stats:
                self._stats["hits"] += 1

            return value

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        async with self._lock:
            if key in self._cache:
                del self._cache[key]

            if len(self._cache) >= self.maxsize:
                oldest_key, _ = self._cache.popitem(last=False)
                if self.enable_stats:
                    self._stats["evictions"] += 1
                logger.debug(f"Evicted LRU entry: {oldest_key}")

            entry_ttl = ttl if ttl is not None else None
            self._cache[key] = (value, time.time(), entry_ttl)

            if self.enable_stats:
                self._stats["sets"] += 1

    async def delete(self, key: str) -> bool:
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                if self.enable_stats:
                    self._stats["deletes"] += 1
                return True
            return False

    async def clear(self) -> None:
        async with self._lock:
            count = len(self._cache)
            self._cache.clear()
            logger.info(f"Cache cleared: {count} entries removed")

    def get_stats(self) -> Dict[str, Any]:
        if not self.enable_stats:
            return {}

        total_requests = self._stats["hits"] + self._stats["misses"]
        hit_rate = (
            self._stats["hits"] / total_requests * 100 if total_requests > 0 else 0
        )

        return {
            **self._stats,
            "size": len(self._cache),
            "max_size": self.maxsize,
            "hit_rate": f"{hit_rate:.2f}%",
            "total_requests": total_requests,
            "default_ttl": self.default_ttl,
        }

    async def cleanup_expired(self) -> int:
        async with self._lock:
            current_time = time.time()
            expired_keys = []

            for key, (_, timestamp, entry_ttl) in self._cache.items():
                effective_ttl = entry_ttl if entry_ttl is not None else self.default_ttl
                if effective_ttl is None:
                    continue
                if (current_time - timestamp) > effective_ttl:
                    expired_keys.append(key)

            for key in expired_keys:
                del self._cache[key]

            if expired_keys and self.enable_stats:
                self._stats["expirations"] += len(expired_keys)
                logger.debug(f"Cleaned up {len(expired_keys)} expired entries")

            return len(expired_keys)

    def __len__(self) -> int:
        return len(self._cache)
