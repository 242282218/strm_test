"""
Prometheus 指标定义模块

定义符合 Prometheus 最佳实践的标准指标：
- 请求计数 (REQUEST_COUNT)
- 请求延迟 (REQUEST_LATENCY)
- STRM 生成统计 (STRM_GENERATED)
- 刮削任务统计 (SCRAPE_JOBS)
- 活跃连接数 (ACTIVE_CONNECTIONS)
- 缓存命中统计 (CACHE_HITS)

命名规范：
- 使用 snake_case
- 添加应用前缀 quark_strm_
- 包含单位后缀 (_seconds, _bytes, _total)
"""

import time
from collections.abc import Callable
from functools import wraps

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, Info

from app.core.logging import get_logger


logger = get_logger(__name__)

# 创建独立的注册表，避免与默认注册表冲突
REGISTRY = CollectorRegistry()

# ============================================================
# HTTP 请求指标
# ============================================================

REQUEST_COUNT = Counter(
    "quark_strm_http_requests_total",
    "Total count of HTTP requests",
    ["method", "endpoint", "status"],
    registry=REGISTRY,
)

REQUEST_LATENCY = Histogram(
    "quark_strm_http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0, 30.0, 60.0),
    registry=REGISTRY,
)

REQUEST_IN_PROGRESS = Gauge(
    "quark_strm_http_requests_in_progress",
    "Number of HTTP requests currently in progress",
    ["method", "endpoint"],
    registry=REGISTRY,
)

# ============================================================
# 业务指标 - STRM 生成
# ============================================================

STRM_GENERATED = Counter(
    "quark_strm_generated_total", "Total number of STRM files generated", ["status", "drive_type"], registry=REGISTRY
)

STRM_GENERATION_ERRORS = Counter(
    "quark_strm_generation_errors_total",
    "Total number of STRM generation errors",
    ["error_type", "drive_type"],
    registry=REGISTRY,
)

STRM_GENERATION_DURATION = Histogram(
    "quark_strm_generation_duration_seconds",
    "Duration of STRM file generation",
    ["drive_type"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
    registry=REGISTRY,
)

# ============================================================
# 业务指标 - 刮削任务
# ============================================================

SCRAPE_JOBS_TOTAL = Counter(
    "quark_strm_scrape_jobs_total", "Total number of scrape jobs", ["status", "source"], registry=REGISTRY
)

SCRAPE_JOBS_DURATION = Histogram(
    "quark_strm_scrape_job_duration_seconds",
    "Duration of scrape jobs",
    ["source"],
    buckets=(1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, 600.0),
    registry=REGISTRY,
)

SCRAPE_JOBS_IN_PROGRESS = Gauge(
    "quark_strm_scrape_jobs_in_progress", "Number of scrape jobs currently in progress", ["source"], registry=REGISTRY
)

SCRAPE_ITEMS_PROCESSED = Counter(
    "quark_strm_scrape_items_processed_total",
    "Total number of items processed during scraping",
    ["source", "status"],
    registry=REGISTRY,
)

# ============================================================
# 连接池指标
# ============================================================

ACTIVE_CONNECTIONS = Gauge(
    "quark_strm_active_connections", "Number of active connections", ["pool_type", "client_type"], registry=REGISTRY
)

CONNECTION_POOL_SIZE = Gauge(
    "quark_strm_connection_pool_size", "Size of connection pools", ["pool_type", "client_type"], registry=REGISTRY
)

CONNECTION_ERRORS = Counter(
    "quark_strm_connection_errors_total",
    "Total number of connection errors",
    ["pool_type", "client_type", "error_type"],
    registry=REGISTRY,
)

# ============================================================
# 缓存指标
# ============================================================

CACHE_HITS = Counter("quark_strm_cache_hits_total", "Total number of cache hits", ["cache_type"], registry=REGISTRY)

CACHE_MISSES = Counter(
    "quark_strm_cache_misses_total", "Total number of cache misses", ["cache_type"], registry=REGISTRY
)

CACHE_SIZE = Gauge("quark_strm_cache_size_bytes", "Current cache size in bytes", ["cache_type"], registry=REGISTRY)

CACHE_ITEMS = Gauge("quark_strm_cache_items", "Number of items in cache", ["cache_type"], registry=REGISTRY)

CACHE_EVICTIONS = Counter(
    "quark_strm_cache_evictions_total", "Total number of cache evictions", ["cache_type", "reason"], registry=REGISTRY
)

# ============================================================
# 数据库连接池指标
# ============================================================

DB_POOL_SIZE = Gauge("quark_strm_db_pool_size", "Size of database connection pool", registry=REGISTRY)

DB_POOL_OVERFLOW = Gauge(
    "quark_strm_db_pool_overflow", "Number of overflow connections in database pool", registry=REGISTRY
)

DB_POOL_CHECKED_OUT = Gauge(
    "quark_strm_db_pool_checked_out", "Number of checked out database connections", registry=REGISTRY
)

DB_POOL_CHECKED_IN = Counter(
    "quark_strm_db_pool_checkedin_total", "Total number of database connections checked in", registry=REGISTRY
)

DB_QUERY_DURATION = Histogram(
    "quark_strm_db_query_duration_seconds",
    "Duration of database queries",
    ["operation"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
    registry=REGISTRY,
)

# ============================================================
# 系统指标
# ============================================================

SYSTEM_CPU_PERCENT = Gauge("quark_strm_system_cpu_percent", "System CPU usage percentage", registry=REGISTRY)

SYSTEM_MEMORY_PERCENT = Gauge("quark_strm_system_memory_percent", "System memory usage percentage", registry=REGISTRY)

SYSTEM_MEMORY_AVAILABLE = Gauge(
    "quark_strm_system_memory_available_bytes", "System available memory in bytes", registry=REGISTRY
)

SYSTEM_DISK_PERCENT = Gauge("quark_strm_system_disk_percent", "System disk usage percentage", registry=REGISTRY)

# ============================================================
# 应用信息
# ============================================================

APP_INFO = Info("quark_strm_app", "Application information", registry=REGISTRY)

# 设置应用信息
APP_INFO.info({"version": "0.1.0", "service": "quark_strm"})

# ============================================================
# 辅助函数
# ============================================================


def track_request(method: str, endpoint: str, status: int, duration: float):
    """
    记录 HTTP 请求指标

    Args:
        method: HTTP 方法
        endpoint: 端点路径
        status: HTTP 状态码
        duration: 请求持续时间（秒）
    """
    try:
        REQUEST_COUNT.labels(method=method, endpoint=endpoint, status=str(status)).inc()
        REQUEST_LATENCY.labels(method=method, endpoint=endpoint).observe(duration)
    except Exception as e:
        logger.error(f"Failed to track request metrics: {e}")


def track_strm_generation(status: str, drive_type: str, duration: float | None = None):
    """
    记录 STRM 生成指标

    Args:
        status: 生成状态 (success, failed)
        drive_type: 驱动类型 (quark, aliyun, etc.)
        duration: 生成持续时间（秒）
    """
    try:
        STRM_GENERATED.labels(status=status, drive_type=drive_type).inc()
        if duration is not None:
            STRM_GENERATION_DURATION.labels(drive_type=drive_type).observe(duration)
    except Exception as e:
        logger.error(f"Failed to track STRM generation metrics: {e}")


def track_scrape_job(status: str, source: str, duration: float | None = None, items_count: int = 0):
    """
    记录刮削任务指标

    Args:
        status: 任务状态 (success, failed)
        source: 数据源 (tmdb, douban, etc.)
        duration: 任务持续时间（秒）
        items_count: 处理的项目数量
    """
    try:
        SCRAPE_JOBS_TOTAL.labels(status=status, source=source).inc()
        if duration is not None:
            SCRAPE_JOBS_DURATION.labels(source=source).observe(duration)
        if items_count > 0:
            SCRAPE_ITEMS_PROCESSED.labels(source=source, status=status).inc(items_count)
    except Exception as e:
        logger.error(f"Failed to track scrape job metrics: {e}")


def track_cache_operation(cache_type: str, hit: bool):
    """
    记录缓存操作指标

    Args:
        cache_type: 缓存类型 (link, metadata, etc.)
        hit: 是否命中
    """
    try:
        if hit:
            CACHE_HITS.labels(cache_type=cache_type).inc()
        else:
            CACHE_MISSES.labels(cache_type=cache_type).inc()
    except Exception as e:
        logger.error(f"Failed to track cache metrics: {e}")


def update_connection_pool_metrics(pool_type: str, client_type: str, active: int, pool_size: int):
    """
    更新连接池指标

    Args:
        pool_type: 池类型 (http, db)
        client_type: 客户端类型
        active: 活跃连接数
        pool_size: 池大小
    """
    try:
        ACTIVE_CONNECTIONS.labels(pool_type=pool_type, client_type=client_type).set(active)
        CONNECTION_POOL_SIZE.labels(pool_type=pool_type, client_type=client_type).set(pool_size)
    except Exception as e:
        logger.error(f"Failed to update connection pool metrics: {e}")


def update_cache_size(cache_type: str, size_bytes: int, items: int):
    """
    更新缓存大小指标

    Args:
        cache_type: 缓存类型
        size_bytes: 缓存大小（字节）
        items: 缓存项目数
    """
    try:
        CACHE_SIZE.labels(cache_type=cache_type).set(size_bytes)
        CACHE_ITEMS.labels(cache_type=cache_type).set(items)
    except Exception as e:
        logger.error(f"Failed to update cache size metrics: {e}")


def update_system_metrics(cpu_percent: float, memory_percent: float, memory_available: int, disk_percent: float):
    """
    更新系统指标

    Args:
        cpu_percent: CPU 使用率
        memory_percent: 内存使用率
        memory_available: 可用内存（字节）
        disk_percent: 磁盘使用率
    """
    try:
        SYSTEM_CPU_PERCENT.set(cpu_percent)
        SYSTEM_MEMORY_PERCENT.set(memory_percent)
        SYSTEM_MEMORY_AVAILABLE.set(memory_available)
        SYSTEM_DISK_PERCENT.set(disk_percent)
    except Exception as e:
        logger.error(f"Failed to update system metrics: {e}")


def update_db_pool_metrics(size: int, overflow: int, checked_out: int):
    """
    更新数据库连接池指标

    Args:
        size: 池大小
        overflow: 溢出连接数
        checked_out: 已检出连接数
    """
    try:
        DB_POOL_SIZE.set(size)
        DB_POOL_OVERFLOW.set(overflow)
        DB_POOL_CHECKED_OUT.set(checked_out)
    except Exception as e:
        logger.error(f"Failed to update DB pool metrics: {e}")


def track_db_query(operation: str, duration: float):
    """
    记录数据库查询指标

    Args:
        operation: 操作类型 (select, insert, update, delete)
        duration: 查询持续时间（秒）
    """
    try:
        DB_QUERY_DURATION.labels(operation=operation).observe(duration)
    except Exception as e:
        logger.error(f"Failed to track DB query metrics: {e}")


# ============================================================
# 装饰器
# ============================================================


def prometheus_track(endpoint: str):
    """
    Prometheus 追踪装饰器

    用于自动追踪函数执行时间和结果

    Args:
        endpoint: 端点名称
    """

    def decorator(func: Callable):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time
                track_request(method="INTERNAL", endpoint=endpoint, status=200, duration=duration)
                return result
            except Exception:
                duration = time.time() - start_time
                track_request(method="INTERNAL", endpoint=endpoint, status=500, duration=duration)
                raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                track_request(method="INTERNAL", endpoint=endpoint, status=200, duration=duration)
                return result
            except Exception:
                duration = time.time() - start_time
                track_request(method="INTERNAL", endpoint=endpoint, status=500, duration=duration)
                raise

        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


# ============================================================
# 导出
# ============================================================

__all__ = [
    # 注册表
    "REGISTRY",
    # HTTP 指标
    "REQUEST_COUNT",
    "REQUEST_LATENCY",
    "REQUEST_IN_PROGRESS",
    # STRM 指标
    "STRM_GENERATED",
    "STRM_GENERATION_ERRORS",
    "STRM_GENERATION_DURATION",
    # 刮削指标
    "SCRAPE_JOBS_TOTAL",
    "SCRAPE_JOBS_DURATION",
    "SCRAPE_JOBS_IN_PROGRESS",
    "SCRAPE_ITEMS_PROCESSED",
    # 连接池指标
    "ACTIVE_CONNECTIONS",
    "CONNECTION_POOL_SIZE",
    "CONNECTION_ERRORS",
    # 缓存指标
    "CACHE_HITS",
    "CACHE_MISSES",
    "CACHE_SIZE",
    "CACHE_ITEMS",
    "CACHE_EVICTIONS",
    # 数据库指标
    "DB_POOL_SIZE",
    "DB_POOL_OVERFLOW",
    "DB_POOL_CHECKED_OUT",
    "DB_POOL_CHECKED_IN",
    "DB_QUERY_DURATION",
    # 系统指标
    "SYSTEM_CPU_PERCENT",
    "SYSTEM_MEMORY_PERCENT",
    "SYSTEM_MEMORY_AVAILABLE",
    "SYSTEM_DISK_PERCENT",
    # 应用信息
    "APP_INFO",
    # 辅助函数
    "track_request",
    "track_strm_generation",
    "track_scrape_job",
    "track_cache_operation",
    "update_connection_pool_metrics",
    "update_cache_size",
    "update_system_metrics",
    "update_db_pool_metrics",
    "track_db_query",
    # 装饰器
    "prometheus_track",
]
