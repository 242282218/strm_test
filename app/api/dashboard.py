"""
仪表盘统计API

提供首页概览所需的聚合统计数据
"""

from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlalchemy import or_

from app.core.config_manager import get_config
from app.core.db import get_db_session
from app.core.logging import get_logger
from app.models.strm_record import StrmRecord
from app.models.task import Task as PlatformTask
from app.services.config_service import get_config_service
from app.services.link_cache import LinkCache
from app.services.platform.task_scheduler import TaskScheduler


logger = get_logger(__name__)
router = APIRouter(prefix="/api/dashboard", tags=["仪表盘"])

# 全局实例
_task_scheduler: TaskScheduler = None
_link_cache: LinkCache = None
config = get_config()
config_service = get_config_service()

TASK_TYPE_LABELS = {
    "strm_generation": "生成 STRM",
    "file_sync": "文件同步",
    "scrape": "媒体刮削",
    "rename": "智能重命名",
}

SUCCESS_TASK_STATUSES = {"completed", "partial_success"}
FAILED_TASK_STATUSES = {"failed", "cancelled"}


def get_strm_files() -> list[dict[str, Any]]:
    with get_db_session() as session:
        return [record.to_dict() for record in StrmRecord.get_all(session)]


async def get_task_scheduler() -> TaskScheduler:
    """获取任务调度器实例（自动启动）"""
    global _task_scheduler
    if _task_scheduler is None:
        _task_scheduler = TaskScheduler()
        await _task_scheduler.start()
    return _task_scheduler


async def get_link_cache() -> LinkCache:
    """获取链接缓存实例（自动启动）"""
    global _link_cache
    if _link_cache is None:
        _link_cache = LinkCache()
        await _link_cache.start()
    return _link_cache


@router.get("/stats")
async def get_dashboard_stats() -> dict[str, Any]:
    """
    获取仪表盘统计数据

    Returns:
        包含各类统计信息的字典
    """
    try:
        # 1. STRM文件数量
        strm_files = get_strm_files()
        strm_count = len(strm_files)

        # 2. 任务统计
        scheduler = await get_task_scheduler()
        scheduler_status = scheduler.get_status()
        task_count = count_platform_tasks()

        # 3. 缓存统计
        cache = await get_link_cache()
        cache_stats = cache.get_stats()
        cache_hit_rate = calculate_hit_rate(cache_stats)

        # 4. 最近任务（从新任务平台获取）
        recent_tasks = get_recent_tasks(get_platform_tasks(limit=5))

        # 5. 服务状态
        services = get_services_status(scheduler_status, cache_stats)

        # 6. 文件类型分布
        file_type_distribution = calculate_file_types(strm_files)

        return {
            "status": "ok",
            "stats": {
                "strm_count": strm_count,
                "task_count": task_count,
                "cache_entries": cache_stats.get("valid_entries", 0),
                "cache_hit_rate": cache_hit_rate,
            },
            "recent_tasks": recent_tasks,
            "services": services,
            "cache_detail": {
                "size": cache_stats.get("valid_entries", 0),
                "hit_rate": cache_hit_rate,
                "ttl": cache_stats.get("default_ttl", 600),
            },
            "file_types": file_type_distribution,
        }

    except Exception as e:
        logger.error(f"Failed to get dashboard stats: {e!s}")
        raise HTTPException(status_code=500, detail="Failed to get dashboard stats")


def calculate_hit_rate(cache_stats: dict[str, Any]) -> float:
    """
    计算缓存命中率

    Args:
        cache_stats: 缓存统计信息

    Returns:
        命中率百分比
    """
    total_access = cache_stats.get("total_access_count", 0)
    if total_access == 0:
        return 0.0

    # 简化的命中率计算（实际应该记录命中次数）
    # 这里使用访问次数作为活跃度指标
    valid_entries = cache_stats.get("valid_entries", 0)
    total_entries = cache_stats.get("total_entries", 0)

    if total_entries == 0:
        return 0.0

    # 有效条目比例作为命中率近似值
    return round((valid_entries / total_entries) * 100, 1)


def count_platform_tasks() -> int:
    with get_db_session() as session:
        return session.query(PlatformTask).count()


def get_platform_tasks(limit: int | None = None, since: datetime | None = None) -> list[PlatformTask]:
    with get_db_session() as session:
        query = session.query(PlatformTask)
        if since is not None:
            query = query.filter(or_(PlatformTask.created_at >= since, PlatformTask.completed_at >= since))

        query = query.order_by(PlatformTask.created_at.desc(), PlatformTask.id.desc())
        if limit is not None:
            query = query.limit(limit)
        return query.all()


def summarize_task_target(task_type: str, params: dict[str, Any]) -> str | None:
    path_key_by_type = {
        "strm_generation": "source_dir",
        "file_sync": "remote_path",
        "scrape": "path",
        "rename": "path",
    }
    path_key = path_key_by_type.get(task_type)
    if not path_key:
        return None

    raw_value = params.get(path_key)
    if not isinstance(raw_value, str):
        return None

    target = raw_value.strip()
    if not target:
        return None

    if len(target) <= 28:
        return target

    return f"...{target[-25:]}"


def build_recent_task_name(task: Any) -> str:
    task_type = str(getattr(task, "task_type", "") or "")
    params = getattr(task, "params", {}) or {}
    task_label = TASK_TYPE_LABELS.get(task_type, task_type or "任务")
    task_target = summarize_task_target(task_type, params if isinstance(params, dict) else {})
    if not task_target:
        return task_label

    return f"{task_label} · {task_target}"


def get_recent_tasks(tasks: list[Any]) -> list[dict[str, Any]]:
    """
    获取最近任务列表

    Args:
        tasks: 任务列表

    Returns:
        任务列表
    """
    try:
        recent = []

        for task in tasks[:5]:  # 只取前5个
            task_time = (
                getattr(task, "completed_at", None)
                or getattr(task, "started_at", None)
                or getattr(task, "created_at", None)
            )
            recent.append(
                {
                    "name": build_recent_task_name(task),
                    "type": getattr(task, "task_type", "unknown"),
                    "status": getattr(task, "status", "pending"),
                    "progress": int(getattr(task, "progress", 0) or 0),
                    "time": task_time.isoformat() if hasattr(task_time, "isoformat") else "未开始",
                }
            )

        return recent

    except Exception as e:
        logger.error(f"Failed to get recent tasks: {e!s}")
        return []


def build_task_trends(tasks: list[Any], days: int) -> tuple[list[str], list[int], list[int]]:
    normalized_days = max(days, 1)
    dates: list[str] = []
    success_data: list[int] = []
    failed_data: list[int] = []
    today = datetime.now().date()
    start_day = today - timedelta(days=normalized_days - 1)
    success_counts: dict[Any, int] = {}
    failed_counts: dict[Any, int] = {}

    for task in tasks:
        status = str(getattr(task, "status", "") or "")
        if status not in SUCCESS_TASK_STATUSES and status not in FAILED_TASK_STATUSES:
            continue

        task_time = getattr(task, "completed_at", None) or getattr(task, "created_at", None)
        if not hasattr(task_time, "date"):
            continue

        task_day = task_time.date()
        if task_day < start_day or task_day > today:
            continue

        if status in SUCCESS_TASK_STATUSES:
            success_counts[task_day] = success_counts.get(task_day, 0) + 1
        else:
            failed_counts[task_day] = failed_counts.get(task_day, 0) + 1

    for i in range(normalized_days - 1, -1, -1):
        current_day = today - timedelta(days=i)
        dates.append(current_day.strftime("%m-%d"))
        success_data.append(success_counts.get(current_day, 0))
        failed_data.append(failed_counts.get(current_day, 0))

    return dates, success_data, failed_data


def get_services_status(task_status: dict, cache_stats: dict) -> list[dict[str, str]]:
    """
    获取服务状态列表

    Args:
        task_status: 任务调度器状态
        cache_stats: 缓存统计

    Returns:
        服务状态列表
    """
    services = [
        {"name": "API服务", "status": "running"},
        {"name": "任务调度器", "status": "running" if task_status.get("running") else "stopped"},
        {"name": "缓存服务", "status": "running" if cache_stats.get("running") else "stopped"},
        {"name": "Emby代理", "status": "running" if config.get_quark_cookie() else "stopped"},
    ]
    return services


def calculate_file_types(strm_files: list[dict]) -> dict[str, int]:
    """
    计算文件类型分布

    Args:
        strm_files: STRM文件列表

    Returns:
        文件类型分布字典
    """
    type_count = {}

    for file in strm_files:
        filename = file.get("filename") or file.get("file_name") or file.get("name") or ""
        if "." in filename:
            ext = filename.rsplit(".", 1)[1].lower()
        else:
            ext = "unknown"

        type_count[ext] = type_count.get(ext, 0) + 1

    # 如果没有数据，返回空字典
    return type_count


@router.get("/trends")
async def get_task_trends(days: int = 7) -> dict[str, Any]:
    """
    获取任务执行趋势

    Args:
        days: 查询天数（默认7天）

    Returns:
        趋势数据
    """
    try:
        normalized_days = max(days, 1)
        since = datetime.combine((datetime.now() - timedelta(days=normalized_days - 1)).date(), datetime.min.time())
        tasks = get_platform_tasks(since=since)
        dates, success_data, failed_data = build_task_trends(tasks, normalized_days)

        return {
            "status": "ok",
            "dates": dates,
            "success": success_data,
            "failed": failed_data,
        }

    except Exception as e:
        logger.error(f"Failed to get task trends: {e!s}")
        raise HTTPException(status_code=500, detail="Failed to get task trends")
