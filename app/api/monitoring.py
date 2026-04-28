"""
监控API端点

提供性能指标查询和系统状态监控接口
"""

import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.core.dependencies import require_api_key
from app.core.http_pool import get_http_pool
from app.core.logging import get_logger
from app.core.metrics_collector import (
    AlertManager,
    MetricsCollector,
    SystemMonitor,
    get_alert_manager,
    get_metrics_collector,
    get_system_monitor,
)


logger = get_logger(__name__)

router = APIRouter(prefix="/monitor", tags=["monitoring"])


@router.get("/metrics")
async def get_metrics(
    collector: MetricsCollector = Depends(get_metrics_collector), _auth: None = Depends(require_api_key)
) -> dict[str, Any]:
    """
    获取所有指标的最新统计数据

    Returns:
        指标统计信息
    """
    try:
        metrics_stats = {}

        # 获取常见的系统指标
        system_metrics = [
            "system.cpu.percent",
            "system.memory.percent",
            "system.memory.available_mb",
            "system.disk.percent",
            "system.network.bytes_sent",
            "system.network.bytes_recv",
        ]

        for metric_name in system_metrics:
            stats = collector.get_metric_stats(metric_name)
            if stats:
                metrics_stats[metric_name] = stats

        return {
            "status": "success",
            "data": metrics_stats,
            "timestamp": collector.get_metric_stats("system.cpu.percent").get("timestamp") if metrics_stats else None,
        }

    except Exception as e:
        logger.error(f"Error getting metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve metrics")


@router.get("/metrics/{metric_name}")
async def get_metric_history(
    metric_name: str, limit: int = 100, collector: MetricsCollector = Depends(get_metrics_collector)
) -> dict[str, Any]:
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
        history_data = [{"timestamp": point.timestamp, "value": point.value, "tags": point.tags} for point in points]

        stats = collector.get_metric_stats(metric_name)

        return {
            "status": "success",
            "metric_name": metric_name,
            "stats": stats,
            "history": history_data,
            "count": len(history_data),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting metric history for {metric_name}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve metric history")


@router.get("/alerts")
async def get_active_alerts(alert_manager: AlertManager = Depends(get_alert_manager)) -> dict[str, Any]:
    """
    获取当前活跃的告警

    Returns:
        活跃告警列表
    """
    try:
        active_alerts = [alert for alert in alert_manager.alerts if alert.get("status") == "active"]

        return {
            "status": "success",
            "active_alerts": active_alerts,
            "count": len(active_alerts),
            "total_alerts": len(alert_manager.alerts),
        }

    except Exception as e:
        logger.error(f"Error getting alerts: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve alerts")


@router.get("/system/status")
async def get_system_status(collector: MetricsCollector = Depends(get_metrics_collector)) -> dict[str, Any]:
    """
    获取系统整体状态

    Returns:
        系统状态信息
    """
    try:
        # 获取关键系统指标
        cpu_stats = collector.get_metric_stats("system.cpu.percent")
        memory_stats = collector.get_metric_stats("system.memory.percent")
        disk_stats = collector.get_metric_stats("system.disk.percent")

        # 确定系统健康状态
        health_status = "healthy"
        issues = []

        if cpu_stats and cpu_stats.get("latest", 0) > 80:
            health_status = "warning"
            issues.append(f"CPU usage high: {cpu_stats['latest']:.1f}%")

        if memory_stats and memory_stats.get("latest", 0) > 85:
            health_status = "warning"
            issues.append(f"Memory usage high: {memory_stats['latest']:.1f}%")

        if disk_stats and disk_stats.get("latest", 0) > 90:
            health_status = "critical"
            issues.append(f"Disk usage critical: {disk_stats['latest']:.1f}%")

        return {
            "status": "success",
            "system_health": health_status,
            "issues": issues,
            "metrics": {
                "cpu_percent": cpu_stats.get("latest") if cpu_stats else None,
                "memory_percent": memory_stats.get("latest") if memory_stats else None,
                "disk_percent": disk_stats.get("latest") if disk_stats else None,
            },
            "timestamp": cpu_stats.get("timestamp") if cpu_stats else None,
        }

    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve system status")


@router.post("/monitoring/start")
async def start_monitoring(
    interval: float = 10.0, monitor: SystemMonitor = Depends(get_system_monitor)
) -> dict[str, Any]:
    """
    启动系统监控

    Args:
        interval: 监控间隔（秒）

    Returns:
        操作结果
    """
    try:
        monitor.start_monitoring(interval)
        return {"status": "success", "message": f"Monitoring started with interval {interval}s"}
    except Exception as e:
        logger.error(f"Error starting monitoring: {e}")
        raise HTTPException(status_code=500, detail="Failed to start monitoring")


@router.post("/monitoring/stop")
async def stop_monitoring(monitor: SystemMonitor = Depends(get_system_monitor)) -> dict[str, Any]:
    """
    停止系统监控

    Returns:
        操作结果
    """
    try:
        monitor.stop_monitoring()
        return {"status": "success", "message": "Monitoring stopped"}
    except Exception as e:
        logger.error(f"Error stopping monitoring: {e}")
        raise HTTPException(status_code=500, detail="Failed to stop monitoring")


@router.get("/health")
async def health_check() -> dict[str, Any]:
    """
    健康检查端点

    Returns:
        服务健康状态
    """
    return {"status": "healthy", "service": "monitoring-api", "timestamp": time.time()}


# ============ HTTP 连接池监控端点 ============


@router.get("/http-pool/stats")
async def get_http_pool_stats() -> dict[str, Any]:
    """
    获取 HTTP 连接池统计信息

    Returns:
        连接池统计信息
    """
    try:
        pool = await get_http_pool()
        stats = pool.get_stats()

        return {"status": "success", "data": stats}
    except Exception as e:
        logger.error(f"Error getting HTTP pool stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve HTTP pool stats")


@router.get("/http-pool/health")
async def get_http_pool_health() -> dict[str, Any]:
    """
    获取 HTTP 连接池健康状态

    Returns:
        连接池健康状态
    """
    try:
        pool = await get_http_pool()
        health = pool.get_health_status()

        return {"status": "success", "data": health}
    except Exception as e:
        logger.error(f"Error getting HTTP pool health: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve HTTP pool health")


@router.post("/http-pool/reset/{client_type}")
async def reset_http_pool_client(client_type: str, _auth: None = Depends(require_api_key)) -> dict[str, Any]:
    """
    重置指定的 HTTP 客户端

    Args:
        client_type: 客户端类型 (quark, emby, tmdb, ai, general)

    Returns:
        操作结果
    """
    try:
        from app.core.http_pool import ClientType

        # 映射客户端类型
        type_map = {
            "quark": ClientType.QUARK,
            "emby": ClientType.EMBY,
            "tmdb": ClientType.TMDB,
            "ai": ClientType.AI_PROVIDER,
            "general": ClientType.GENERAL,
        }

        if client_type.lower() not in type_map:
            raise HTTPException(
                status_code=400, detail=f"Invalid client type: {client_type}. Valid types: {list(type_map.keys())}"
            )

        pool = await get_http_pool()
        await pool.reset_client(type_map[client_type.lower()])

        return {"status": "success", "message": f"HTTP client '{client_type}' has been reset"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resetting HTTP pool client: {e}")
        raise HTTPException(status_code=500, detail="Failed to reset HTTP pool client")


# ============ 数据库连接池监控端点 ============


@router.get("/db-pool/status")
async def get_db_pool_status(_auth: None = Depends(require_api_key)) -> dict[str, Any]:
    """
    获取数据库连接池状态

    Returns:
        连接池状态信息
    """
    try:
        from app.core.db import get_pool_status
        from app.core.db_monitor import get_pool_monitor

        # 获取基础状态
        pool_status = get_pool_status()

        # 获取监控指标
        monitor = get_pool_monitor()
        metrics = monitor.get_metrics()

        # 获取活跃连接
        active_connections = monitor.get_active_connections()

        return {
            "status": "success",
            "data": {
                "pool": pool_status,
                "metrics": metrics.to_dict(),
                "active_connections": active_connections,
                "active_count": len(active_connections),
            },
        }
    except Exception as e:
        logger.error(f"Error getting DB pool status: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve DB pool status")


@router.get("/db-pool/health")
async def get_db_pool_health() -> dict[str, Any]:
    """
    获取数据库连接池健康状态

    Returns:
        连接池健康状态
    """
    try:
        from app.core.db import check_pool_health
        from app.core.db_monitor import get_pool_monitor

        # 基础健康检查
        basic_health = check_pool_health()

        # 详细健康检查
        monitor = get_pool_monitor()
        detailed_health = monitor.check_health()

        return {
            "status": "success",
            "data": {
                "basic": basic_health,
                "detailed": detailed_health,
            },
        }
    except Exception as e:
        logger.error(f"Error getting DB pool health: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve DB pool health")


@router.get("/db-pool/metrics")
async def get_db_pool_metrics() -> dict[str, Any]:
    """
    获取数据库连接池性能指标

    Returns:
        性能指标数据
    """
    try:
        from app.core.db_monitor import get_pool_monitor

        monitor = get_pool_monitor()
        metrics = monitor.get_metrics()

        return {"status": "success", "data": metrics.to_dict()}
    except Exception as e:
        logger.error(f"Error getting DB pool metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve DB pool metrics")


@router.get("/db-pool/connections")
async def get_db_active_connections() -> dict[str, Any]:
    """
    获取当前活跃的数据库连接

    Returns:
        活跃连接列表
    """
    try:
        from app.core.db_monitor import get_pool_monitor

        monitor = get_pool_monitor()
        connections = monitor.get_active_connections()

        return {
            "status": "success",
            "data": {
                "connections": connections,
                "count": len(connections),
            },
        }
    except Exception as e:
        logger.error(f"Error getting active connections: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve active connections")


@router.get("/db-pool/history")
async def get_db_connection_history(limit: int = 100) -> dict[str, Any]:
    """
    获取数据库连接历史记录

    Args:
        limit: 返回记录数量限制

    Returns:
        连接历史记录
    """
    try:
        from app.core.db_monitor import get_pool_monitor

        monitor = get_pool_monitor()
        history = monitor._tracker.get_history(limit)

        return {
            "status": "success",
            "data": {
                "history": history,
                "count": len(history),
            },
        }
    except Exception as e:
        logger.error(f"Error getting connection history: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve connection history")


@router.post("/db-pool/reset-metrics")
async def reset_db_pool_metrics(_auth: None = Depends(require_api_key)) -> dict[str, Any]:
    """
    重置数据库连接池指标

    Returns:
        操作结果
    """
    try:
        from app.core.db_monitor import get_pool_monitor

        monitor = get_pool_monitor()
        monitor.reset_metrics()

        return {"status": "success", "message": "Database pool metrics have been reset"}
    except Exception as e:
        logger.error(f"Error resetting DB pool metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to reset DB pool metrics")


@router.put("/db-pool/thresholds")
async def set_db_pool_thresholds(thresholds: dict[str, Any], _auth: None = Depends(require_api_key)) -> dict[str, Any]:
    """
    设置数据库连接池告警阈值

    Args:
        thresholds: 阈值配置字典

    Returns:
        操作结果
    """
    try:
        from app.core.db_monitor import get_pool_monitor

        monitor = get_pool_monitor()
        updated = []

        for name, value in thresholds.items():
            try:
                monitor.set_threshold(name, value)
                updated.append(name)
            except ValueError as e:
                logger.warning(f"Invalid threshold {name}: {e}")

        return {
            "status": "success",
            "message": f"Updated thresholds: {updated}",
            "current_thresholds": monitor._thresholds,
        }
    except Exception as e:
        logger.error(f"Error setting DB pool thresholds: {e}")
        raise HTTPException(status_code=500, detail="Failed to set DB pool thresholds")


@router.get("/db-pool/config")
async def get_db_pool_config() -> dict[str, Any]:
    """
    获取数据库连接池配置

    Returns:
        连接池配置信息
    """
    try:
        from dataclasses import asdict

        from app.core.db import get_pool_config, get_pool_status

        config = get_pool_config()
        status = get_pool_status()

        return {
            "status": "success",
            "data": {
                "config": asdict(config),
                "pool_status": status,
            },
        }
    except Exception as e:
        logger.error(f"Error getting DB pool config: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve DB pool config")


# ============ 缓存监控仪表板端点 ============


@router.get("/cache/stats")
async def get_cache_stats() -> dict[str, Any]:
    """
    获取缓存全局统计信息

    Returns:
        缓存统计信息
    """
    try:
        from app.core.cache_manager import get_cache_manager

        manager = get_cache_manager()
        stats = manager.get_stats()

        return {"status": "success", "data": stats}
    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve cache stats")


@router.get("/cache/namespaces")
async def get_cache_namespaces() -> dict[str, Any]:
    """
    获取所有命名空间的统计信息

    Returns:
        命名空间统计信息
    """
    try:
        from app.core.cache_manager import CacheNamespace, get_cache_manager

        manager = get_cache_manager()

        namespaces = {}
        for namespace in CacheNamespace:
            ns_stats = manager.get_namespace_stats(namespace)
            ns_config = manager.get_namespace_config(namespace)
            namespaces[namespace.value] = {"stats": ns_stats, "config": ns_config}

        return {
            "status": "success",
            "data": {"namespaces": namespaces, "dependency_graph": manager.get_dependency_graph()},
        }
    except Exception as e:
        logger.error(f"Error getting cache namespaces: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve cache namespaces")


@router.get("/cache/namespace/{namespace_name}")
async def get_cache_namespace_stats(namespace_name: str) -> dict[str, Any]:
    """
    获取指定命名空间的统计信息

    Args:
        namespace_name: 命名空间名称

    Returns:
        命名空间统计信息
    """
    try:
        from app.core.cache_manager import CacheNamespace, get_cache_manager

        # 解析命名空间
        try:
            namespace = CacheNamespace(namespace_name.lower())
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid namespace: {namespace_name}. Valid namespaces: {[ns.value for ns in CacheNamespace]}",
            )

        manager = get_cache_manager()
        stats = manager.get_namespace_stats(namespace)
        config = manager.get_namespace_config(namespace)
        version = manager.get_namespace_version(namespace)

        return {
            "status": "success",
            "data": {"namespace": namespace.value, "stats": stats, "config": config, "version": version.to_dict()},
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting cache namespace stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve cache namespace stats")


@router.get("/cache/versions")
async def get_cache_versions() -> dict[str, Any]:
    """
    获取所有命名空间的版本信息

    Returns:
        版本信息
    """
    try:
        from app.core.cache_manager import get_cache_manager

        manager = get_cache_manager()
        versions = manager.get_all_versions()

        return {"status": "success", "data": {"versions": {k: v.to_dict() for k, v in versions.items()}}}
    except Exception as e:
        logger.error(f"Error getting cache versions: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve cache versions")


@router.get("/cache/invalidation-log")
async def get_cache_invalidation_log(limit: int = 20) -> dict[str, Any]:
    """
    获取缓存失效事件日志

    Args:
        limit: 返回记录数量限制

    Returns:
        失效事件日志
    """
    try:
        from app.core.cache_manager import get_cache_manager

        manager = get_cache_manager()
        log = manager.get_invalidation_log(limit)

        return {"status": "success", "data": {"log": log, "count": len(log)}}
    except Exception as e:
        logger.error(f"Error getting cache invalidation log: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve cache invalidation log")


@router.post("/cache/invalidate/{namespace_name}")
async def invalidate_cache_namespace(
    namespace_name: str, key: str = None, cascade: bool = True, _auth: None = Depends(require_api_key)
) -> dict[str, Any]:
    """
    失效指定命名空间的缓存

    Args:
        namespace_name: 命名空间名称
        key: 可选的特定键，不传则失效整个命名空间
        cascade: 是否级联失效关联命名空间

    Returns:
        失效结果
    """
    try:
        from app.core.cache_manager import CacheNamespace, get_cache_manager

        # 解析命名空间
        try:
            namespace = CacheNamespace(namespace_name.lower())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid namespace: {namespace_name}")

        manager = get_cache_manager()
        result = await manager.invalidate_related(namespace, key, cascade)

        return {"status": "success", "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error invalidating cache: {e}")
        raise HTTPException(status_code=500, detail="Failed to invalidate cache")


@router.post("/cache/increment-version/{namespace_name}")
async def increment_cache_version(
    namespace_name: str, cascade: bool = True, _auth: None = Depends(require_api_key)
) -> dict[str, Any]:
    """
    递增命名空间版本号

    Args:
        namespace_name: 命名空间名称
        cascade: 是否级联更新关联命名空间

    Returns:
        版本更新结果
    """
    try:
        from app.core.cache_manager import CacheNamespace, get_cache_manager

        # 解析命名空间
        try:
            namespace = CacheNamespace(namespace_name.lower())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid namespace: {namespace_name}")

        manager = get_cache_manager()
        result = await manager.increment_namespace_version(namespace, cascade)

        return {"status": "success", "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error incrementing cache version: {e}")
        raise HTTPException(status_code=500, detail="Failed to increment cache version")


@router.post("/cache/clear/{namespace_name}")
async def clear_cache_namespace(namespace_name: str, _auth: None = Depends(require_api_key)) -> dict[str, Any]:
    """
    清空指定命名空间的缓存

    Args:
        namespace_name: 命名空间名称

    Returns:
        操作结果
    """
    try:
        from app.core.cache_manager import CacheNamespace, get_cache_manager

        # 解析命名空间
        try:
            namespace = CacheNamespace(namespace_name.lower())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid namespace: {namespace_name}")

        manager = get_cache_manager()
        await manager.clear_namespace(namespace)

        return {"status": "success", "message": f"Namespace '{namespace_name}' has been cleared"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error clearing cache namespace: {e}")
        raise HTTPException(status_code=500, detail="Failed to clear cache namespace")


@router.post("/cache/clear-all")
async def clear_all_cache(_auth: None = Depends(require_api_key)) -> dict[str, Any]:
    """
    清空所有缓存

    Returns:
        操作结果
    """
    try:
        from app.core.cache_manager import get_cache_manager

        manager = get_cache_manager()
        await manager.clear_all()

        return {"status": "success", "message": "All cache has been cleared"}
    except Exception as e:
        logger.error(f"Error clearing all cache: {e}")
        raise HTTPException(status_code=500, detail="Failed to clear all cache")


@router.get("/cache/health")
async def get_cache_health() -> dict[str, Any]:
    """
    获取缓存健康状态

    Returns:
        缓存健康状态
    """
    try:
        from app.core.cache_manager import get_cache_manager

        manager = get_cache_manager()
        stats = manager.get_stats()

        # 计算健康状态
        health_status = "healthy"
        issues = []

        # 检查命中率
        total_requests = stats.get("total_requests", 0)
        if total_requests > 100:  # 至少有100次请求才检查命中率
            hit_rate_str = stats.get("hit_rate", "0%").replace("%", "")
            hit_rate = float(hit_rate_str)
            if hit_rate < 50:
                health_status = "warning"
                issues.append(f"Low cache hit rate: {hit_rate:.1f}%")

        # 检查各命名空间
        namespaces = stats.get("namespaces", {})
        for ns_name, ns_stats in namespaces.items():
            if ns_stats.get("size", 0) > ns_stats.get("max_size", 1000) * 0.9:
                if health_status == "healthy":
                    health_status = "warning"
                issues.append(f"Namespace '{ns_name}' is near capacity")

        return {
            "status": "success",
            "data": {
                "health": health_status,
                "issues": issues,
                "summary": {
                    "total_requests": total_requests,
                    "hit_rate": stats.get("hit_rate"),
                    "total_invalidations": stats.get("total_invalidations", 0),
                    "versioning_enabled": stats.get("config", {}).get("versioning_enabled", False),
                    "cross_namespace_invalidation_enabled": stats.get("config", {}).get(
                        "cross_namespace_invalidation_enabled", False
                    ),
                },
            },
        }
    except Exception as e:
        logger.error(f"Error getting cache health: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve cache health")


@router.get("/cache/dashboard")
async def get_cache_dashboard() -> dict[str, Any]:
    """
    获取缓存仪表板数据（聚合接口）

    Returns:
        仪表板数据
    """
    try:
        from app.core.cache_manager import CacheNamespace, get_cache_manager

        manager = get_cache_manager()
        stats = manager.get_stats()
        versions = manager.get_all_versions()
        dependency_graph = manager.get_dependency_graph()
        invalidation_log = manager.get_invalidation_log(10)

        # 计算各命名空间使用率
        namespace_usage = {}
        for namespace in CacheNamespace:
            ns_stats = manager.get_namespace_stats(namespace)
            if ns_stats:
                usage_percent = (ns_stats.get("size", 0) / ns_stats.get("max_size", 1)) * 100
                namespace_usage[namespace.value] = {
                    "size": ns_stats.get("size", 0),
                    "max_size": ns_stats.get("max_size", 0),
                    "usage_percent": round(usage_percent, 2),
                    "hits": ns_stats.get("hits", 0),
                    "misses": ns_stats.get("misses", 0),
                }

        return {
            "status": "success",
            "data": {
                "summary": {
                    "total_requests": stats.get("total_requests", 0),
                    "hit_rate": stats.get("hit_rate"),
                    "total_hits": stats.get("total_hits", 0),
                    "total_misses": stats.get("total_misses", 0),
                    "total_sets": stats.get("total_sets", 0),
                    "total_invalidations": stats.get("total_invalidations", 0),
                },
                "config": stats.get("config", {}),
                "namespace_usage": namespace_usage,
                "versions": {k: v.to_dict() for k, v in versions.items()},
                "dependency_graph": dependency_graph,
                "recent_invalidations": invalidation_log,
            },
        }
    except Exception as e:
        logger.error(f"Error getting cache dashboard: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve cache dashboard")
