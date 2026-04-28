"""
LRU 缓存模块单元测试

测试缓存操作、TTL 过期、统计功能
"""

import threading
import time

from app.core.lru_cache import (
    LRUCache,
    MultiLevelLRUCache,
    cached,
    clear_default_cache,
    get_default_cache,
)


class TestLRUCache:
    """LRU 缓存测试"""

    def test_init(self):
        """测试初始化"""
        cache = LRUCache(maxsize=100, ttl=60)

        assert cache.maxsize == 100
        assert cache.ttl == 60
        assert cache.enable_stats is True
        assert len(cache) == 0

    def test_init_with_defaults(self):
        """测试使用默认值初始化"""
        cache = LRUCache()

        assert cache.maxsize == 1000
        assert cache.ttl is None
        assert cache.enable_stats is True

    def test_set_and_get(self):
        """测试设置和获取"""
        cache = LRUCache()

        cache.set("key1", "value1")
        result = cache.get("key1")

        assert result == "value1"

    def test_get_non_existent(self):
        """测试获取不存在的键"""
        cache = LRUCache()

        result = cache.get("non_existent")

        assert result is None

    def test_delete(self):
        """测试删除"""
        cache = LRUCache()

        cache.set("key1", "value1")
        result = cache.delete("key1")

        assert result is True
        assert cache.get("key1") is None

    def test_delete_non_existent(self):
        """测试删除不存在的键"""
        cache = LRUCache()

        result = cache.delete("non_existent")

        assert result is False

    def test_clear(self):
        """测试清空缓存"""
        cache = LRUCache()

        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.clear()

        assert len(cache) == 0

    def test_lru_eviction(self):
        """测试 LRU 淘汰机制"""
        cache = LRUCache(maxsize=3)

        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")
        cache.set("key4", "value4")  # 应该淘汰 key1

        assert cache.get("key1") is None
        assert cache.get("key2") == "value2"
        assert cache.get("key3") == "value3"
        assert cache.get("key4") == "value4"

    def test_lru_access_order(self):
        """测试 LRU 访问顺序"""
        cache = LRUCache(maxsize=3)

        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")

        # 访问 key1，使其变为最近使用
        cache.get("key1")

        # 添加新项，应该淘汰 key2
        cache.set("key4", "value4")

        assert cache.get("key1") == "value1"
        assert cache.get("key2") is None
        assert cache.get("key3") == "value3"
        assert cache.get("key4") == "value4"

    def test_ttl_expiration(self):
        """测试 TTL 过期"""
        cache = LRUCache(ttl=1)  # 1 秒 TTL

        cache.set("key1", "value1")

        # 立即获取应该成功
        assert cache.get("key1") == "value1"

        # 等待过期
        time.sleep(1.1)

        # 过期后应该返回 None
        assert cache.get("key1") is None

    def test_ttl_per_entry(self):
        """测试单条目 TTL"""
        cache = LRUCache(ttl=10)  # 默认 10 秒

        # 设置单条目 TTL 为 1 秒
        cache.set("key1", "value1", ttl=1)
        cache.set("key2", "value2")  # 使用默认 TTL

        time.sleep(1.1)

        assert cache.get("key1") is None  # 已过期
        assert cache.get("key2") == "value2"  # 未过期

    def test_cleanup_expired(self):
        """测试清理过期条目"""
        cache = LRUCache(ttl=1)

        cache.set("key1", "value1")
        cache.set("key2", "value2")

        time.sleep(1.1)

        count = cache.cleanup_expired()

        assert count == 2
        assert len(cache) == 0

    def test_contains(self):
        """测试包含检查"""
        cache = LRUCache()

        cache.set("key1", "value1")

        assert "key1" in cache
        assert "non_existent" not in cache

    def test_contains_expired(self):
        """测试包含检查过期条目"""
        cache = LRUCache(ttl=1)

        cache.set("key1", "value1")

        assert "key1" in cache

        time.sleep(1.1)

        assert "key1" not in cache

    def test_len(self):
        """测试长度"""
        cache = LRUCache()

        assert len(cache) == 0

        cache.set("key1", "value1")
        cache.set("key2", "value2")

        assert len(cache) == 2

    def test_thread_safety(self):
        """测试线程安全"""
        cache = LRUCache(maxsize=1000)
        errors = []

        def writer(start, count):
            try:
                for i in range(start, start + count):
                    cache.set(f"key_{i}", f"value_{i}")
            except Exception as e:
                errors.append(e)

        def reader(start, count):
            try:
                for i in range(start, start + count):
                    cache.get(f"key_{i}")
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=writer, args=(0, 100)),
            threading.Thread(target=writer, args=(100, 100)),
            threading.Thread(target=reader, args=(0, 100)),
            threading.Thread(target=reader, args=(100, 100)),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0


class TestLRUCacheStats:
    """LRU 缓存统计测试"""

    def test_stats_disabled(self):
        """测试禁用统计"""
        cache = LRUCache(enable_stats=False)

        stats = cache.get_stats()

        assert stats == {}

    def test_stats_hits(self):
        """测试命中统计"""
        cache = LRUCache()

        cache.set("key1", "value1")
        cache.get("key1")
        cache.get("key1")

        stats = cache.get_stats()

        assert stats["hits"] == 2

    def test_stats_misses(self):
        """测试未命中统计"""
        cache = LRUCache()

        cache.get("non_existent1")
        cache.get("non_existent2")

        stats = cache.get_stats()

        assert stats["misses"] == 2

    def test_stats_sets(self):
        """测试设置统计"""
        cache = LRUCache()

        cache.set("key1", "value1")
        cache.set("key2", "value2")

        stats = cache.get_stats()

        assert stats["sets"] == 2

    def test_stats_deletes(self):
        """测试删除统计"""
        cache = LRUCache()

        cache.set("key1", "value1")
        cache.delete("key1")

        stats = cache.get_stats()

        assert stats["deletes"] == 1

    def test_stats_evictions(self):
        """测试淘汰统计"""
        cache = LRUCache(maxsize=2)

        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")  # 淘汰 key1

        stats = cache.get_stats()

        assert stats["evictions"] == 1

    def test_stats_expirations(self):
        """测试过期统计"""
        cache = LRUCache(ttl=1)

        cache.set("key1", "value1")
        time.sleep(1.1)
        cache.get("key1")  # 触发过期

        stats = cache.get_stats()

        assert stats["expirations"] == 1

    def test_stats_hit_rate(self):
        """测试命中率计算"""
        cache = LRUCache()

        cache.set("key1", "value1")
        cache.get("key1")  # hit
        cache.get("non_existent")  # miss

        stats = cache.get_stats()

        assert stats["hit_rate"] == "50.00%"


class TestCachedFunction:
    """函数缓存装饰器测试"""

    def test_cached_function(self):
        """测试缓存函数结果"""
        cache = LRUCache()
        call_count = 0

        @cached(cache)
        def expensive_function(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        # 第一次调用
        result1 = expensive_function(5)
        assert result1 == 10
        assert call_count == 1

        # 第二次调用应该使用缓存
        result2 = expensive_function(5)
        assert result2 == 10
        assert call_count == 1  # 没有增加

        # 不同参数应该重新计算
        result3 = expensive_function(10)
        assert result3 == 20
        assert call_count == 2

    def test_cached_function_with_key_func(self):
        """测试使用自定义键函数"""
        cache = LRUCache()

        def key_func(a, b):
            return f"{a}_{b}"

        @cached(cache, key_func=key_func)
        def add(a, b):
            return a + b

        result1 = add(1, 2)
        result2 = add(1, 2)

        assert result1 == 3
        assert result2 == 3

    def test_cached_function_metadata(self):
        """测试函数元数据保留"""
        cache = LRUCache()

        @cached(cache)
        def documented_function():
            """This is a documented function."""
            return 42

        assert documented_function.__name__ == "documented_function"
        assert documented_function.__doc__ == "This is a documented function."


class TestMultiLevelLRUCache:
    """多级 LRU 缓存测试"""

    def test_init(self):
        """测试初始化"""
        cache = MultiLevelLRUCache(l1_maxsize=100, l2_maxsize=1000, l1_ttl=60, l2_ttl=3600)

        assert cache.l1_cache.maxsize == 100
        assert cache.l2_cache.maxsize == 1000

    def test_set_and_get(self):
        """测试设置和获取"""
        cache = MultiLevelLRUCache()

        cache.set("key1", "value1")
        result = cache.get("key1")

        assert result == "value1"

    def test_l1_hit(self):
        """测试 L1 缓存命中"""
        cache = MultiLevelLRUCache()

        cache.set("key1", "value1")

        # 第一次获取会同时设置 L1 和 L2
        cache.get("key1")

        stats = cache.get_stats()
        assert stats["l1_hits"] == 1

    def test_l2_hit_promotes_to_l1(self):
        """测试 L2 命中后提升到 L1"""
        cache = MultiLevelLRUCache()

        cache.set("key1", "value1")

        # 清空 L1
        cache.l1_cache.clear()

        # 从 L2 获取
        result = cache.get("key1")

        assert result == "value1"
        assert cache.l1_cache.get("key1") == "value1"  # 已提升到 L1

    def test_get_stats(self):
        """测试获取统计信息"""
        cache = MultiLevelLRUCache()

        cache.set("key1", "value1")
        cache.get("key1")
        cache.get("non_existent")

        stats = cache.get_stats()

        assert "l1_hits" in stats
        assert "l2_hits" in stats
        assert "misses" in stats
        assert "hit_rate" in stats


class TestDefaultCache:
    """默认缓存测试"""

    def test_get_default_cache(self):
        """测试获取默认缓存"""
        clear_default_cache()

        cache = get_default_cache()

        assert cache is not None
        assert isinstance(cache, LRUCache)

    def test_get_default_cache_singleton(self):
        """测试默认缓存是单例"""
        clear_default_cache()

        cache1 = get_default_cache()
        cache2 = get_default_cache()

        assert cache1 is cache2

    def test_clear_default_cache(self):
        """测试清空默认缓存"""
        cache = get_default_cache()
        cache.set("key1", "value1")

        clear_default_cache()

        # 获取新的默认缓存
        cache = get_default_cache()
        assert cache.get("key1") is None


class TestLRUCacheEdgeCases:
    """LRU 缓存边界情况测试"""

    def test_maxsize_one(self):
        """测试最大容量为 1"""
        cache = LRUCache(maxsize=1)

        cache.set("key1", "value1")
        cache.set("key2", "value2")

        assert cache.get("key1") is None
        assert cache.get("key2") == "value2"

    def test_update_existing_key(self):
        """测试更新已存在的键"""
        cache = LRUCache()

        cache.set("key1", "value1")
        cache.set("key1", "value2")

        assert cache.get("key1") == "value2"
        assert len(cache) == 1

    def test_none_value(self):
        """测试 None 值"""
        cache = LRUCache()

        cache.set("key1", None)

        # 注意：get 返回 None 可能表示不存在或值为 None
        # 这里测试的是可以存储 None
        assert "key1" in cache

    def test_complex_value(self):
        """测试复杂值"""
        cache = LRUCache()

        value = {"list": [1, 2, 3], "dict": {"a": 1, "b": 2}, "tuple": (4, 5, 6)}

        cache.set("complex", value)
        result = cache.get("complex")

        assert result == value

    def test_large_key(self):
        """测试大键"""
        cache = LRUCache()

        large_key = "k" * 10000
        cache.set(large_key, "value")

        assert cache.get(large_key) == "value"

    def test_unicode_key_and_value(self):
        """测试 Unicode 键和值"""
        cache = LRUCache()

        cache.set("中文键", "中文值")
        cache.set("emoji", "😀🎉")

        assert cache.get("中文键") == "中文值"
        assert cache.get("emoji") == "😀🎉"
