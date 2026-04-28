"""
数据库连接池监控模块

提供连接池状态追踪、性能指标收集和健康检查功能
"""

import threading
import time
from collections import deque
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.core.logging import get_logger


logger = get_logger(__name__)


@dataclass
class ConnectionMetrics:
    """连接指标数据类"""

    # 连接计数
    total_created: int = 0
    total_closed: int = 0
    current_active: int = 0
    peak_active: int = 0

    # 等待队列
    current_waiting: int = 0
    peak_waiting: int = 0
    total_waits: int = 0

    # 性能指标
    total_wait_time_ms: float = 0.0
    total_usage_time_ms: float = 0.0

    # 错误统计
    connection_errors: int = 0
    timeout_errors: int = 0

    # 时间戳
    last_activity: datetime | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        avg_wait_time = self.total_wait_time_ms / self.total_waits if self.total_waits > 0 else 0
        avg_usage_time = self.total_usage_time_ms / self.total_created if self.total_created > 0 else 0

        return {
            "connections": {
                "total_created": self.total_created,
                "total_closed": self.total_closed,
                "current_active": self.current_active,
                "peak_active": self.peak_active,
            },
            "waiting": {
                "current_waiting": self.current_waiting,
                "peak_waiting": self.peak_waiting,
                "total_waits": self.total_waits,
            },
            "performance": {
                "avg_wait_time_ms": round(avg_wait_time, 2),
                "avg_usage_time_ms": round(avg_usage_time, 2),
                "total_wait_time_ms": round(self.total_wait_time_ms, 2),
                "total_usage_time_ms": round(self.total_usage_time_ms, 2),
            },
            "errors": {
                "connection_errors": self.connection_errors,
                "timeout_errors": self.timeout_errors,
            },
            "timestamps": {
                "last_activity": self.last_activity.isoformat() if self.last_activity else None,
                "created_at": self.created_at.isoformat(),
            },
        }


class ConnectionTracker:
    """
    连接追踪器

    追踪每个连接的生命周期和使用情况
    """

    def __init__(self, max_history: int = 1000):
        """
        初始化连接追踪器

        Args:
            max_history: 最大历史记录数
        """
        self._lock = threading.Lock()
        self._metrics = ConnectionMetrics()
        self._active_connections: dict[int, dict[str, Any]] = {}
        self._history: deque = deque(maxlen=max_history)

    def on_connection_created(self, conn_id: int, source: str = "unknown") -> None:
        """
        连接创建事件

        Args:
            conn_id: 连接ID
            source: 连接来源
        """
        with self._lock:
            self._metrics.total_created += 1
            self._metrics.current_active += 1
            self._metrics.peak_active = max(self._metrics.peak_active, self._metrics.current_active)
            self._metrics.last_activity = datetime.utcnow()

            self._active_connections[conn_id] = {
                "created_at": time.time(),
                "source": source,
                "thread_id": threading.current_thread().ident,
            }

            logger.debug(f"Connection created: {conn_id} from {source}")

    def on_connection_closed(self, conn_id: int) -> None:
        """
        连接关闭事件

        Args:
            conn_id: 连接ID
        """
        with self._lock:
            if conn_id in self._active_connections:
                conn_info = self._active_connections.pop(conn_id)
                usage_time = (time.time() - conn_info["created_at"]) * 1000
                self._metrics.total_usage_time_ms += usage_time

                # 添加到历史记录
                self._history.append(
                    {
                        "conn_id": conn_id,
                        "source": conn_info["source"],
                        "usage_time_ms": usage_time,
                        "closed_at": datetime.utcnow().isoformat(),
                    }
                )

            self._metrics.total_closed += 1
            self._metrics.current_active = max(0, self._metrics.current_active - 1)
            self._metrics.last_activity = datetime.utcnow()

            logger.debug(f"Connection closed: {conn_id}")

    def on_wait_start(self) -> float:
        """
        等待开始事件

        Returns:
            等待开始时间戳
        """
        with self._lock:
            self._metrics.current_waiting += 1
            self._metrics.peak_waiting = max(self._metrics.peak_waiting, self._metrics.current_waiting)
            self._metrics.total_waits += 1

        return time.time()

    def on_wait_end(self, start_time: float) -> None:
        """
        等待结束事件

        Args:
            start_time: 等待开始时间戳
        """
        wait_time = (time.time() - start_time) * 1000

        with self._lock:
            self._metrics.current_waiting = max(0, self._metrics.current_waiting - 1)
            self._metrics.total_wait_time_ms += wait_time

    def on_connection_error(self, error_type: str = "connection") -> None:
        """
        连接错误事件

        Args:
            error_type: 错误类型
        """
        with self._lock:
            if error_type == "timeout":
                self._metrics.timeout_errors += 1
            else:
                self._metrics.connection_errors += 1
            self._metrics.last_activity = datetime.utcnow()

            logger.warning(f"Connection error: {error_type}")

    def get_metrics(self) -> ConnectionMetrics:
        """获取当前指标"""
        with self._lock:
            return self._metrics

    def get_active_connections(self) -> list[dict[str, Any]]:
        """获取活跃连接列表"""
        with self._lock:
            current_time = time.time()
            return [
                {
                    "conn_id": conn_id,
                    "age_ms": round((current_time - info["created_at"]) * 1000, 2),
                    "source": info["source"],
                    "thread_id": info["thread_id"],
                }
                for conn_id, info in self._active_connections.items()
            ]

    def get_history(self, limit: int = 100) -> list[dict[str, Any]]:
        """
        获取连接历史记录

        Args:
            limit: 返回记录数量限制

        Returns:
            历史记录列表
        """
        with self._lock:
            return list(self._history)[-limit:]

    def reset_metrics(self) -> None:
        """重置指标（保留活跃连接）"""
        with self._lock:
            self._metrics = ConnectionMetrics()
            # 保留当前活跃连接数
            self._metrics.current_active = len(self._active_connections)
            self._metrics.total_created = len(self._active_connections)


class DatabasePoolMonitor:
    """
    数据库连接池监控器

    提供连接池状态监控、性能指标收集和告警功能
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """初始化监控器"""
        if self._initialized:
            return

        self._tracker = ConnectionTracker()
        self._alerts: list[dict[str, Any]] = []
        self._alert_handlers: list[Callable] = []
        self._thresholds = {
            "max_active_connections": 50,
            "max_wait_time_ms": 5000,
            "max_waiting_count": 10,
            "max_connection_age_ms": 300000,  # 5分钟
        }
        self._initialized = True

        logger.info("Database pool monitor initialized")

    @classmethod
    def get_instance(cls) -> "DatabasePoolMonitor":
        """获取监控器实例"""
        return cls()

    @contextmanager
    def track_connection(self, conn_id: int, source: str = "unknown"):
        """
        追踪连接生命周期的上下文管理器

        Args:
            conn_id: 连接ID
            source: 连接来源

        Yields:
            None
        """
        self._tracker.on_connection_created(conn_id, source)
        try:
            yield
        finally:
            self._tracker.on_connection_closed(conn_id)

    @contextmanager
    def track_wait(self):
        """
        追踪等待时间的上下文管理器

        Yields:
            None
        """
        start_time = self._tracker.on_wait_start()
        try:
            yield
        finally:
            self._tracker.on_wait_end(start_time)

    def record_error(self, error_type: str = "connection") -> None:
        """
        记录连接错误

        Args:
            error_type: 错误类型
        """
        self._tracker.on_connection_error(error_type)

    def get_status(self) -> dict[str, Any]:
        """
        获取连接池完整状态

        Returns:
            状态信息字典
        """
        metrics = self._tracker.get_metrics()

        return {
            "metrics": metrics.to_dict(),
            "active_connections": self._tracker.get_active_connections(),
            "thresholds": self._thresholds,
            "alerts_count": len(self._alerts),
        }

    def get_metrics(self) -> ConnectionMetrics:
        """获取当前指标"""
        return self._tracker.get_metrics()

    def get_active_connections(self) -> list[dict[str, Any]]:
        """获取活跃连接列表"""
        return self._tracker.get_active_connections()

    def check_health(self) -> dict[str, Any]:
        """
        检查连接池健康状态

        Returns:
            健康检查结果
        """
        metrics = self._tracker.get_metrics()
        issues = []

        # 检查活跃连接数
        if metrics.current_active > self._thresholds["max_active_connections"]:
            issues.append(
                {
                    "type": "high_active_connections",
                    "message": f"Active connections ({metrics.current_active}) exceeds threshold ({self._thresholds['max_active_connections']})",
                    "severity": "warning",
                }
            )

        # 检查等待队列
        if metrics.current_waiting > self._thresholds["max_waiting_count"]:
            issues.append(
                {
                    "type": "high_waiting_count",
                    "message": f"Waiting connections ({metrics.current_waiting}) exceeds threshold ({self._thresholds['max_waiting_count']})",
                    "severity": "warning",
                }
            )

        # 检查平均等待时间
        avg_wait = metrics.total_wait_time_ms / metrics.total_waits if metrics.total_waits > 0 else 0
        if avg_wait > self._thresholds["max_wait_time_ms"]:
            issues.append(
                {
                    "type": "high_wait_time",
                    "message": f"Average wait time ({avg_wait:.2f}ms) exceeds threshold ({self._thresholds['max_wait_time_ms']}ms)",
                    "severity": "warning",
                }
            )

        # 检查连接泄漏（长时间活跃的连接）
        active_conns = self._tracker.get_active_connections()
        leaked = [conn for conn in active_conns if conn["age_ms"] > self._thresholds["max_connection_age_ms"]]
        if leaked:
            issues.append(
                {
                    "type": "potential_leak",
                    "message": f"Found {len(leaked)} connections active for more than {self._thresholds['max_connection_age_ms']}ms",
                    "severity": "warning",
                    "connections": leaked[:10],  # 最多显示10个
                }
            )

        # 检查错误率
        error_rate = metrics.connection_errors / metrics.total_created * 100 if metrics.total_created > 0 else 0
        if error_rate > 5:  # 错误率超过 5%
            issues.append(
                {
                    "type": "high_error_rate",
                    "message": f"Connection error rate ({error_rate:.2f}%) is high",
                    "severity": "error",
                }
            )

        # 确定健康状态
        if any(i["severity"] == "error" for i in issues):
            status = "unhealthy"
        elif issues:
            status = "warning"
        else:
            status = "healthy"

        return {
            "status": status,
            "issues": issues,
            "metrics_summary": {
                "active_connections": metrics.current_active,
                "waiting_connections": metrics.current_waiting,
                "avg_wait_time_ms": round(avg_wait, 2),
                "error_rate_percent": round(error_rate, 2),
            },
            "checked_at": datetime.utcnow().isoformat(),
        }

    def set_threshold(self, name: str, value: Any) -> None:
        """
        设置告警阈值

        Args:
            name: 阈值名称
            value: 阈值
        """
        if name in self._thresholds:
            self._thresholds[name] = value
            logger.info(f"Threshold updated: {name} = {value}")
        else:
            raise ValueError(f"Unknown threshold: {name}")

    def add_alert_handler(self, handler: Callable) -> None:
        """
        添加告警处理器

        Args:
            handler: 告警处理函数
        """
        self._alert_handlers.append(handler)

    def reset_metrics(self) -> None:
        """重置指标"""
        self._tracker.reset_metrics()
        logger.info("Database pool metrics reset")


# 全局监控器实例
_monitor: DatabasePoolMonitor | None = None


def get_pool_monitor() -> DatabasePoolMonitor:
    """获取数据库连接池监控器实例"""
    global _monitor
    if _monitor is None:
        _monitor = DatabasePoolMonitor()
    return _monitor
