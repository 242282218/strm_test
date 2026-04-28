"""
缓存预热机制

提供智能缓存预热功能，支持基于模式、依赖关系和访问预测的预热策略
"""

import asyncio
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from enum import Enum
from typing import Any

from app.core.logging import get_logger


logger = get_logger(__name__)


class WarmupStrategy(Enum):
    """预热策略枚举"""

    PATTERN_BASED = "pattern_based"  # 基于模式
    ACCESS_PATTERN = "access_pattern"  # 基于访问模式
    DEPENDENCY_BASED = "dependency_based"  # 基于依赖关系
    SCHEDULED = "scheduled"  # 定时预热


@dataclass
class WarmupPattern:
    """预热模式定义"""

    name: str
    pattern: str  # 支持通配符，如 "user:*", "movie:*"
    priority: int = 1  # 优先级，数字越小优先级越高
    ttl: int | None = None  # 特定TTL
    strategy: WarmupStrategy = WarmupStrategy.PATTERN_BASED


@dataclass
class AccessRecord:
    """访问记录"""

    key: str
    timestamp: float
    frequency: int = 1


class CacheWarmer:
    """
    缓存预热器

    特性：
    - 多种预热策略支持
    - 访问模式学习
    - 依赖关系分析
    - 智能优先级调度
    """

    def __init__(self, cache_service, max_history: int = 10000):
        """
        初始化缓存预热器

        Args:
            cache_service: 缓存服务实例
            max_history: 最大访问历史记录数
        """
        self.cache_service = cache_service
        self.max_history = max_history

        # 预热模式
        self.warmup_patterns: list[WarmupPattern] = []

        # 访问历史记录
        self.access_history: deque = deque(maxlen=max_history)

        # 依赖关系图
        self.dependencies: dict[str, set[str]] = defaultdict(set)

        # 预热统计
        self.stats = {"total_warmed": 0, "successful_warms": 0, "failed_warms": 0, "patterns_used": defaultdict(int)}

        # 控制标志
        self._running = False
        self._warmup_task: asyncio.Task | None = None

        logger.info(f"CacheWarmer initialized with max_history={max_history}")

    def add_warmup_pattern(self, pattern: WarmupPattern):
        """
        添加预热模式

        Args:
            pattern: 预热模式对象
        """
        self.warmup_patterns.append(pattern)
        # 按优先级排序
        self.warmup_patterns.sort(key=lambda x: x.priority)
        logger.info(f"Added warmup pattern: {pattern.name} ({pattern.pattern})")

    def record_access(self, key: str):
        """
        记录缓存访问

        Args:
            key: 访问的键
        """
        timestamp = time.time()

        # 更新访问历史
        self.access_history.append(AccessRecord(key, timestamp))

        # 更新访问频率统计
        # 这里可以实现更复杂的频率分析逻辑

        logger.debug(f"Recorded access for key: {key}")

    def add_dependency(self, dependent_key: str, dependency_key: str):
        """
        添加缓存依赖关系

        Args:
            dependent_key: 依赖方键
            dependency_key: 被依赖方键
        """
        self.dependencies[dependent_key].add(dependency_key)
        logger.debug(f"Added dependency: {dependent_key} -> {dependency_key}")

    async def start_automatic_warming(self, interval: int = 300):
        """
        启动自动预热

        Args:
            interval: 预热间隔（秒）
        """
        if self._running:
            logger.warning("Cache warmer is already running")
            return

        self._running = True
        self._warmup_task = asyncio.create_task(self._automatic_warming_loop(interval))
        logger.info(f"Automatic cache warming started with interval={interval}s")

    async def stop_automatic_warming(self):
        """停止自动预热"""
        if not self._running:
            return

        self._running = False
        if self._warmup_task:
            self._warmup_task.cancel()
            try:
                await self._warmup_task
            except asyncio.CancelledError:
                pass
        logger.info("Automatic cache warming stopped")

    async def _automatic_warming_loop(self, interval: int):
        """自动预热循环"""
        while self._running:
            try:
                await self.perform_comprehensive_warming()
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in automatic warming loop: {e}")
                await asyncio.sleep(60)  # 出错时等待1分钟后重试

    async def perform_comprehensive_warming(self):
        """执行综合预热"""
        logger.info("Starting comprehensive cache warming")
        start_time = time.time()

        # 1. 基于模式的预热
        await self._warmup_by_patterns()

        # 2. 基于访问模式的预热
        await self._warmup_by_access_patterns()

        # 3. 基于依赖关系的预热
        await self._warmup_by_dependencies()

        elapsed = time.time() - start_time
        logger.info(f"Comprehensive warming completed in {elapsed:.2f}s")
        self._log_warming_stats()

    async def _warmup_by_patterns(self):
        """基于预设模式进行预热"""
        for pattern in self.warmup_patterns:
            if pattern.strategy != WarmupStrategy.PATTERN_BASED:
                continue

            try:
                warmed_count = await self._warmup_pattern(pattern)
                self.stats["patterns_used"][pattern.name] += warmed_count
                logger.info(f"Warmed {warmed_count} items for pattern: {pattern.name}")

            except Exception as e:
                logger.error(f"Failed to warm pattern {pattern.name}: {e}")

    async def _warmup_pattern(self, pattern: WarmupPattern) -> int:
        """
        预热单个模式

        Args:
            pattern: 预热模式

        Returns:
            预热成功的项目数
        """
        # 这里需要根据具体的缓存实现来发现匹配的键
        # 简化实现：假设我们知道要预热的键集合
        warmed_count = 0

        # 示例：预热用户相关信息
        if pattern.pattern.startswith("user:"):
            # 模拟预热用户数据
            user_ids = await self._discover_user_keys()
            for user_id in user_ids:
                try:
                    # 这里应该调用实际的数据加载函数
                    await self.cache_service.get_or_set(
                        f"user:{user_id}", lambda uid=user_id: self._load_user_data(uid), pattern.ttl
                    )
                    warmed_count += 1
                except Exception as e:
                    logger.error(f"Failed to warm user {user_id}: {e}")

        # 示例：预热电影相关信息
        elif pattern.pattern.startswith("movie:"):
            movie_ids = await self._discover_movie_keys()
            for movie_id in movie_ids:
                try:
                    await self.cache_service.get_or_set(
                        f"movie:{movie_id}", lambda mid=movie_id: self._load_movie_data(mid), pattern.ttl
                    )
                    warmed_count += 1
                except Exception as e:
                    logger.error(f"Failed to warm movie {movie_id}: {e}")

        self.stats["total_warmed"] += warmed_count
        return warmed_count

    async def _warmup_by_access_patterns(self):
        """基于访问模式进行预热"""
        if not self.access_history:
            return

        # 分析访问模式
        access_frequency = defaultdict(int)
        recent_accesses = list(self.access_history)[-1000:]  # 最近1000次访问

        for record in recent_accesses:
            access_frequency[record.key] += 1

        # 预热高频访问的键
        high_freq_keys = [
            key
            for key, freq in sorted(access_frequency.items(), key=lambda x: x[1], reverse=True)[:50]  # 预热前50个高频键
        ]

        warmed_count = 0
        for key in high_freq_keys:
            try:
                # 尝试刷新这些键的缓存
                await self.cache_service.get(key)  # 这会触发重新加载
                warmed_count += 1
            except Exception as e:
                logger.error(f"Failed to warm key {key}: {e}")

        logger.info(f"Warmed {warmed_count} high-frequency keys")

    async def _warmup_by_dependencies(self):
        """基于依赖关系进行预热"""
        warmed_count = 0

        # 对于有依赖关系的键，确保依赖项先被预热
        for dependent_key, dependencies in self.dependencies.items():
            try:
                # 先预热依赖项
                for dep_key in dependencies:
                    await self.cache_service.get(dep_key)

                # 再预热依赖方
                await self.cache_service.get(dependent_key)
                warmed_count += 1

            except Exception as e:
                logger.error(f"Failed to warm dependency chain for {dependent_key}: {e}")

        logger.info(f"Warmed {warmed_count} dependency chains")

    async def schedule_warming(self, keys: list[str], delay: float = 0):
        """
        延迟预热指定键

        Args:
            keys: 要预热的键列表
            delay: 延迟时间（秒）
        """

        async def delayed_warmup():
            await asyncio.sleep(delay)
            for key in keys:
                try:
                    await self.cache_service.get(key)
                    logger.debug(f"Scheduled warmup completed for key: {key}")
                except Exception as e:
                    logger.error(f"Failed scheduled warmup for key {key}: {e}")

        asyncio.create_task(delayed_warmup())

    def get_stats(self) -> dict[str, Any]:
        """
        获取预热统计信息

        Returns:
            统计信息字典
        """
        return {
            **self.stats,
            "active_patterns": len(self.warmup_patterns),
            "access_history_size": len(self.access_history),
            "dependencies_count": len(self.dependencies),
            "running": self._running,
        }

    def _log_warming_stats(self):
        """记录预热统计"""
        stats = self.get_stats()
        logger.info(
            f"Cache warming stats - "
            f"Total warmed: {stats['total_warmed']}, "
            f"Patterns: {stats['active_patterns']}, "
            f"Access history: {stats['access_history_size']}"
        )

    # 模拟数据加载函数（实际使用时需要替换为真实的业务逻辑）
    async def _discover_user_keys(self) -> list[str]:
        """发现用户键（模拟实现）"""
        # 实际实现应该查询数据库或其他数据源
        return [f"user_{i}" for i in range(1, 11)]

    async def _discover_movie_keys(self) -> list[str]:
        """发现电影键（模拟实现）"""
        return [f"movie_{i}" for i in range(1, 21)]

    async def _load_user_data(self, user_id: str) -> dict[str, Any]:
        """加载用户数据（模拟实现）"""
        # 模拟耗时操作
        await asyncio.sleep(0.01)
        return {"id": user_id, "name": f"User {user_id}", "email": f"user{user_id}@example.com"}

    async def _load_movie_data(self, movie_id: str) -> dict[str, Any]:
        """加载电影数据（模拟实现）"""
        await asyncio.sleep(0.01)
        return {"id": movie_id, "title": f"Movie {movie_id}", "year": 2023, "rating": 8.5}


# 便捷函数和全局实例
_global_cache_warmer: CacheWarmer | None = None


def get_cache_warmer(cache_service) -> CacheWarmer:
    """
    获取全局缓存预热器实例

    Args:
        cache_service: 缓存服务实例

    Returns:
        缓存预热器实例
    """
    global _global_cache_warmer

    if _global_cache_warmer is None:
        _global_cache_warmer = CacheWarmer(cache_service)

    return _global_cache_warmer


def setup_default_warming_patterns(warmer: CacheWarmer):
    """
    设置默认预热模式

    Args:
        warmer: 缓存预热器实例
    """
    # 用户数据预热模式
    warmer.add_warmup_pattern(
        WarmupPattern(
            name="user_data",
            pattern="user:*",
            priority=1,
            ttl=1800,  # 30分钟
            strategy=WarmupStrategy.PATTERN_BASED,
        )
    )

    # 电影数据预热模式
    warmer.add_warmup_pattern(
        WarmupPattern(
            name="movie_data",
            pattern="movie:*",
            priority=2,
            ttl=3600,  # 1小时
            strategy=WarmupStrategy.PATTERN_BASED,
        )
    )

    # 高频访问数据预热
    warmer.add_warmup_pattern(
        WarmupPattern(
            name="hot_data",
            pattern="hot:*",
            priority=1,
            ttl=600,  # 10分钟
            strategy=WarmupStrategy.ACCESS_PATTERN,
        )
    )

    logger.info("Default warming patterns configured")
