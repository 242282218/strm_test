"""
监控API端点

提供性能指标查询和系统状态监控接口
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any, List
from app.core.metrics_collector import (
    get_metrics_collector,
    get_system_monitor,
    get_alert_manager,
    MetricsCollector,
    SystemMonitor,
    AlertManager
)
from app.core.logging import get_logger
from app.core.dependencies import require_api_key

logger = get_logger(__name__)

router = APIRouter(prefix="/monitor", tags=["monitoring"])


@router.get("/metrics")
async def get_metrics(
    collector: MetricsCollector = Depends(get_metrics_collector)
) -> Dict[str, Any]:
    """
    获取所有指标的最新统计数据
    
    Returns:
        指标统计信息
    """
    try:
        metrics_stats = {}
        
        # 获取常见的系统指标
        system_metrics = [
            'system.cpu.percent',
            'system.memory.percent', 
            'system.memory.available_mb',
            'system.disk.percent',
            'system.network.bytes_sent',
            'system.network.bytes_recv'
        ]
        
        for metric_name in system_metrics:
            stats = collector.get_metric_stats(metric_name)
            if stats:
                metrics_stats[metric_name] = stats
        
        return {
            "status": "success",
            "data": metrics_stats,
            "timestamp": collector.get_metric_stats('system.cpu.percent').get('timestamp') if metrics_stats else None
        }
        
    except Exception as e:
        logger.error(f"Error getting metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve metrics")


@router.get("/metrics/{metric_name}")
async def get_metric_history(
    metric_name: str,
    limit: int = 100,
    collector: MetricsCollector = Depends(get_metrics_collector)
) -> Dict[str, Any]:
    """
    获取指定指标的历史数据
    
    Args:
        metric_name: 指标名称
        limit: 返回数据点数量限制
        
    Returns:
        指标历史数据
    """
    try:
        points = collector.get_recent_points(metric_name, limit)
        
        if not points:
            raise HTTPException(status_code=404, detail=f"Metric '{metric_name}' not found")
        
        # 转换为序列化格式
        history_data = [
            {
                "timestamp": point.timestamp,
                "value": point.value,
                "tags": point.tags
            }
            for point in points
        ]
        
        stats = collector.get_metric_stats(metric_name)
        
        return {
            "status": "success",
            "metric_name": metric_name,
            "stats": stats,
            "history": history_data,
            "count": len(history_data)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting metric history for {metric_name}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve metric history")


@router.get("/alerts")
async def get_active_alerts(
    alert_manager: AlertManager = Depends(get_alert_manager)
) -> Dict[str, Any]:
    """
    获取当前活跃的告警
    
    Returns:
        活跃告警列表
    """
    try:
        active_alerts = [
            alert for alert in alert_manager.alerts 
            if alert.get('status') == 'active'
        ]
        
        return {
            "status": "success",
            "active_alerts": active_alerts,
            "count": len(active_alerts),
            "total_alerts": len(alert_manager.alerts)
        }
        
    except Exception as e:
        logger.error(f"Error getting alerts: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve alerts")


@router.get("/system/status")
async def get_system_status(
    collector: MetricsCollector = Depends(get_metrics_collector)
) -> Dict[str, Any]:
    """
    获取系统整体状态
    
    Returns:
        系统状态信息
    """
    try:
        # 获取关键系统指标
        cpu_stats = collector.get_metric_stats('system.cpu.percent')
        memory_stats = collector.get_metric_stats('system.memory.percent')
        disk_stats = collector.get_metric_stats('system.disk.percent')
        
        # 确定系统健康状态
        health_status = "healthy"
        issues = []
        
        if cpu_stats and cpu_stats.get('latest', 0) > 80:
            health_status = "warning"
            issues.append(f"CPU usage high: {cpu_stats['latest']:.1f}%")
            
        if memory_stats and memory_stats.get('latest', 0) > 85:
            health_status = "warning" 
            issues.append(f"Memory usage high: {memory_stats['latest']:.1f}%")
            
        if disk_stats and disk_stats.get('latest', 0) > 90:
            health_status = "critical"
            issues.append(f"Disk usage critical: {disk_stats['latest']:.1f}%")
        
        return {
            "status": "success",
            "system_health": health_status,
            "issues": issues,
            "metrics": {
                "cpu_percent": cpu_stats.get('latest') if cpu_stats else None,
                "memory_percent": memory_stats.get('latest') if memory_stats else None,
                "disk_percent": disk_stats.get('latest') if disk_stats else None
            },
            "timestamp": cpu_stats.get('timestamp') if cpu_stats else None
        }
        
    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve system status")


@router.post("/monitoring/start")
async def start_monitoring(
    interval: float = 10.0,
    _auth: None = Depends(require_api_key),
    monitor: SystemMonitor = Depends(get_system_monitor)
) -> Dict[str, Any]:
    """
    启动系统监控
    
    Args:
        interval: 监控间隔（秒）
        
    Returns:
        操作结果
    """
    try:
        monitor.start_monitoring(interval)
        return {
            "status": "success",
            "message": f"Monitoring started with interval {interval}s"
        }
    except Exception as e:
        logger.error(f"Error starting monitoring: {e}")
        raise HTTPException(status_code=500, detail="Failed to start monitoring")


@router.post("/monitoring/stop")
async def stop_monitoring(
    _auth: None = Depends(require_api_key),
    monitor: SystemMonitor = Depends(get_system_monitor)
) -> Dict[str, Any]:
    """
    停止系统监控
    
    Returns:
        操作结果
    """
    try:
        monitor.stop_monitoring()
        return {
            "status": "success", 
            "message": "Monitoring stopped"
        }
    except Exception as e:
        logger.error(f"Error stopping monitoring: {e}")
        raise HTTPException(status_code=500, detail="Failed to stop monitoring")


@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """
    健康检查端点
    
    Returns:
        服务健康状态
    """
    return {
        "status": "healthy",
        "service": "monitoring-api",
        "timestamp": time.time()
    }


# 导入time模块用于健康检查
import time
