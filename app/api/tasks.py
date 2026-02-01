"""
定时任务API路由

参考: alist-strm task_scheduler.py
"""

from fastapi import APIRouter, HTTPException
from app.services.task_scheduler import TaskScheduler, TaskMode
from app.core.logging import get_logger
from typing import Optional

logger = get_logger(__name__)
router = APIRouter(prefix="/api/tasks", tags=["定时任务"])


# 全局调度器实例
_scheduler: Optional[TaskScheduler] = None


def get_scheduler() -> TaskScheduler:
    """获取调度器实例"""
    global _scheduler
    if _scheduler is None:
        _scheduler = TaskScheduler()
    return _scheduler


@router.get("/")
async def list_tasks():
    """
    列出所有任务

    Returns:
        任务列表
    """
    try:
        scheduler = get_scheduler()
        return scheduler.get_status()
    except Exception as e:
        logger.error(f"Failed to list tasks: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/")
async def create_task(
    name: str,
    mode: str,
    interval_type: str,
    interval_value: int,
    config_id: str,
    enabled: bool = True
):
    """
    创建任务

    Args:
        name: 任务名称
        mode: 任务模式（strm_creation/strm_validation_quick/strm_validation_slow）
        interval_type: 间隔类型（minute/hourly/daily/weekly/monthly）
        interval_value: 间隔值
        config_id: 配置ID
        enabled: 是否启用

    Returns:
        创建的任务
    """
    try:
        # 验证任务模式
        try:
            task_mode = TaskMode(mode)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid task mode: {mode}")

        # 验证间隔类型
        valid_interval_types = ["minute", "hourly", "daily", "weekly", "monthly"]
        if interval_type not in valid_interval_types:
            raise HTTPException(status_code=400, detail=f"Invalid interval type: {interval_type}")

        # 验证间隔值
        if interval_value <= 0:
            raise HTTPException(status_code=400, detail="Interval value must be positive")

        scheduler = get_scheduler()
        task = scheduler.add_task(
            name=name,
            mode=task_mode,
            interval_type=interval_type,
            interval_value=interval_value,
            config_id=config_id,
            enabled=enabled
        )

        return task.to_dict()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create task: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{task_id}")
async def update_task(
    task_id: str,
    name: Optional[str] = None,
    interval_type: Optional[str] = None,
    interval_value: Optional[int] = None,
    enabled: Optional[bool] = None
):
    """
    更新任务

    Args:
        task_id: 任务ID
        name: 任务名称
        interval_type: 间隔类型
        interval_value: 间隔值
        enabled: 是否启用

    Returns:
        更新结果
    """
    try:
        # 验证间隔类型
        if interval_type is not None:
            valid_interval_types = ["minute", "hourly", "daily", "weekly", "monthly"]
            if interval_type not in valid_interval_types:
                raise HTTPException(status_code=400, detail=f"Invalid interval type: {interval_type}")

        # 验证间隔值
        if interval_value is not None and interval_value <= 0:
            raise HTTPException(status_code=400, detail="Interval value must be positive")

        scheduler = get_scheduler()
        success = scheduler.update_task(
            task_id=task_id,
            name=name,
            interval_type=interval_type,
            interval_value=interval_value,
            enabled=enabled
        )

        if not success:
            raise HTTPException(status_code=404, detail="Task not found")

        task = scheduler.get_task(task_id)
        return task.to_dict()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update task: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{task_id}")
async def delete_task(task_id: str):
    """
    删除任务

    Args:
        task_id: 任务ID

    Returns:
        删除结果
    """
    try:
        scheduler = get_scheduler()
        success = scheduler.delete_task(task_id)

        if not success:
            raise HTTPException(status_code=404, detail="Task not found")

        return {"status": "ok", "message": "Task deleted"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete task: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{task_id}/run")
async def run_task_immediately(task_id: str):
    """
    立即运行任务

    Args:
        task_id: 任务ID

    Returns:
        运行结果
    """
    try:
        scheduler = get_scheduler()
        success = await scheduler.run_task_immediately(task_id)

        if not success:
            raise HTTPException(status_code=404, detail="Task not found or handler not registered")

        return {"status": "ok", "message": "Task started"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to run task: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/start")
async def start_scheduler():
    """
    启动调度器

    Returns:
        启动结果
    """
    try:
        scheduler = get_scheduler()
        await scheduler.start()
        return {"status": "ok", "message": "Scheduler started"}

    except Exception as e:
        logger.error(f"Failed to start scheduler: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stop")
async def stop_scheduler():
    """
    停止调度器

    Returns:
        停止结果
    """
    try:
        scheduler = get_scheduler()
        await scheduler.stop()
        return {"status": "ok", "message": "Scheduler stopped"}

    except Exception as e:
        logger.error(f"Failed to stop scheduler: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))