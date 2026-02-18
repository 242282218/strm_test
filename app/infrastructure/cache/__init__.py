"""
Cache infrastructure module.

Provides unified cache implementations.
"""

from app.infrastructure.cache.base import CacheInterface, CacheBackend
from app.infrastructure.cache.memory import MemoryCache

__all__ = [
    "CacheInterface",
    "CacheBackend",
    "MemoryCache",
]
