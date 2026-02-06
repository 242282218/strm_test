import asyncio
import pytest

from app.services.cache_service import MemoryCache, CacheService


@pytest.mark.asyncio
async def test_memory_cache_respects_default_ttl():
    cache = MemoryCache(max_size=10, default_ttl=0.01)
    await cache.set("a", "1")
    await asyncio.sleep(0.02)
    assert await cache.get("a") is None


@pytest.mark.asyncio
async def test_memory_cache_respects_per_key_ttl():
    cache = MemoryCache(max_size=10, default_ttl=0.01)
    await cache.set("a", "1", ttl=0.1)
    await asyncio.sleep(0.02)
    assert await cache.get("a") == "1"


@pytest.mark.asyncio
async def test_cache_service_per_key_ttl_overrides_default():
    service = CacheService(backend="memory", max_size=10, default_ttl=0.01)
    await service.set("a", "1", ttl=0.1)
    await asyncio.sleep(0.02)
    assert await service.get("a") == "1"
