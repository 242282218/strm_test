"""
数据库连接池监控模块

提供连接池健康检查、状态监控和告警功能
"""

import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from app.core.db import check_pool_health, get_pool_config, get_pool_status
from app.core.logging import get_logger


logger = get_logger(__name__)


class HealthStatus(Enum):
    """健康状态枚举"""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class PoolMetrics:
    """连接池指标"""

    timestamp: datetime
    pool_type: str
    mode: str
    pool_size: int | None = None
    checked_in: int | None = None
    checked_out: int | None = None
    overflow: int | None = None
    invalid: int | None = None
    healthy: bool = True
    message: str = ""


@dataclass
class MonitorConfig:
    """监控配置"""

    # 健康检查间隔（秒）
    check_interval: int = 60
    # 告警阈值：检出连接数占比
    checkout_threshold: float = 0.8
    # 告警阈值：无效连接数
    invalid_threshold: int = 3
    # 历史记录保留数量
    history_size: int = 100
    # 是否启用告警回调
    enable_alerts: bool = True


class PoolMonitor:
    """
    连接池监控器

    功能:
        - 定期健康检查
        - 指标收集和存储
        - 告警触发
        - 状态查询 API
    """

    def __init__(self, config: MonitorConfig | None = None):
        """
        初始化监控器

        Args:
            config: 监控配置
        """
        self.config = config or MonitorConfig()
        self._metrics_history: list[PoolMetrics] = []
        self._alert_callbacks: list[Callable[[str, PoolMetrics], None]] = []
        self._monitoring = False
        self._monitor_thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def add_alert_callback(self, callback: Callable[[str, PoolMetrics], None]) -> None:
        """
        添加告警回调函数

        Args:
            callback: 回调函数，接收 (alert_level, metrics) 参数
        """
        self._alert_callbacks.append(callback)
        logger.info(f"Alert callback added: {callback.__name__}")

    def collect_metrics(self) -> PoolMetrics:
        """
        收集当前连接池指标

        Returns:
            PoolMetrics 实例
        """
        health_result = check_pool_health()
        pool_status = health_result.get("pool_status", {})

        metrics = PoolMetrics(
            timestamp=datetime.utcnow(),
            pool_type=pool_status.get("pool_type", "unknown"),
            mode=pool_status.get("mode", "unknown"),
            healthy=health_result.get("healthy", False),
            message=health_result.get("message", ""),
        )

        # QueuePool 特定指标
        if "pool_size" in pool_status:
            metrics.pool_size = pool_status.get("pool_size")
            metrics.checked_in = pool_status.get("checked_in")
            metrics.checked_out = pool_status.get("checked_out")
            metrics.overflow = pool_status.get("overflow")
            metrics.invalid = pool_status.get("invalid", 0)

        return metrics

    def _add_to_history(self, metrics: PoolMetrics) -> None:
        """添加指标到历史记录"""
        with self._lock:
            self._metrics_history.append(metrics)
            # 保留最近 N 条记录
            if len(self._metrics_history) > self.config.history_size:
                self._metrics_history = self._metrics_history[-self.config.history_size :]

    def _check_alerts(self, metrics: PoolMetrics) -> str | None:
        """
        检查是否需要触发告警

        Args:
            metrics: 当前指标

        Returns:
            告警级别，无告警返回 None
        """
        # 不健康状态
        if not metrics.healthy:
            return "critical"

        # QueuePool 特定检查
        if metrics.pool_size is not None and metrics.pool_size > 0:
            config = get_pool_config()
            total_connections = config.pool_size + config.max_overflow

            # 检出连接占比过高
            if metrics.checked_out is not None:
                checkout_ratio = metrics.checked_out / total_connections
                if checkout_ratio > self.config.checkout_threshold:
                    return "warning"

            # 无效连接过多
            if metrics.invalid is not None and metrics.invalid >= self.config.invalid_threshold:
                return "warning"

        return None

    def _trigger_alerts(self, level: str, metrics: PoolMetrics) -> None:
        """触发告警回调"""
        if not self.config.enable_alerts:
            return

        for callback in self._alert_callbacks:
            try:
                callback(level, metrics)
            except Exception as e:
                logger.error(f"Alert callback failed: {e}")

    def _monitor_loop(self) -> None:
        """监控循环"""
        logger.info("Pool monitor started")

        while self._monitoring:
            try:
                # 收集指标
                metrics = self.collect_metrics()
                self._add_to_history(metrics)

                # 检查告警
                alert_level = self._check_alerts(metrics)
                if alert_level:
                    logger.warning(f"Pool alert triggered: {alert_level}")
                    self._trigger_alerts(alert_level, metrics)

                logger.debug(f"Pool metrics collected: {metrics}")

            except Exception as e:
                logger.error(f"Monitor loop error: {e}")

            # 等待下次检查
            import time

            time.sleep(self.config.check_interval)

        logger.info("Pool monitor stopped")

    def start(self) -> None:
        """启动监控"""
        if self._monitoring:
            logger.warning("Pool monitor is already running")
            return

        self._monitoring = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True, name="PoolMonitor")
        self._monitor_thread.start()
        logger.info(f"Pool monitor started with interval: {self.config.check_interval}s")

    def stop(self) -> None:
        """停止监控"""
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
        logger.info("Pool monitor stopped")

    def get_status(self) -> dict[str, Any]:
        """
        获取监控状态

        Returns:
            监控状态信息
        """
        with self._lock:
            recent_metrics = self._metrics_history[-10:] if self._metrics_history else []

        return {
            "monitoring": self._monitoring,
            "config": {
                "check_interval": self.config.check_interval,
                "checkout_threshold": self.config.checkout_threshold,
                "invalid_threshold": self.config.invalid_threshold,
                "history_size": self.config.history_size,
            },
            "current_metrics": self.collect_metrics().__dict__ if not self._monitoring else None,
            "history_count": len(self._metrics_history),
            "recent_metrics": [m.__dict__ for m in recent_metrics],
        }

    def get_health_summary(self) -> dict[str, Any]:
        """
        获取健康摘要

        Returns:
            健康摘要信息
        """
        health_result = check_pool_health()
        pool_status = get_pool_status()

        # 计算健康状态
        if health_result["healthy"]:
            status = HealthStatus.HEALTHY
        else:
            status = HealthStatus.UNHEALTHY

        # 检查是否降级
        if status == HealthStatus.HEALTHY:
            metrics = self.collect_metrics()
            if metrics.pool_size is not None and metrics.checked_out is not None:
                config = get_pool_config()
                total = config.pool_size + config.max_overflow
                if metrics.checked_out / total > self.config.checkout_threshold:
                    status = HealthStatus.DEGRADED

        return {
            "status": status.value,
            "healthy": health_result["healthy"],
            "message": health_result["message"],
            "pool_status": pool_status,
            "timestamp": datetime.utcnow().isoformat(),
        }


# 全局监控器实例
_monitor_instance: PoolMonitor | None = None


def get_pool_monitor(config: MonitorConfig | None = None) -> PoolMonitor:
    """
    获取全局监控器实例

    Args:
        config: 监控配置（仅首次调用有效）

    Returns:
        PoolMonitor 实例
    """
    global _monitor_instance

    if _monitor_instance is None:
        _monitor_instance = PoolMonitor(config)

    return _monitor_instance


def start_monitoring(config: MonitorConfig | None = None) -> PoolMonitor:
    """
    启动连接池监控

    Args:
        config: 监控配置

    Returns:
        PoolMonitor 实例
    """
    monitor = get_pool_monitor(config)
    monitor.start()
    return monitor


def stop_monitoring() -> None:
    """停止连接池监控"""
    global _monitor_instance

    if _monitor_instance:
        _monitor_instance.stop()


def default_alert_handler(level: str, metrics: PoolMetrics) -> None:
    """
    默认告警处理器

    Args:
        level: 告警级别
        metrics: 指标数据
    """
    if level == "critical":
        logger.critical(f"POOL ALERT [{level}]: {metrics.message}")
    elif level == "warning":
        logger.warning(f"POOL ALERT [{level}]: Pool under pressure - checked_out={metrics.checked_out}")
    else:
        logger.info(f"POOL ALERT [{level}]: {metrics.message}")
