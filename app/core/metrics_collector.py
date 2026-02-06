"""
性能指标收集器模块

提供实时性能指标收集、统计分析和告警功能
"""

import time
import psutil
import threading
from typing import Dict, Any, List, Optional
from collections import deque, defaultdict
from dataclasses import dataclass
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class MetricPoint:
    """指标数据点"""
    timestamp: float
    value: float
    tags: Dict[str, str] = None


class MetricsCollector:
    """指标收集器"""
    
    def __init__(self, max_points: int = 1000):
        """
        初始化指标收集器
        
        Args:
            max_points: 每个指标保留的最大数据点数
        """
        self.max_points = max_points
        self.metrics: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=max_points)
        )
        self.lock = threading.RLock()
        
        logger.info(f"MetricsCollector initialized with max_points={max_points}")
    
    def record_metric(
        self, 
        metric_name: str, 
        value: float, 
        tags: Dict[str, str] = None
    ):
        """
        记录指标数据点
        
        Args:
            metric_name: 指标名称
            value: 指标值
            tags: 标签字典
        """
        point = MetricPoint(
            timestamp=time.time(),
            value=value,
            tags=tags or {}
        )
        
        with self.lock:
            self.metrics[metric_name].append(point)
    
    def get_metric_stats(self, metric_name: str) -> Dict[str, Any]:
        """
        获取指标统计信息
        
        Args:
            metric_name: 指标名称
            
        Returns:
            统计信息字典
        """
        with self.lock:
            if metric_name not in self.metrics:
                return {}
            
            points = list(self.metrics[metric_name])
            if not points:
                return {}
            
            values = [p.value for p in points]
            
            return {
                'count': len(points),
                'min': min(values),
                'max': max(values),
                'avg': sum(values) / len(values),
                'latest': values[-1],
                'timestamp': points[-1].timestamp
            }
    
    def get_recent_points(
        self, 
        metric_name: str, 
        limit: int = 100
    ) -> List[MetricPoint]:
        """
        获取最近的指标数据点
        
        Args:
            metric_name: 指标名称
            limit: 限制返回点数
            
        Returns:
            指标数据点列表
        """
        with self.lock:
            if metric_name not in self.metrics:
                return []
            
            points = list(self.metrics[metric_name])
            return points[-limit:] if points else []


class SystemMonitor:
    """系统监控器"""
    
    def __init__(self, collector: MetricsCollector):
        """
        初始化系统监控器
        
        Args:
            collector: 指标收集器实例
        """
        self.collector = collector
        self.monitoring = False
        self.monitor_thread: Optional[threading.Thread] = None
        self.interval = 5.0  # 监控间隔（秒）
        
        logger.info("SystemMonitor initialized")
    
    def start_monitoring(self, interval: float = 5.0):
        """
        开始系统监控
        
        Args:
            interval: 监控间隔（秒）
        """
        if self.monitoring:
            logger.warning("System monitoring is already running")
            return
        
        self.interval = interval
        self.monitoring = True
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True
        )
        self.monitor_thread.start()
        
        logger.info(f"System monitoring started with interval={interval}s")
    
    def stop_monitoring(self):
        """停止系统监控"""
        if not self.monitoring:
            return
        
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=10)
        
        logger.info("System monitoring stopped")
    
    def _monitor_loop(self):
        """监控循环"""
        while self.monitoring:
            try:
                self._collect_system_metrics()
                time.sleep(self.interval)
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
                time.sleep(1)  # 出错时短暂停顿
    
    def _collect_system_metrics(self):
        """收集系统指标"""
        try:
            # CPU使用率
            cpu_percent = psutil.cpu_percent(interval=1)
            self.collector.record_metric('system.cpu.percent', cpu_percent)
            
            # 内存使用率
            memory = psutil.virtual_memory()
            self.collector.record_metric('system.memory.percent', memory.percent)
            self.collector.record_metric('system.memory.available_mb', memory.available / 1024 / 1024)
            
            # 磁盘使用率
            disk = psutil.disk_usage('/')
            self.collector.record_metric('system.disk.percent', disk.percent)
            
            # 网络IO
            net_io = psutil.net_io_counters()
            self.collector.record_metric('system.network.bytes_sent', net_io.bytes_sent)
            self.collector.record_metric('system.network.bytes_recv', net_io.bytes_recv)
            
        except Exception as e:
            logger.error(f"Failed to collect system metrics: {e}")


class AlertThreshold:
    """告警阈值定义"""
    
    def __init__(
        self,
        metric_name: str,
        threshold_value: float,
        comparison: str = 'gt',  # gt, lt, eq, ge, le
        duration: float = 60.0,  # 持续时间（秒）
        tags: Dict[str, str] = None
    ):
        """
        初始化告警阈值
        
        Args:
            metric_name: 指标名称
            threshold_value: 阈值
            comparison: 比较操作符
            duration: 持续时间
            tags: 标签过滤
        """
        self.metric_name = metric_name
        self.threshold_value = threshold_value
        self.comparison = comparison
        self.duration = duration
        self.tags = tags or {}
        self.violation_start_time: Optional[float] = None
        self.active = False


class AlertManager:
    """告警管理器"""
    
    def __init__(self, collector: MetricsCollector):
        """
        初始化告警管理器
        
        Args:
            collector: 指标收集器实例
        """
        self.collector = collector
        self.thresholds: List[AlertThreshold] = []
        self.alerts: List[Dict[str, Any]] = []
        self.lock = threading.RLock()
        
        logger.info("AlertManager initialized")
    
    def add_threshold(self, threshold: AlertThreshold):
        """
        添加告警阈值
        
        Args:
            threshold: 告警阈值对象
        """
        with self.lock:
            self.thresholds.append(threshold)
            logger.info(f"Added alert threshold for {threshold.metric_name}")
    
    def check_thresholds(self):
        """检查所有阈值"""
        current_time = time.time()
        
        with self.lock:
            for threshold in self.thresholds:
                self._check_single_threshold(threshold, current_time)
    
    def _check_single_threshold(self, threshold: AlertThreshold, current_time: float):
        """检查单个阈值"""
        # 获取最新指标值
        stats = self.collector.get_metric_stats(threshold.metric_name)
        if not stats:
            return
        
        current_value = stats['latest']
        
        # 检查阈值条件
        condition_met = self._evaluate_condition(
            current_value, 
            threshold.threshold_value, 
            threshold.comparison
        )
        
        if condition_met:
            if not threshold.violation_start_time:
                threshold.violation_start_time = current_time
            
            # 检查持续时间
            if current_time - threshold.violation_start_time >= threshold.duration:
                if not threshold.active:
                    self._trigger_alert(threshold, current_value, current_time)
                    threshold.active = True
        else:
            # 条件不满足，重置状态
            threshold.violation_start_time = None
            if threshold.active:
                self._resolve_alert(threshold, current_time)
                threshold.active = False
    
    def _evaluate_condition(self, value: float, threshold: float, op: str) -> bool:
        """评估条件"""
        if op == 'gt':
            return value > threshold
        elif op == 'lt':
            return value < threshold
        elif op == 'eq':
            return value == threshold
        elif op == 'ge':
            return value >= threshold
        elif op == 'le':
            return value <= threshold
        else:
            return False
    
    def _trigger_alert(self, threshold: AlertThreshold, value: float, timestamp: float):
        """触发告警"""
        alert = {
            'type': 'threshold_violation',
            'metric_name': threshold.metric_name,
            'threshold_value': threshold.threshold_value,
            'current_value': value,
            'comparison': threshold.comparison,
            'timestamp': timestamp,
            'status': 'active'
        }
        
        self.alerts.append(alert)
        logger.warning(f"ALERT TRIGGERED: {threshold.metric_name} {threshold.comparison} {threshold.threshold_value}, current={value}")
    
    def _resolve_alert(self, threshold: AlertThreshold, timestamp: float):
        """解决告警"""
        # 找到对应的活跃告警并标记为已解决
        for alert in reversed(self.alerts):
            if (alert['metric_name'] == threshold.metric_name and 
                alert['status'] == 'active'):
                alert['status'] = 'resolved'
                alert['resolved_timestamp'] = timestamp
                logger.info(f"ALERT RESOLVED: {threshold.metric_name}")
                break


# 便捷函数和全局实例
_global_collector: Optional[MetricsCollector] = None
_global_monitor: Optional[SystemMonitor] = None
_global_alert_manager: Optional[AlertManager] = None


def get_metrics_collector() -> MetricsCollector:
    """获取全局指标收集器实例"""
    global _global_collector
    if _global_collector is None:
        _global_collector = MetricsCollector()
    return _global_collector


def get_system_monitor() -> SystemMonitor:
    """获取全局系统监控器实例"""
    global _global_monitor
    if _global_monitor is None:
        collector = get_metrics_collector()
        _global_monitor = SystemMonitor(collector)
    return _global_monitor


def get_alert_manager() -> AlertManager:
    """获取全局告警管理器实例"""
    global _global_alert_manager
    if _global_alert_manager is None:
        collector = get_metrics_collector()
        _global_alert_manager = AlertManager(collector)
    return _global_alert_manager


def setup_default_monitoring():
    """设置默认监控配置"""
    collector = get_metrics_collector()
    monitor = get_system_monitor()
    alert_manager = get_alert_manager()
    
    # 添加默认告警阈值
    alert_manager.add_threshold(
        AlertThreshold('system.cpu.percent', 80.0, 'gt', duration=60.0)
    )
    alert_manager.add_threshold(
        AlertThreshold('system.memory.percent', 85.0, 'gt', duration=120.0)
    )
    alert_manager.add_threshold(
        AlertThreshold('system.disk.percent', 90.0, 'gt', duration=300.0)
    )
    alert_manager.add_threshold(
        AlertThreshold('scrape.job.failure_rate', 0.3, 'gt', duration=120.0)
    )
    alert_manager.add_threshold(
        AlertThreshold('emby.webhook.event_latency_seconds', 60.0, 'gt', duration=120.0)
    )
    alert_manager.add_threshold(
        AlertThreshold('emby.delete.execute.warning', 0.0, 'gt', duration=1.0)
    )
    
    # 启动监控
    monitor.start_monitoring(interval=10.0)
    
    logger.info("Default monitoring setup completed")
