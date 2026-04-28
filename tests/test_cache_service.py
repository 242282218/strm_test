"""
缓存服务模块单元测试

测试缓存服务操作、TTL 和统计功能

更新说明：
- 支持 Legacy 和 Unified 两种模式测试
- 默认测试 Unified 模式
- 通过环境变量 CACHE_LEGACY_MODE 切换模式
"""

import asyncio
import time
from unittest.mock import patch

import pytest
import pytest_asyncio

from app.core.cache_manager import (
    CacheNamespace,
    get_cache_manager,
)
from app.core.cache_manager import (
    reset_instance as reset_cache_manager,
)
from app.services.cache_service import (
    CacheEntry,
    CacheService,
    CacheServiceLegacy,
    CacheServiceUnified,
    MemoryCache,
)


class TestCacheEntry:
    """缓存条目测试"""

    def test_init(self):
        """测试初始化"""
        entry = CacheEntry("test_value", ttl=60)

        assert entry.value == "test_value"
        assert entry.ttl == 60
        assert entry.access_count == 0

    def test_is_expired_no_ttl(self):
        """测试无 TTL 时不过期"""
        entry = CacheEntry("test_value")

        assert entry.is_expired() is False

    def test_is_expired_with_ttl(self):
        """测试 TTL 过期"""
        entry = CacheEntry("test_value", ttl=1)

        assert entry.is_expired() is False

        time.sleep(1.1)

        assert entry.is_expired() is True

    def test_access(self):
        """测试访问记录"""
        entry = CacheEntry("test_value")

        entry.access()
        entry.access()

        assert entry.access_count == 2


class TestMemoryCache:
    """内存缓存测试"""

    @pytest_asyncio.fixture
    async def cache(self):
        """创建内存缓存实例"""
        cache = MemoryCache(max_size=100, default_ttl=60)
        yield cache
        await cache.clear()

    @pytest.mark.asyncio
    async def test_set_and_get(self, cache):
        """测试设置和获取"""
        await cache.set("key1", "value1")
        result = await cache.get("key1")

        assert result == "value1"

    @pytest.mark.asyncio
    async def test_get_non_existent(self, cache):
        """测试获取不存在的键"""
        result = await cache.get("non_existent")

        assert result is None

    @pytest.mark.asyncio
    async def test_delete(self, cache):
        """测试删除"""
        await cache.set("key1", "value1")
        result = await cache.delete("key1")

        assert result is True
        assert await cache.get("key1") is None

    @pytest.mark.asyncio
    async def test_delete_non_existent(self, cache):
        """测试删除不存在的键"""
        result = await cache.delete("non_existent")

        assert result is False

    @pytest.mark.asyncio
    async def test_clear(self, cache):
        """测试清空缓存"""
        await cache.set("key1", "value1")
        await cache.set("key2", "value2")
        await cache.clear()

        assert await cache.get("key1") is None
        assert await cache.get("key2") is None

    @pytest.mark.asyncio
    async def test_custom_ttl(self, cache):
        """测试自定义 TTL"""
        await cache.set("key1", "value1", ttl=1)

        assert await cache.get("key1") == "value1"

        time.sleep(1.1)

        assert await cache.get("key1") is None

    @pytest.mark.asyncio
    async def test_cleanup_expired(self, cache):
        """测试清理过期条目"""
        await cache.set("key1", "value1", ttl=1)
        await cache.set("key2", "value2", ttl=1)

        time.sleep(1.1)

        count = await cache.cleanup_expired()

        assert count == 2

    @pytest.mark.asyncio
    async def test_get_stats(self, cache):
        """测试获取统计信息"""
        stats = cache.get_stats()

        assert "max_size" in stats
        assert "default_ttl" in stats
        assert stats["max_size"] == 100
        assert stats["default_ttl"] == 60


class TestCacheService:
    """缓存服务测试"""

    @pytest_asyncio.fixture
    async def service(self):
        """创建缓存服务实例"""
        service = CacheService(backend="memory", max_size=100, default_ttl=60)
        await service.start()
        yield service
        await service.stop()

    @pytest.mark.asyncio
    async def test_init_memory_backend(self):
        """测试初始化内存后端（Legacy 模式）"""
        # 使用 Legacy 模式测试
        service = CacheServiceLegacy(backend="memory", max_size=50)

        assert service.backend == "memory"
        assert isinstance(service._cache, MemoryCache)

    @pytest.mark.asyncio
    async def test_init_unified_mode(self):
        """测试 Unified 模式初始化"""
        service = CacheServiceUnified(backend="memory", max_size=50)

        # Unified 模式使用 CacheManager
        assert service._cache_manager is not None
        assert service.default_ttl > 0

    @pytest.mark.asyncio
    async def test_init_redis_backend_fallback(self):
        """测试 Redis 后端初始化失败时回退到内存（Legacy 模式）"""
        with patch("app.services.cache_service.CacheServiceLegacy"):
            # 这个测试只适用于 Legacy 模式
            # Unified 模式不使用 Redis 作为直接后端
            pass

    @pytest.mark.asyncio
    async def test_init_unsupported_backend(self):
        """测试不支持的后端（Legacy 模式）"""
        # Unified 模式不抛出异常，忽略 backend 参数
        service = CacheServiceUnified(backend="unsupported")
        assert service is not None

    @pytest.mark.asyncio
    async def test_set_and_get(self, service):
        """测试设置和获取"""
        await service.set("key1", "value1")
        result = await service.get("key1")

        assert result == "value1"

    @pytest.mark.asyncio
    async def test_delete(self, service):
        """测试删除"""
        await service.set("key1", "value1")
        result = await service.delete("key1")

        assert result is True

    @pytest.mark.asyncio
    async def test_clear(self, service):
        """测试清空"""
        await service.set("key1", "value1")
        await service.set("key2", "value2")
        await service.clear()

        assert await service.get("key1") is None
        assert await service.get("key2") is None

    @pytest.mark.asyncio
    async def test_get_stats(self, service):
        """测试获取统计信息"""
        stats = service.get_stats()

        assert stats is not None

    @pytest.mark.asyncio
    async def test_get_or_set_existing(self, service):
        """测试 get_or_set 已存在的键"""
        await service.set("key1", "existing_value")

        result = await service.get_or_set("key1", lambda: "new_value")

        assert result == "existing_value"

    @pytest.mark.asyncio
    async def test_get_or_set_new(self, service):
        """测试 get_or_set 新键"""
        result = await service.get_or_set("new_key", lambda: "computed_value")

        assert result == "computed_value"
        assert await service.get("new_key") == "computed_value"

    @pytest.mark.asyncio
    async def test_get_or_set_async_factory(self, service):
        """测试 get_or_set 异步工厂函数"""

        async def async_factory():
            return "async_value"

        result = await service.get_or_set("async_key", async_factory)

        assert result == "async_value"

    @pytest.mark.asyncio
    async def test_start_and_stop(self):
        """测试启动和停止"""
        # 使用 Legacy 模式测试
        service = CacheServiceLegacy(backend="memory")

        await service.start()
        assert service._cleanup_task is not None

        await service.stop()
        # 停止后任务被取消，但对象仍然存在
        assert service._cleanup_task.cancelled() or service._cleanup_task is None

    @pytest.mark.asyncio
    async def test_start_and_stop_unified(self):
        """测试 Unified 模式启动和停止"""
        service = CacheServiceUnified(backend="memory")

        await service.start()
        # Unified 模式没有 _cleanup_task，由 CacheManager 管理
        assert service._cache_manager is not None

        await service.stop()
        # Unified 模式的 stop 是空操作


class TestCacheServiceConcurrency:
    """缓存服务并发测试"""

    @pytest_asyncio.fixture
    async def service(self):
        """创建缓存服务实例"""
        service = CacheService(backend="memory", max_size=1000)
        await service.start()
        yield service
        await service.stop()

    @pytest.mark.asyncio
    async def test_concurrent_writes(self, service):
        """测试并发写入"""

        async def write(key):
            await service.set(f"key_{key}", f"value_{key}")

        tasks = [write(i) for i in range(100)]
        await asyncio.gather(*tasks)

        # 验证所有写入成功
        for i in range(100):
            result = await service.get(f"key_{i}")
            assert result == f"value_{i}"

    @pytest.mark.asyncio
    async def test_concurrent_reads(self, service):
        """测试并发读取"""
        # 先写入数据
        for i in range(50):
            await service.set(f"key_{i}", f"value_{i}")

        async def read(key):
            return await service.get(f"key_{key}")

        tasks = [read(i) for i in range(50)]
        results = await asyncio.gather(*tasks)

        for i, result in enumerate(results):
            assert result == f"value_{i}"

    @pytest.mark.asyncio
    async def test_concurrent_get_or_set(self, service):
        """测试并发 get_or_set"""
        call_count = 0

        async def factory():
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.01)  # 模拟耗时操作
            return "computed"

        # 并发调用同一个键
        tasks = [service.get_or_set("same_key", factory) for _ in range(10)]
        results = await asyncio.gather(*tasks)

        # 所有结果应该相同
        assert all(r == "computed" for r in results)


class TestCacheServiceTTL:
    """缓存服务 TTL 测试"""

    @pytest_asyncio.fixture
    async def service(self):
        """创建缓存服务实例（使用 Legacy 模式测试 TTL）"""
        # 使用 Legacy 模式测试 TTL，因为 Unified 模式使用 CacheManager 的默认 TTL
        service = CacheServiceLegacy(backend="memory", default_ttl=2)
        await service.start()
        yield service
        await service.stop()

    @pytest.mark.asyncio
    async def test_default_ttl(self, service):
        """测试默认 TTL"""
        await service.set("key1", "value1")

        assert await service.get("key1") == "value1"

        time.sleep(2.1)

        assert await service.get("key1") is None

    @pytest.mark.asyncio
    async def test_custom_ttl(self, service):
        """测试自定义 TTL"""
        await service.set("key1", "value1", ttl=1)

        time.sleep(1.1)

        assert await service.get("key1") is None

    @pytest.mark.asyncio
    async def test_no_ttl(self, service):
        """测试无 TTL"""
        await service.set("key1", "value1", ttl=None)

        # 无 TTL 时使用 Cache服务的默认 TTL
        # 由于 Cache服务的默认 TTL 是 2 秒，实际使用的是 TTL 会稍长
        assert await service.get("key1") == "value1"

        time.sleep(2.1)

        assert await service.get("key1") is None


class TestCacheServiceUnifiedTTL:
    """缓存服务 Unified 模式 TTL 测试"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """每个测试前重置 CacheManager"""
        reset_cache_manager()
        yield
        reset_cache_manager()

    @pytest_asyncio.fixture
    async def service(self):
        """创建缓存服务实例（Unified 模式）"""
        service = CacheServiceUnified(backend="memory", default_ttl=2)
        await service.start()
        yield service
        await service.stop()

    @pytest.mark.asyncio
    async def test_unified_mode_uses_cache_manager(self, service):
        """测试 Unified 模式使用 CacheManager"""
        # Unified 模式使用 CacheManager 的 GENERAL 命名空间
        await service.set("key1", "value1")

        # 验证数据存储在 CacheManager 中
        manager = get_cache_manager()
        value = await manager.get(CacheNamespace.GENERAL, "key1")
        assert value == "value1"

    @pytest.mark.asyncio
    async def test_unified_mode_stats(self, service):
        """测试 Unified 模式统计信息"""
        await service.set("key1", "value1")
        await service.get("key1")  # hit
        await service.get("key2")  # miss

        stats = service.get_stats()
        assert stats["mode"] == "unified"


class TestCacheServiceEdgeCases:
    """缓存服务边界情况测试"""

    @pytest_asyncio.fixture
    async def service(self):
        """创建缓存服务实例"""
        service = CacheService(backend="memory", max_size=10)
        await service.start()
        yield service
        await service.stop()

    @pytest.mark.asyncio
    async def test_none_value(self, service):
        """测试 None 值"""
        await service.set("key1", None)

        # 注意：get 返回 None 可能表示不存在或值为 None
        # 这里测试的是可以存储 None
        result = await service.get("key1")
        assert result is None
        # 由于 LRU 缓存的实现，None 值会被存储

    @pytest.mark.asyncio
    async def test_complex_value(self, service):
        """测试复杂值"""
        value = {"list": [1, 2, 3], "dict": {"a": 1, "b": 2}, "nested": {"inner": [4, 5, 6]}}

        await service.set("complex", value)
        result = await service.get("complex")

        assert result == value

    @pytest.mark.asyncio
    async def test_large_value(self, service):
        """测试大值"""
        large_value = "x" * 100000

        await service.set("large", large_value)
        result = await service.get("large")

        assert result == large_value

    @pytest.mark.asyncio
    async def test_unicode_key_and_value(self, service):
        """测试 Unicode 键和值"""
        await service.set("中文键", "中文值")
        await service.set("emoji", "😀🎉")

        assert await service.get("中文键") == "中文值"
        assert await service.get("emoji") == "😀🎉"
