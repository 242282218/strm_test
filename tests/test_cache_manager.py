"""
缓存管理器单元测试

测试统一缓存管理器的核心功能：
- 单例模式
- 命名空间隔离
- TTL 配置
- 缓存命中/未命中
- 统计信息
"""

import asyncio
import time

import pytest
import pytest_asyncio

from app.core.cache_manager import CacheConfig, CacheManager, CacheNamespace, get_cache_manager


class TestCacheManagerSingleton:
    """单例模式测试"""

    def test_singleton_pattern(self):
        """测试单例模式 - 同一实例"""
        manager1 = CacheManager.get_instance()
        manager2 = CacheManager.get_instance()

        assert manager1 is manager2

    def test_get_cache_manager_function(self):
        """测试便捷函数"""
        manager = get_cache_manager()

        assert manager is CacheManager.get_instance()

    def test_singleton_reset(self):
        """测试单例重置"""
        manager1 = CacheManager.get_instance()
        CacheManager.reset_instance()
        manager2 = CacheManager.get_instance()

        # 重置后应该是新实例
        assert manager1 is not manager2


class TestCacheNamespace:
    """命名空间测试"""

    @pytest_asyncio.fixture
    async def manager(self):
        """创建缓存管理器实例"""
        manager = CacheManager.get_instance()
        await manager.start()
        yield manager
        await manager.stop()
        CacheManager.reset_instance()

    @pytest.mark.asyncio
    async def test_namespace_isolation(self, manager):
        """测试命名空间隔离 - 相同键不同命名空间"""
        await manager.set(CacheNamespace.LINK, "key1", "value1")
        await manager.set(CacheNamespace.FILE_SIZE, "key1", "value2")

        assert await manager.get(CacheNamespace.LINK, "key1") == "value1"
        assert await manager.get(CacheNamespace.FILE_SIZE, "key1") == "value2"

    @pytest.mark.asyncio
    async def test_namespace_delete_isolation(self, manager):
        """测试命名空间删除隔离"""
        await manager.set(CacheNamespace.LINK, "key1", "value1")
        await manager.set(CacheNamespace.FILE_SIZE, "key1", "value2")

        # 删除 LINK 命名空间的键
        await manager.delete(CacheNamespace.LINK, "key1")

        # LINK 命名空间应该删除
        assert await manager.get(CacheNamespace.LINK, "key1") is None
        # FILE_SIZE 命名空间应该保留
        assert await manager.get(CacheNamespace.FILE_SIZE, "key1") == "value2"

    @pytest.mark.asyncio
    async def test_namespace_clear_isolation(self, manager):
        """测试命名空间清空隔离"""
        await manager.set(CacheNamespace.LINK, "key1", "value1")
        await manager.set(CacheNamespace.LINK, "key2", "value2")
        await manager.set(CacheNamespace.FILE_SIZE, "key3", "value3")

        # 清空 LINK 命名空间
        await manager.clear_namespace(CacheNamespace.LINK)

        # LINK 命名空间应该清空
        assert await manager.get(CacheNamespace.LINK, "key1") is None
        assert await manager.get(CacheNamespace.LINK, "key2") is None
        # FILE_SIZE 命名空间应该保留
        assert await manager.get(CacheNamespace.FILE_SIZE, "key3") == "value3"


class TestCacheManagerTTL:
    """TTL 配置测试"""

    @pytest_asyncio.fixture
    async def manager(self):
        """创建缓存管理器实例"""
        config = CacheConfig(
            default_ttls={
                CacheNamespace.LINK: 2,  # 2秒
                CacheNamespace.FILE_SIZE: 1,  # 1秒
            }
        )
        manager = CacheManager(config=config)
        await manager.start()
        yield manager
        await manager.stop()
        CacheManager.reset_instance()

    @pytest.mark.asyncio
    async def test_namespace_default_ttl(self, manager):
        """测试命名空间默认 TTL"""
        # 使用默认 TTL
        await manager.set(CacheNamespace.LINK, "key1", "value1")

        assert await manager.get(CacheNamespace.LINK, "key1") == "value1"

        # 等待 TTL 过期
        time.sleep(2.1)

        assert await manager.get(CacheNamespace.LINK, "key1") is None

    @pytest.mark.asyncio
    async def test_custom_ttl_override(self, manager):
        """测试自定义 TTL 覆盖默认值"""
        # 自定义 TTL
        await manager.set(CacheNamespace.LINK, "key1", "value1", ttl=1)

        time.sleep(1.1)

        assert await manager.get(CacheNamespace.LINK, "key1") is None

    @pytest.mark.asyncio
    async def test_no_ttl(self, manager):
        """测试无 TTL（永不过期）"""
        await manager.set(CacheNamespace.LINK, "key1", "value1", ttl=None)

        time.sleep(2.1)

        # 无 TTL 应该不过期
        assert await manager.get(CacheNamespace.LINK, "key1") == "value1"


class TestCacheManagerHitMiss:
    """缓存命中/未命中测试"""

    @pytest_asyncio.fixture
    async def manager(self):
        """创建缓存管理器实例"""
        manager = CacheManager.get_instance()
        await manager.start()
        yield manager
        await manager.stop()
        CacheManager.reset_instance()

    @pytest.mark.asyncio
    async def test_cache_hit(self, manager):
        """测试缓存命中"""
        await manager.set(CacheNamespace.LINK, "key1", "value1")

        result = await manager.get(CacheNamespace.LINK, "key1")

        assert result == "value1"

        # 检查统计
        stats = manager.get_stats()
        assert stats["total_hits"] >= 1

    @pytest.mark.asyncio
    async def test_cache_miss(self, manager):
        """测试缓存未命中"""
        result = await manager.get(CacheNamespace.LINK, "non_existent")

        assert result is None

        # 检查统计
        stats = manager.get_stats()
        assert stats["total_misses"] >= 1

    @pytest.mark.asyncio
    async def test_get_or_set_existing(self, manager):
        """测试 get_or_set 已存在的键"""
        await manager.set(CacheNamespace.LINK, "key1", "existing_value")

        result = await manager.get_or_set(CacheNamespace.LINK, "key1", lambda: "new_value")

        assert result == "existing_value"

    @pytest.mark.asyncio
    async def test_get_or_set_new(self, manager):
        """测试 get_or_set 新键"""
        result = await manager.get_or_set(CacheNamespace.LINK, "new_key", lambda: "computed_value")

        assert result == "computed_value"
        assert await manager.get(CacheNamespace.LINK, "new_key") == "computed_value"

    @pytest.mark.asyncio
    async def test_get_or_set_async_factory(self, manager):
        """测试 get_or_set 异步工厂函数"""

        async def async_factory():
            return "async_value"

        result = await manager.get_or_set(CacheNamespace.LINK, "async_key", async_factory)

        assert result == "async_value"


class TestCacheManagerStats:
    """统计信息测试"""

    @pytest_asyncio.fixture
    async def manager(self):
        """创建缓存管理器实例"""
        manager = CacheManager.get_instance()
        await manager.start()
        yield manager
        await manager.stop()
        CacheManager.reset_instance()

    @pytest.mark.asyncio
    async def test_get_stats(self, manager):
        """测试获取统计信息"""
        await manager.set(CacheNamespace.LINK, "key1", "value1")
        await manager.get(CacheNamespace.LINK, "key1")
        await manager.get(CacheNamespace.LINK, "non_existent")

        stats = manager.get_stats()

        assert "total_hits" in stats
        assert "total_misses" in stats
        assert "total_sets" in stats
        assert "namespaces" in stats
        assert stats["total_hits"] >= 1
        assert stats["total_misses"] >= 1
        assert stats["total_sets"] >= 1

    @pytest.mark.asyncio
    async def test_namespace_stats(self, manager):
        """测试命名空间统计"""
        await manager.set(CacheNamespace.LINK, "key1", "value1")
        await manager.set(CacheNamespace.FILE_SIZE, "key2", "value2")

        stats = manager.get_namespace_stats(CacheNamespace.LINK)

        assert stats is not None
        assert "size" in stats

    @pytest.mark.asyncio
    async def test_hit_rate_calculation(self, manager):
        """测试命中率计算"""
        # 3 次命中
        await manager.set(CacheNamespace.LINK, "key1", "value1")
        await manager.get(CacheNamespace.LINK, "key1")
        await manager.get(CacheNamespace.LINK, "key1")
        await manager.get(CacheNamespace.LINK, "key1")

        # 1 次未命中
        await manager.get(CacheNamespace.LINK, "non_existent")

        stats = manager.get_stats()

        # 命中率应该是 75% (3/4)
        assert stats["hit_rate"] == "75.00%"


class TestCacheManagerOperations:
    """基本操作测试"""

    @pytest_asyncio.fixture
    async def manager(self):
        """创建缓存管理器实例"""
        manager = CacheManager.get_instance()
        await manager.start()
        yield manager
        await manager.stop()
        CacheManager.reset_instance()

    @pytest.mark.asyncio
    async def test_set_and_get(self, manager):
        """测试设置和获取"""
        await manager.set(CacheNamespace.LINK, "key1", "value1")
        result = await manager.get(CacheNamespace.LINK, "key1")

        assert result == "value1"

    @pytest.mark.asyncio
    async def test_delete(self, manager):
        """测试删除"""
        await manager.set(CacheNamespace.LINK, "key1", "value1")
        result = await manager.delete(CacheNamespace.LINK, "key1")

        assert result is True
        assert await manager.get(CacheNamespace.LINK, "key1") is None

    @pytest.mark.asyncio
    async def test_delete_non_existent(self, manager):
        """测试删除不存在的键"""
        result = await manager.delete(CacheNamespace.LINK, "non_existent")

        assert result is False

    @pytest.mark.asyncio
    async def test_clear_all(self, manager):
        """测试清空所有缓存"""
        await manager.set(CacheNamespace.LINK, "key1", "value1")
        await manager.set(CacheNamespace.FILE_SIZE, "key2", "value2")

        await manager.clear_all()

        assert await manager.get(CacheNamespace.LINK, "key1") is None
        assert await manager.get(CacheNamespace.FILE_SIZE, "key2") is None

    @pytest.mark.asyncio
    async def test_complex_value(self, manager):
        """测试复杂值"""
        value = {"list": [1, 2, 3], "dict": {"a": 1, "b": 2}, "nested": {"inner": [4, 5, 6]}}

        await manager.set(CacheNamespace.LINK, "complex", value)
        result = await manager.get(CacheNamespace.LINK, "complex")

        assert result == value

    @pytest.mark.asyncio
    async def test_unicode_key_and_value(self, manager):
        """测试 Unicode 键和值"""
        await manager.set(CacheNamespace.LINK, "中文键", "中文值")
        await manager.set(CacheNamespace.LINK, "emoji", "😀🎉")

        assert await manager.get(CacheNamespace.LINK, "中文键") == "中文值"
        assert await manager.get(CacheNamespace.LINK, "emoji") == "😀🎉"


class TestCacheManagerConcurrency:
    """并发测试"""

    @pytest_asyncio.fixture
    async def manager(self):
        """创建缓存管理器实例"""
        manager = CacheManager.get_instance()
        await manager.start()
        yield manager
        await manager.stop()
        CacheManager.reset_instance()

    @pytest.mark.asyncio
    async def test_concurrent_writes(self, manager):
        """测试并发写入"""

        async def write(key):
            await manager.set(CacheNamespace.LINK, f"key_{key}", f"value_{key}")

        tasks = [write(i) for i in range(100)]
        await asyncio.gather(*tasks)

        # 验证所有写入成功
        for i in range(100):
            result = await manager.get(CacheNamespace.LINK, f"key_{i}")
            assert result == f"value_{i}"

    @pytest.mark.asyncio
    async def test_concurrent_reads(self, manager):
        """测试并发读取"""
        # 先写入数据
        for i in range(50):
            await manager.set(CacheNamespace.LINK, f"key_{i}", f"value_{i}")

        async def read(key):
            return await manager.get(CacheNamespace.LINK, f"key_{key}")

        tasks = [read(i) for i in range(50)]
        results = await asyncio.gather(*tasks)

        for i, result in enumerate(results):
            assert result == f"value_{i}"

    @pytest.mark.asyncio
    async def test_concurrent_namespace_operations(self, manager):
        """测试并发命名空间操作"""

        async def write_link(key):
            await manager.set(CacheNamespace.LINK, f"key_{key}", f"link_{key}")

        async def write_file_size(key):
            await manager.set(CacheNamespace.FILE_SIZE, f"key_{key}", f"size_{key}")

        tasks = [write_link(i) for i in range(50)] + [write_file_size(i) for i in range(50)]
        await asyncio.gather(*tasks)

        # 验证命名空间隔离
        for i in range(50):
            assert await manager.get(CacheNamespace.LINK, f"key_{i}") == f"link_{i}"
            assert await manager.get(CacheNamespace.FILE_SIZE, f"key_{i}") == f"size_{i}"


class TestCacheManagerLifecycle:
    """生命周期测试"""

    @pytest.mark.asyncio
    async def test_start_and_stop(self):
        """测试启动和停止"""
        manager = CacheManager()

        await manager.start()
        assert manager._running is True

        await manager.stop()
        assert manager._running is False

        CacheManager.reset_instance()

    @pytest.mark.asyncio
    async def test_double_start(self):
        """测试重复启动"""
        manager = CacheManager()

        await manager.start()
        await manager.start()  # 应该是幂等的

        assert manager._running is True

        await manager.stop()
        CacheManager.reset_instance()

    @pytest.mark.asyncio
    async def test_double_stop(self):
        """测试重复停止"""
        manager = CacheManager()

        await manager.start()
        await manager.stop()
        await manager.stop()  # 应该是幂等的

        assert manager._running is False

        CacheManager.reset_instance()
