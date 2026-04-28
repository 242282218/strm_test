"""
缓存统计和可视化模块

提供详细的缓存性能统计、命中率分析和可视化数据接口
"""

import base64
import io
import json
import time
from collections import defaultdict, deque
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

import matplotlib.pyplot as plt

from app.core.logging import get_logger


logger = get_logger(__name__)


@dataclass
class CacheStatPoint:
    """缓存统计数据点"""

    timestamp: float
    hits: int
    misses: int
    hit_rate: float
    size: int
    evictions: int
    memory_usage_mb: float


@dataclass
class CachePerformanceReport:
    """缓存性能报告"""

    period: str  # 'hour', 'day', 'week'
    total_requests: int
    total_hits: int
    total_misses: int
    average_hit_rate: float
    peak_hit_rate: float
    lowest_hit_rate: float
    average_size: float
    peak_memory_mb: float
    total_evictions: int
    trends: dict[str, Any]


class CacheStatistics:
    """
    缓存统计分析器

    特性：
    - 实时统计收集
    - 历史数据分析
    - 趋势预测
    - 性能报告生成
    """

    def __init__(self, max_history_points: int = 1000):
        """
        初始化缓存统计分析器

        Args:
            max_history_points: 最大历史数据点数
        """
        self.max_history_points = max_history_points
        self.history: deque = deque(maxlen=max_history_points)

        # 当前统计
        self.current_stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "deletes": 0,
            "evictions": 0,
            "expirations": 0,
            "size": 0,
            "memory_usage_mb": 0.0,
        }

        # 时间窗口统计
        self.window_stats = defaultdict(lambda: {"hits": 0, "misses": 0, "requests": 0})

        logger.info(f"CacheStatistics initialized with max_history={max_history_points}")

    def record_hit(self, cache_size: int = 0, memory_mb: float = 0.0):
        """
        记录缓存命中

        Args:
            cache_size: 当前缓存大小
            memory_mb: 内存使用量(MB)
        """
        self.current_stats["hits"] += 1
        self.current_stats["size"] = cache_size
        self.current_stats["memory_usage_mb"] = memory_mb
        self._record_stat_point()

    def record_miss(self, cache_size: int = 0, memory_mb: float = 0.0):
        """
        记录缓存未命中

        Args:
            cache_size: 当前缓存大小
            memory_mb: 内存使用量(MB)
        """
        self.current_stats["misses"] += 1
        self.current_stats["size"] = cache_size
        self.current_stats["memory_usage_mb"] = memory_mb
        self._record_stat_point()

    def record_eviction(self):
        """记录缓存淘汰"""
        self.current_stats["evictions"] += 1

    def record_expiration(self):
        """记录缓存过期"""
        self.current_stats["expirations"] += 1

    def record_set(self):
        """记录缓存设置"""
        self.current_stats["sets"] += 1

    def record_delete(self):
        """记录缓存删除"""
        self.current_stats["deletes"] += 1

    def _record_stat_point(self):
        """记录统计数据点"""
        timestamp = time.time()
        total_requests = self.current_stats["hits"] + self.current_stats["misses"]
        hit_rate = self.current_stats["hits"] / total_requests * 100 if total_requests > 0 else 0

        stat_point = CacheStatPoint(
            timestamp=timestamp,
            hits=self.current_stats["hits"],
            misses=self.current_stats["misses"],
            hit_rate=hit_rate,
            size=self.current_stats["size"],
            evictions=self.current_stats["evictions"],
            memory_usage_mb=self.current_stats["memory_usage_mb"],
        )

        self.history.append(stat_point)

    def get_current_stats(self) -> dict[str, Any]:
        """
        获取当前统计信息

        Returns:
            当前统计字典
        """
        total_requests = self.current_stats["hits"] + self.current_stats["misses"]
        hit_rate = self.current_stats["hits"] / total_requests * 100 if total_requests > 0 else 0

        return {
            **self.current_stats,
            "total_requests": total_requests,
            "hit_rate": round(hit_rate, 2),
            "miss_rate": round(100 - hit_rate, 2) if total_requests > 0 else 0,
            "eviction_rate": (self.current_stats["evictions"] / total_requests * 100 if total_requests > 0 else 0),
        }

    def get_history_stats(self, hours: int = 24) -> list[dict[str, Any]]:
        """
        获取历史统计数据

        Args:
            hours: 时间范围（小时）

        Returns:
            历史统计数据列表
        """
        cutoff_time = time.time() - (hours * 3600)
        recent_points = [point for point in self.history if point.timestamp >= cutoff_time]

        return [
            {
                "timestamp": point.timestamp,
                "datetime": datetime.fromtimestamp(point.timestamp).isoformat(),
                "hits": point.hits,
                "misses": point.misses,
                "hit_rate": round(point.hit_rate, 2),
                "size": point.size,
                "evictions": point.evictions,
                "memory_usage_mb": round(point.memory_usage_mb, 2),
            }
            for point in recent_points
        ]

    def generate_performance_report(self, period: str = "day") -> CachePerformanceReport:
        """
        生成性能报告

        Args:
            period: 报告周期 ('hour', 'day', 'week')

        Returns:
            性能报告对象
        """
        # 确定时间范围
        if period == "hour":
            hours = 1
        elif period == "day":
            hours = 24
        elif period == "week":
            hours = 168
        else:
            hours = 24

        history_stats = self.get_history_stats(hours)

        if not history_stats:
            # 返回空报告
            return CachePerformanceReport(
                period=period,
                total_requests=0,
                total_hits=0,
                total_misses=0,
                average_hit_rate=0.0,
                peak_hit_rate=0.0,
                lowest_hit_rate=0.0,
                average_size=0.0,
                peak_memory_mb=0.0,
                total_evictions=0,
                trends={},
            )

        # 计算统计指标
        total_requests = sum(s["hits"] + s["misses"] for s in history_stats)
        total_hits = sum(s["hits"] for s in history_stats)
        total_misses = sum(s["misses"] for s in history_stats)

        hit_rates = [s["hit_rate"] for s in history_stats]
        sizes = [s["size"] for s in history_stats]
        memory_usages = [s["memory_usage_mb"] for s in history_stats]
        evictions = sum(s["evictions"] for s in history_stats)

        report = CachePerformanceReport(
            period=period,
            total_requests=total_requests,
            total_hits=total_hits,
            total_misses=total_misses,
            average_hit_rate=round(sum(hit_rates) / len(hit_rates), 2),
            peak_hit_rate=round(max(hit_rates), 2),
            lowest_hit_rate=round(min(hit_rates), 2),
            average_size=round(sum(sizes) / len(sizes), 2),
            peak_memory_mb=round(max(memory_usages), 2),
            total_evictions=evictions,
            trends=self._calculate_trends(history_stats),
        )

        return report

    def _calculate_trends(self, history_stats: list[dict]) -> dict[str, Any]:
        """
        计算趋势分析

        Args:
            history_stats: 历史统计数据

        Returns:
            趋势分析结果
        """
        if len(history_stats) < 2:
            return {}

        # 计算最近的趋势
        recent_stats = history_stats[-10:] if len(history_stats) >= 10 else history_stats

        hit_rates = [s["hit_rate"] for s in recent_stats]
        sizes = [s["size"] for s in recent_stats]

        # 简单的线性趋势分析
        time_points = list(range(len(recent_stats)))

        # 命中率趋势
        hit_rate_slope = self._calculate_slope(time_points, hit_rates)

        # 缓存大小趋势
        size_slope = self._calculate_slope(time_points, sizes)

        return {
            "hit_rate_trend": "increasing" if hit_rate_slope > 0 else "decreasing" if hit_rate_slope < 0 else "stable",
            "size_trend": "growing" if size_slope > 0 else "shrinking" if size_slope < 0 else "stable",
            "hit_rate_slope": round(hit_rate_slope, 4),
            "size_slope": round(size_slope, 2),
        }

    def _calculate_slope(self, x: list[float], y: list[float]) -> float:
        """
        计算线性回归斜率

        Args:
            x: x坐标列表
            y: y坐标列表

        Returns:
            斜率值
        """
        if len(x) != len(y) or len(x) < 2:
            return 0.0

        n = len(x)
        sum_x = sum(x)
        sum_y = sum(y)
        sum_xy = sum(xi * yi for xi, yi in zip(x, y))
        sum_xx = sum(xi * xi for xi in x)

        denominator = n * sum_xx - sum_x * sum_x
        if denominator == 0:
            return 0.0

        slope = (n * sum_xy - sum_x * sum_y) / denominator
        return slope

    def export_stats_json(self) -> str:
        """
        导出统计信息为JSON格式

        Returns:
            JSON字符串
        """
        data = {
            "current_stats": self.get_current_stats(),
            "history": self.get_history_stats(24),
            "reports": {
                "hourly": asdict(self.generate_performance_report("hour")),
                "daily": asdict(self.generate_performance_report("day")),
                "weekly": asdict(self.generate_performance_report("week")),
            },
        }
        return json.dumps(data, indent=2, default=str)

    def clear_history(self):
        """清空历史统计数据"""
        self.history.clear()
        logger.info("Cache statistics history cleared")


class CacheVisualizer:
    """
    缓存数据可视化器

    提供图表生成和可视化功能
    """

    def __init__(self, statistics: CacheStatistics):
        """
        初始化可视化器

        Args:
            statistics: 缓存统计实例
        """
        self.statistics = statistics
        # 设置matplotlib中文字体支持
        plt.rcParams["font.sans-serif"] = ["SimHei", "Arial Unicode MS", "DejaVu Sans"]
        plt.rcParams["axes.unicode_minus"] = False

    def generate_hit_rate_chart(self, hours: int = 24) -> str:
        """
        生成命中率图表

        Args:
            hours: 时间范围（小时）

        Returns:
            base64编码的PNG图像
        """
        history_stats = self.statistics.get_history_stats(hours)

        if not history_stats:
            return self._generate_empty_chart("暂无数据")

        timestamps = [s["timestamp"] for s in history_stats]
        hit_rates = [s["hit_rate"] for s in history_stats]

        # 转换为相对时间
        base_time = timestamps[0]
        relative_times = [(t - base_time) / 3600 for t in timestamps]  # 转换为小时

        plt.figure(figsize=(12, 6))
        plt.plot(relative_times, hit_rates, "b-", linewidth=2, marker="o", markersize=4)
        plt.xlabel("时间 (小时)")
        plt.ylabel("命中率 (%)")
        plt.title(f"缓存命中率趋势 ({hours}小时)")
        plt.grid(True, alpha=0.3)
        plt.ylim(0, 100)

        # 添加统计信息
        avg_hit_rate = sum(hit_rates) / len(hit_rates)
        plt.axhline(y=avg_hit_rate, color="r", linestyle="--", alpha=0.7, label=f"平均值: {avg_hit_rate:.1f}%")
        plt.legend()

        return self._plt_to_base64()

    def generate_memory_usage_chart(self, hours: int = 24) -> str:
        """
        生成内存使用图表

        Args:
            hours: 时间范围（小时）

        Returns:
            base64编码的PNG图像
        """
        history_stats = self.statistics.get_history_stats(hours)

        if not history_stats:
            return self._generate_empty_chart("暂无数据")

        timestamps = [s["timestamp"] for s in history_stats]
        memory_usage = [s["memory_usage_mb"] for s in history_stats]

        base_time = timestamps[0]
        relative_times = [(t - base_time) / 3600 for t in timestamps]

        plt.figure(figsize=(12, 6))
        plt.plot(relative_times, memory_usage, "g-", linewidth=2, marker="s", markersize=4)
        plt.xlabel("时间 (小时)")
        plt.ylabel("内存使用 (MB)")
        plt.title(f"缓存内存使用情况 ({hours}小时)")
        plt.grid(True, alpha=0.3)

        return self._plt_to_base64()

    def generate_comparison_chart(self) -> str:
        """
        生成综合对比图表

        Returns:
            base64编码的PNG图像
        """
        daily_report = self.statistics.generate_performance_report("day")
        weekly_report = self.statistics.generate_performance_report("week")

        periods = ["24小时", "7天"]
        hit_rates = [daily_report.average_hit_rate, weekly_report.average_hit_rate]
        memory_usage = [daily_report.peak_memory_mb, weekly_report.peak_memory_mb]

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))

        # 命中率对比
        bars1 = ax1.bar(periods, hit_rates, color=["skyblue", "lightgreen"])
        ax1.set_ylabel("平均命中率 (%)")
        ax1.set_title("命中率对比")
        ax1.set_ylim(0, 100)

        # 添加数值标签
        for bar in bars1:
            height = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width() / 2.0, height, f"{height:.1f}%", ha="center", va="bottom")

        # 内存使用对比
        bars2 = ax2.bar(periods, memory_usage, color=["orange", "pink"])
        ax2.set_ylabel("峰值内存使用 (MB)")
        ax2.set_title("内存使用对比")

        # 添加数值标签
        for bar in bars2:
            height = bar.get_height()
            ax2.text(bar.get_x() + bar.get_width() / 2.0, height, f"{height:.0f}MB", ha="center", va="bottom")

        plt.tight_layout()
        return self._plt_to_base64()

    def _plt_to_base64(self) -> str:
        """
        将matplotlib图表转换为base64编码的PNG

        Returns:
            base64编码的图像字符串
        """
        buffer = io.BytesIO()
        plt.savefig(buffer, format="png", dpi=100, bbox_inches="tight")
        buffer.seek(0)
        image_png = buffer.getvalue()
        buffer.close()
        plt.close()  # 关闭图表释放内存

        return base64.b64encode(image_png).decode()

    def _generate_empty_chart(self, message: str) -> str:
        """
        生成空图表

        Args:
            message: 显示的消息

        Returns:
            base64编码的PNG图像
        """
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.text(0.5, 0.5, message, ha="center", va="center", fontsize=16)
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis("off")

        return self._plt_to_base64()


# 全局实例管理
_global_statistics: CacheStatistics | None = None
_global_visualizer: CacheVisualizer | None = None


def get_cache_statistics() -> CacheStatistics:
    """获取全局缓存统计实例"""
    global _global_statistics
    if _global_statistics is None:
        _global_statistics = CacheStatistics()
    return _global_statistics


def get_cache_visualizer() -> CacheVisualizer:
    """获取全局缓存可视化实例"""
    global _global_visualizer
    if _global_visualizer is None:
        stats = get_cache_statistics()
        _global_visualizer = CacheVisualizer(stats)
    return _global_visualizer
