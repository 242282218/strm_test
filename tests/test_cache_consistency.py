"""
缓存一致性测试套件

测试 CacheManager 的核心功能：
- 命名空间隔离
- TTL 配置
- 版本控制
- 跨命名空间失效
- Legacy 模式兼容
"""

import asyncio

import pytest

from app.core.cache_manager import (
    CacheConfig,
    CacheNamespace,
    get_cache_manager,
    reset_instance,
)


class TestCacheManagerBasics:
    """CacheManager 基础功能测试"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """每个测试前重置 CacheManager"""
        reset_instance()
        self.config = CacheConfig(
            enable_versioning=True,
            enable_cross_namespace_invalidation=True,
        )
        self.cache_manager = get_cache_manager(self.config)
        yield
        # 清理
        asyncio.run(self.cache_manager.clear_all())

    @pytest.mark.asyncio
    async def test_basic_set_and_get(self):
        """测试基本的设置和获取"""
        # Set
        await self.cache_manager.set(CacheNamespace.GENERAL, "test_key", "test_value")

        # Get
        value = await self.cache_manager.get(CacheNamespace.GENERAL, "test_key")
        assert value == "test_value"

    @pytest.mark.asyncio
    async def test_cache_miss(self):
        """测试缓存未命中"""
        value = await self.cache_manager.get(CacheNamespace.GENERAL, "nonexistent_key")
        assert value is None

    @pytest.mark.asyncio
    async def test_delete(self):
        """测试删除缓存"""
        await self.cache_manager.set(CacheNamespace.GENERAL, "key1", "value1")

        # Delete
        result = await self.cache_manager.delete(CacheNamespace.GENERAL, "key1")
        assert result is True

        # Verify deleted
        value = await self.cache_manager.get(CacheNamespace.GENERAL, "key1")
        assert value is None

    @pytest.mark.asyncio
    async def test_clear_namespace(self):
        """测试清空命名空间"""
        await self.cache_manager.set(CacheNamespace.GENERAL, "key1", "value1")
        await self.cache_manager.set(CacheNamespace.GENERAL, "key2", "value2")

        await self.cache_manager.clear_namespace(CacheNamespace.GENERAL)

        assert await self.cache_manager.get(CacheNamespace.GENERAL, "key1") is None
        assert await self.cache_manager.get(CacheNamespace.GENERAL, "key2") is None


class TestNamespaceIsolation:
    """命名空间隔离测试"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """每个测试前重置 CacheManager"""
        reset_instance()
        self.cache_manager = get_cache_manager()
        yield
        asyncio.run(self.cache_manager.clear_all())

    @pytest.mark.asyncio
    async def test_namespace_isolation(self):
        """测试不同命名空间的键是隔离的"""
        # 在不同命名空间设置相同的键
        await self.cache_manager.set(CacheNamespace.GENERAL, "shared_key", "general_value")
        await self.cache_manager.set(CacheNamespace.LINK, "shared_key", "link_value")
        await self.cache_manager.set(CacheNamespace.TMDB, "shared_key", "tmdb_value")

        # 验证各命名空间的值是独立的
        assert await self.cache_manager.get(CacheNamespace.GENERAL, "shared_key") == "general_value"
        assert await self.cache_manager.get(CacheNamespace.LINK, "shared_key") == "link_value"
        assert await self.cache_manager.get(CacheNamespace.TMDB, "shared_key") == "tmdb_value"

    @pytest.mark.asyncio
    async def test_clear_one_namespace_does_not_affect_others(self):
        """测试清空一个命名空间不影响其他命名空间"""
        await self.cache_manager.set(CacheNamespace.GENERAL, "key1", "value1")
        await self.cache_manager.set(CacheNamespace.LINK, "key1", "value2")

        # 清空 GENERAL
        await self.cache_manager.clear_namespace(CacheNamespace.GENERAL)

        # GENERAL 应该被清空
        assert await self.cache_manager.get(CacheNamespace.GENERAL, "key1") is None
        # LINK 应该保留
        assert await self.cache_manager.get(CacheNamespace.LINK, "key1") == "value2"


class TestTTLConfiguration:
    """TTL 配置测试"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """每个测试前重置 CacheManager"""
        reset_instance()
        self.config = CacheConfig(
            default_ttls={
                CacheNamespace.GENERAL: 1,  # 1 秒
                CacheNamespace.LINK: 2,  # 2 秒
            }
        )
        self.cache_manager = get_cache_manager(self.config)
        yield
        asyncio.run(self.cache_manager.clear_all())

    @pytest.mark.asyncio
    async def test_default_ttl(self):
        """测试默认 TTL"""
        await self.cache_manager.set(CacheNamespace.GENERAL, "key1", "value1")

        # 立即获取应该成功
        assert await self.cache_manager.get(CacheNamespace.GENERAL, "key1") == "value1"

        # 等待 TTL 过期
        await asyncio.sleep(1.5)

        # 应该已过期
        assert await self.cache_manager.get(CacheNamespace.GENERAL, "key1") is None

    @pytest.mark.asyncio
    async def test_custom_ttl(self):
        """测试自定义 TTL"""
        await self.cache_manager.set(CacheNamespace.GENERAL, "key1", "value1", ttl=3)

        # 等待默认 TTL 时间
        await asyncio.sleep(1.5)

        # 自定义 TTL 更长，应该还存在
        assert await self.cache_manager.get(CacheNamespace.GENERAL, "key1") == "value1"

    @pytest.mark.asyncio
    async def test_never_expire(self):
        """测试永不过期"""
        await self.cache_manager.set(CacheNamespace.GENERAL, "key1", "value1", ttl=None)

        # 等待默认 TTL 时间
        await asyncio.sleep(1.5)

        # 应该还存在
        assert await self.cache_manager.get(CacheNamespace.GENERAL, "key1") == "value1"


class TestVersionControl:
    """版本控制测试"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """每个测试前重置 CacheManager"""
        reset_instance()
        self.config = CacheConfig(enable_versioning=True)
        self.cache_manager = get_cache_manager(self.config)
        yield
        asyncio.run(self.cache_manager.clear_all())

    @pytest.mark.asyncio
    async def test_version_increment_invalidates_cache(self):
        """测试版本递增使旧缓存失效"""
        # 设置缓存
        await self.cache_manager.set(CacheNamespace.GENERAL, "key1", "value1")
        assert await self.cache_manager.get(CacheNamespace.GENERAL, "key1") == "value1"

        # 递增版本
        await self.cache_manager.increment_namespace_version(CacheNamespace.GENERAL)

        # 旧缓存应该失效
        assert await self.cache_manager.get(CacheNamespace.GENERAL, "key1") is None

    @pytest.mark.asyncio
    async def test_get_version(self):
        """测试获取版本信息"""
        version = self.cache_manager.get_namespace_version(CacheNamespace.GENERAL)
        assert version.namespace == CacheNamespace.GENERAL
        assert version.version == 1

        # 递增版本
        await self.cache_manager.increment_namespace_version(CacheNamespace.GENERAL)

        version = self.cache_manager.get_namespace_version(CacheNamespace.GENERAL)
        assert version.version == 2

    @pytest.mark.asyncio
    async def test_all_versions(self):
        """测试获取所有版本"""
        versions = self.cache_manager.get_all_versions()
        assert CacheNamespace.GENERAL.value in versions
        assert CacheNamespace.LINK.value in versions


class TestCrossNamespaceInvalidation:
    """跨命名空间失效测试"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """每个测试前重置 CacheManager"""
        reset_instance()
        self.config = CacheConfig(
            enable_versioning=True,
            enable_cross_namespace_invalidation=True,
        )
        self.cache_manager = get_cache_manager(self.config)
        yield
        asyncio.run(self.cache_manager.clear_all())

    @pytest.mark.asyncio
    async def test_cascade_invalidation(self):
        """测试级联失效"""
        # 设置多个命名空间的缓存
        await self.cache_manager.set(CacheNamespace.QUARK_API, "key1", "quark_value")
        await self.cache_manager.set(CacheNamespace.LINK, "key1", "link_value")
        await self.cache_manager.set(CacheNamespace.PROXY, "key1", "proxy_value")

        # 验证都存在
        assert await self.cache_manager.get(CacheNamespace.QUARK_API, "key1") == "quark_value"
        assert await self.cache_manager.get(CacheNamespace.LINK, "key1") == "link_value"
        assert await self.cache_manager.get(CacheNamespace.PROXY, "key1") == "proxy_value"

        # 失效 QUARK_API（应该级联失效 LINK 和 PROXY）
        result = await self.cache_manager.invalidate_related(CacheNamespace.QUARK_API)

        # 验证级联失效
        assert "link" in result["cascaded_namespaces"]
        assert "proxy" in result["cascaded_namespaces"]

        # 所有相关缓存应该失效
        assert await self.cache_manager.get(CacheNamespace.QUARK_API, "key1") is None
        assert await self.cache_manager.get(CacheNamespace.LINK, "key1") is None
        assert await self.cache_manager.get(CacheNamespace.PROXY, "key1") is None

    @pytest.mark.asyncio
    async def test_invalidation_log(self):
        """测试失效日志"""
        await self.cache_manager.set(CacheNamespace.GENERAL, "key1", "value1")

        # 失效
        await self.cache_manager.invalidate_related(CacheNamespace.GENERAL, key="key1")

        # 获取日志
        log = self.cache_manager.get_invalidation_log()
        assert len(log) > 0
        assert log[-1]["namespace"] == CacheNamespace.GENERAL.value
        assert log[-1]["key"] == "key1"


class TestStatistics:
    """统计功能测试"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """每个测试前重置 CacheManager"""
        reset_instance()
        self.cache_manager = get_cache_manager()
        yield
        asyncio.run(self.cache_manager.clear_all())

    @pytest.mark.asyncio
    async def test_hit_miss_stats(self):
        """测试命中/未命中统计"""
        # Miss
        await self.cache_manager.get(CacheNamespace.GENERAL, "nonexistent")

        # Set
        await self.cache_manager.set(CacheNamespace.GENERAL, "key1", "value1")

        # Hit
        await self.cache_manager.get(CacheNamespace.GENERAL, "key1")

        stats = self.cache_manager.get_stats()
        assert stats["total_hits"] == 1
        assert stats["total_misses"] == 1
        assert stats["total_sets"] == 1

    @pytest.mark.asyncio
    async def test_namespace_stats(self):
        """测试命名空间统计"""
        await self.cache_manager.set(CacheNamespace.GENERAL, "key1", "value1")
        await self.cache_manager.set(CacheNamespace.LINK, "key2", "value2")

        general_stats = self.cache_manager.get_namespace_stats(CacheNamespace.GENERAL)
        link_stats = self.cache_manager.get_namespace_stats(CacheNamespace.LINK)

        assert general_stats is not None
        assert link_stats is not None


class TestLegacyAdapter:
    """Legacy 适配器测试"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """每个测试前重置 CacheManager"""
        reset_instance()
        self.cache_manager = get_cache_manager()
        yield
        asyncio.run(self.cache_manager.clear_all())

    @pytest.mark.asyncio
    async def test_legacy_adapter_basic(self):
        """测试 Legacy 适配器基本功能"""
        adapter = self.cache_manager.get_legacy_cache_adapter("link")

        # Set
        await adapter.set("test_key", "test_value")

        # Get
        value = await adapter.get("test_key")
        assert value == "test_value"

        # Delete
        await adapter.delete("test_key")
        assert await adapter.get("test_key") is None

    @pytest.mark.asyncio
    async def test_legacy_adapter_get_or_set(self):
        """测试 Legacy 适配器 get_or_set"""
        adapter = self.cache_manager.get_legacy_cache_adapter("general")

        call_count = 0

        async def factory():
            nonlocal call_count
            call_count += 1
            return "factory_value"

        # 第一次应该调用 factory
        value1 = await adapter.get_or_set("key1", factory)
        assert value1 == "factory_value"
        assert call_count == 1

        # 第二次应该从缓存获取
        value2 = await adapter.get_or_set("key1", factory)
        assert value2 == "factory_value"
        assert call_count == 1  # 没有再次调用


class TestDependencyGraph:
    """依赖关系图测试"""

    def test_dependency_graph(self):
        """测试获取依赖关系图"""
        reset_instance()
        cache_manager = get_cache_manager()

        graph = cache_manager.get_dependency_graph()

        # 验证预定义的依赖关系
        assert "quark_api" in graph
        assert "link" in graph["quark_api"]
        assert "proxy" in graph["quark_api"]


# 运行测试的入口
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
