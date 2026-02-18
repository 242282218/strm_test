"""
Cache interface abstraction.

Provides a unified interface for all cache implementations.
"""

from abc import ABC, abstractmethod
from typing import Any, Optional, Dict


class CacheInterface(ABC):
    """
    Abstract base class for cache implementations.

    All cache backends must implement this interface.
    """

    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """
        Get a value from the cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        pass

    @abstractmethod
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """
        Set a value in the cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds (None for default)
        """
        pass

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """
        Delete a value from the cache.

        Args:
            key: Cache key

        Returns:
            True if deleted, False if not found
        """
        pass

    @abstractmethod
    async def clear(self) -> None:
        """Clear all cached values."""
        pass

    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary containing cache statistics
        """
        pass

    async def exists(self, key: str) -> bool:
        """
        Check if a key exists in the cache.

        Args:
            key: Cache key

        Returns:
            True if exists and not expired
        """
        return await self.get(key) is not None

    async def get_or_set(
        self,
        key: str,
        factory,
        ttl: Optional[int] = None
    ) -> Any:
        """
        Get a value, or set it using factory if not found.

        Args:
            key: Cache key
            factory: Callable (sync or async) to generate value
            ttl: Time-to-live in seconds

        Returns:
            Cached or newly generated value
        """
        import asyncio

        value = await self.get(key)
        if value is not None:
            return value

        if asyncio.iscoroutinefunction(factory):
            value = await factory()
        else:
            value = factory()

        await self.set(key, value, ttl)
        return value


class CacheBackend(ABC):
    """
    Abstract base class for cache backend configuration.
    """

    @abstractmethod
    def create_cache(self) -> CacheInterface:
        """Create and return a cache instance."""
        pass
