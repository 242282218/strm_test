"""
仪表盘统计API

提供首页概览所需的聚合统计数据
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List
from app.core.database import Database, resolve_db_path
from app.core.logging import get_logger
from app.services.task_scheduler import TaskScheduler
from app.services.link_cache import LinkCache
from app.core.config_manager import get_config
from app.services.config_service import get_config_service

logger = get_logger(__name__)
router = APIRouter(prefix="/api/dashboard", tags=["仪表盘"])

# 全局实例
_db: Database = None
_task_scheduler: TaskScheduler = None
_link_cache: LinkCache = None
config = get_config()
config_service = get_config_service()


def get_db() -> Database:
    """获取数据库实例"""
    global _db
    if _db is None:
        _db = Database(resolve_db_path())
    return _db


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
async def get_dashboard_stats() -> Dict[str, Any]:
    """
    获取仪表盘统计数据

    Returns:
        包含各类统计信息的字典
    """
    try:
        db = get_db()

        # 1. STRM文件数量
        strm_files = db.get_all_strms()
        strm_count = len(strm_files)

        # 2. 任务统计
        scheduler = await get_task_scheduler()
        task_status = scheduler.get_status()
        task_count = task_status.get("task_count", 0)

        # 3. 缓存统计
        cache = await get_link_cache()
        cache_stats = cache.get_stats()
        cache_hit_rate = calculate_hit_rate(cache_stats)

        # 4. 最近任务（从任务调度器获取）
        recent_tasks = get_recent_tasks(scheduler)

        # 5. 服务状态
        services = get_services_status(task_status, cache_stats)

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
        logger.error(f"Failed to get dashboard stats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


def calculate_hit_rate(cache_stats: Dict[str, Any]) -> float:
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


def get_recent_tasks(scheduler: TaskScheduler) -> List[Dict[str, Any]]:
    """
    获取最近任务列表

    Args:
        scheduler: 任务调度器实例

    Returns:
        任务列表
    """
    try:
        tasks = scheduler.list_tasks()
        recent = []

        for task in tasks[:5]:  # 只取前5个
            recent.append({
                "name": task.get("name", "未命名任务"),
                "type": task.get("mode", "unknown"),
                "status": "running" if task.get("enabled") else "stopped",
                "progress": task.get("progress", 0),
                "time": task.get("last_run", "未执行"),
            })

        return recent

    except Exception as e:
        logger.error(f"Failed to get recent tasks: {str(e)}")
        return []


def get_services_status(task_status: Dict, cache_stats: Dict) -> List[Dict[str, str]]:
    """
    获取服务状态列表

    Args:
        task_status: 任务调度器状态
        cache_stats: 缓存统计

    Returns:
        服务状态列表
    """
    app_config = config_service.get_config()
    services = [
        {"name": "API服务", "status": "running"},
        {"name": "任务调度器", "status": "running" if task_status.get("running") else "stopped"},
        {"name": "缓存服务", "status": "running" if cache_stats.get("running") else "stopped"},
        {"name": "Emby代理", "status": "running" if config.get_quark_cookie() else "stopped"},
    ]
    return services


def calculate_file_types(strm_files: List[Dict]) -> Dict[str, int]:
    """
    计算文件类型分布

    Args:
        strm_files: STRM文件列表

    Returns:
        文件类型分布字典
    """
    type_count = {}

    for file in strm_files:
        filename = file.get("filename", "")
        if "." in filename:
            ext = filename.rsplit(".", 1)[1].lower()
        else:
            ext = "unknown"

        type_count[ext] = type_count.get(ext, 0) + 1

    # 如果没有数据，返回空字典
    return type_count


@router.get("/trends")
async def get_task_trends(days: int = 7) -> Dict[str, Any]:
    """
    获取任务执行趋势

    Args:
        days: 查询天数（默认7天）

    Returns:
        趋势数据
    """
    try:
        # 这里可以从数据库查询历史任务执行记录
        # 目前返回模拟的趋势数据结构
        scheduler = await get_task_scheduler()
        tasks = scheduler.list_tasks()

        # 生成日期标签
        from datetime import datetime, timedelta

        dates = []
        success_data = []
        failed_data = []

        for i in range(days - 1, -1, -1):
            date = datetime.now() - timedelta(days=i)
            dates.append(date.strftime("%m-%d"))
            # 模拟数据，实际应该从数据库查询
            success_data.append(len(tasks) * 2 + i)
            failed_data.append(max(0, len(tasks) - i))

        return {
            "status": "ok",
            "dates": dates,
            "success": success_data,
            "failed": failed_data,
        }

    except Exception as e:
        logger.error(f"Failed to get task trends: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
