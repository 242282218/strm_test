"""
定时任务服务模块

提供定时任务调度功能:
- 基于APScheduler的任务调度
- 支持Cron表达式和间隔触发
- 任务队列管理
- 任务去重
- 任务状态跟踪

参考: QMediaSync synccron实现
"""

import asyncio
import os
import weakref
from collections.abc import Callable
from datetime import datetime
from typing import Any

from apscheduler.job import Job
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.core.logging import get_logger


logger = get_logger(__name__)


class TaskInfo:
    """任务信息"""

    def __init__(self, task_id: str, task_type: str, params: dict | None = None):
        self.task_id = task_id
        self.task_type = task_type
        self.params = params or {}
        self.created_at = datetime.now()
        self.started_at: datetime | None = None
        self.finished_at: datetime | None = None
        self.status = "pending"  # pending/running/success/failed
        self.result: Any | None = None
        self.error: str | None = None


class CronService:
    """
    定时任务服务

    参考: QMediaSync的InitCron和SyncProcessor实现
    """

    def __init__(self):
        """初始化定时任务服务"""
        self.scheduler = AsyncIOScheduler(
            timezone="Asia/Shanghai",
            job_defaults={
                "coalesce": True,  # 合并错过的执行
                "max_instances": 1,  # 同一任务最多1个实例
            },
        )

        # 任务队列
        self.task_queue: asyncio.Queue = asyncio.Queue()
        self._queue_loop: asyncio.AbstractEventLoop | None = None

        # 正在运行的任务
        self.running_tasks: dict[str, asyncio.Task] = {}

        # 任务历史记录
        self.task_history: list[TaskInfo] = []
        self.max_history = 100

        # Worker任务
        self._worker_task: asyncio.Task | None = None
        self._running = False

        # 任务处理器映射
        self._task_handlers: dict[str, Callable] = {}

        logger.info("CronService initialized")

    def register_handler(self, task_type: str, handler: Callable):
        """
        注册任务处理器

        Args:
            task_type: 任务类型
            handler: 处理函数(async)
        """
        self._task_handlers[task_type] = handler
        logger.info(f"Registered task handler: {task_type}")

    async def start(self):
        """启动定时任务服务"""
        if self._running:
            logger.warning("CronService is already running")
            return

        self._running = True

        # 绑定当前事件循环，避免跨事件循环使用队列
        self._ensure_queue()

        # 启动调度器
        self.scheduler.start()

        # 启动任务队列处理器
        self._worker_task = asyncio.create_task(self._process_queue())

        logger.info("CronService started")

    def _ensure_queue(self):
        current_loop = asyncio.get_running_loop()
        if self._queue_loop is not current_loop:
            if self._queue_loop is not None:
                logger.info("Task queue loop changed; reinitializing queue for current loop")
            self.task_queue = asyncio.Queue()
            self._queued_task_ids = set()
            self._queue_loop = current_loop

    async def stop(self):
        """停止定时任务服务"""
        if not self._running:
            logger.warning("CronService is not running")
            return

        self._running = False

        # 停止调度器
        self.scheduler.shutdown(wait=False)

        # 停止worker
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass

        # 取消所有运行中的任务
        for task_id, task in list(self.running_tasks.items()):
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        logger.info("CronService stopped")

    async def _process_queue(self):
        """
        任务队列处理器

        参考: QMediaSync的SyncProcessor.worker()
        """
        logger.info("Task queue processor started")

        while self._running:
            try:
                # 从队列获取任务
                task_info: TaskInfo = await asyncio.wait_for(self.task_queue.get(), timeout=1.0)

                # 检查是否已在运行(去重)
                if task_info.task_id in self.running_tasks:
                    logger.warning(f"Task {task_info.task_id} is already running, skipping")
                    self.task_queue.task_done()
                    continue

                # 创建任务
                task = asyncio.create_task(self._execute_task(task_info))
                self.running_tasks[task_info.task_id] = task

                # 等待完成
                try:
                    await task
                except Exception as e:
                    logger.error(f"Task {task_info.task_id} failed: {e}")
                finally:
                    # 清理
                    if task_info.task_id in self.running_tasks:
                        del self.running_tasks[task_info.task_id]
                    # BUG-006: 清理队列跟踪集合
                    if hasattr(self, "_queued_task_ids") and task_info.task_id in self._queued_task_ids:
                        self._queued_task_ids.discard(task_info.task_id)
                    self.task_queue.task_done()

            except TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Queue processor error: {e}")
                await asyncio.sleep(1)

        logger.info("Task queue processor stopped")

    async def _execute_task(self, task_info: TaskInfo):
        """
        执行任务

        Args:
            task_info: 任务信息
        """
        task_info.status = "running"
        task_info.started_at = datetime.now()

        logger.info(f"Executing task: {task_info.task_id} (type={task_info.task_type})")

        try:
            # 获取处理器
            handler = self._task_handlers.get(task_info.task_type)

            if handler is None:
                raise ValueError(f"No handler registered for task type: {task_info.task_type}")

            # 执行处理器
            if asyncio.iscoroutinefunction(handler):
                result = await handler(**task_info.params)
            else:
                result = handler(**task_info.params)

            task_info.status = "success"
            task_info.result = result

            logger.info(f"Task {task_info.task_id} completed successfully")

        except Exception as e:
            task_info.status = "failed"
            task_info.error = str(e)
            logger.error(f"Task {task_info.task_id} failed: {e}")
            raise

        finally:
            task_info.finished_at = datetime.now()

            # 添加到历史记录
            self.task_history.append(task_info)

            # 限制历史记录大小
            if len(self.task_history) > self.max_history:
                self.task_history = self.task_history[-self.max_history :]

    async def add_task(self, task_type: str, task_id: str | None = None, **params) -> str:
        """
        添加任务到队列

        参考: QMediaSync的AddTask方法

        BUG-006: 修复任务去重逻辑

        Args:
            task_type: 任务类型
            task_id: 任务ID(可选,默认自动生成)
            **params: 任务参数

        Returns:
            任务ID
        """
        if task_id is None:
            task_id = f"{task_type}_{datetime.now().timestamp()}"

        # 检查是否已在运行或已在队列中
        if task_id in self.running_tasks:
            logger.warning(f"Task {task_id} is already running, skipping")
            return task_id

        # 检查队列中是否已有相同task_id的任务
        # 注意: asyncio.Queue没有直接检查方法，这里通过额外集合跟踪
        if hasattr(self, "_queued_task_ids") and task_id in self._queued_task_ids:
            logger.warning(f"Task {task_id} is already in queue, skipping")
            return task_id

        # 初始化队列跟踪集合
        if not hasattr(self, "_queued_task_ids"):
            self._queued_task_ids = set()

        task_info = TaskInfo(task_id=task_id, task_type=task_type, params=params)

        self._queued_task_ids.add(task_id)
        await self.task_queue.put(task_info)

        logger.info(f"Task added to queue: {task_id} (type={task_type})")

        return task_id

    def stop_task(self, task_id: str) -> bool:
        """
        停止指定任务

        Args:
            task_id: 任务ID

        Returns:
            是否成功停止
        """
        if task_id in self.running_tasks:
            self.running_tasks[task_id].cancel()
            logger.info(f"Task {task_id} stopped")
            return True

        logger.warning(f"Task {task_id} not found in running tasks")
        return False

    def add_cron_job(self, job_id: str, cron_expression: str, task_type: str, **params) -> Job:
        """
        添加Cron定时任务

        BUG-004: 支持6字段Cron表达式(带秒)

        Args:
            job_id: 任务ID
            cron_expression: Cron表达式 (5字段或6字段)
            task_type: 任务类型
            **params: 任务参数

        Returns:
            APScheduler Job对象
        """
        # 检测字段数量
        fields = cron_expression.split()
        if len(fields) == 6:
            # 6字段格式: 秒 分 时 日 月 周
            # APScheduler的from_crontab不支持6字段，需要手动解析
            trigger = CronTrigger(
                second=fields[0],
                minute=fields[1],
                hour=fields[2],
                day=fields[3],
                month=fields[4],
                day_of_week=fields[5],
            )
        elif len(fields) == 5:
            # 5字段标准格式
            trigger = CronTrigger.from_crontab(cron_expression)
        else:
            raise ValueError(f"Invalid cron expression: {cron_expression}. Expected 5 or 6 fields.")

        job = self.scheduler.add_job(
            func=self._schedule_task, trigger=trigger, id=job_id, args=[task_type], kwargs=params, replace_existing=True
        )

        logger.info(f"Cron job added: {job_id} (cron={cron_expression}, type={task_type})")

        return job

    def add_interval_job(
        self,
        job_id: str,
        seconds: int | None = None,
        minutes: int | None = None,
        hours: int | None = None,
        task_type: str = None,
        **params,
    ) -> Job:
        """
        添加间隔定时任务

        BUG-005: 修复IntervalTrigger传递None的问题

        Args:
            job_id: 任务ID
            seconds: 秒间隔
            minutes: 分钟间隔
            hours: 小时间隔
            task_type: 任务类型
            **params: 任务参数

        Returns:
            APScheduler Job对象
        """
        # 构建trigger参数，过滤None值
        trigger_kwargs = {}
        if seconds is not None:
            trigger_kwargs["seconds"] = seconds
        if minutes is not None:
            trigger_kwargs["minutes"] = minutes
        if hours is not None:
            trigger_kwargs["hours"] = hours

        # 确保至少有一个时间参数
        if not trigger_kwargs:
            raise ValueError("At least one of seconds, minutes, or hours must be specified")

        trigger = IntervalTrigger(**trigger_kwargs)

        job = self.scheduler.add_job(
            func=self._schedule_task, trigger=trigger, id=job_id, args=[task_type], kwargs=params, replace_existing=True
        )

        logger.info(f"Interval job added: {job_id} (interval={seconds}s/{minutes}m/{hours}h, type={task_type})")

        return job

    def add_date_job(self, job_id: str, run_date: datetime, task_type: str, **params) -> Job:
        """
        添加一次性定时任务

        Args:
            job_id: 任务ID
            run_date: 执行时间
            task_type: 任务类型
            **params: 任务参数

        Returns:
            APScheduler Job对象
        """
        trigger = DateTrigger(run_date=run_date)

        job = self.scheduler.add_job(
            func=self._schedule_task, trigger=trigger, id=job_id, args=[task_type], kwargs=params, replace_existing=True
        )

        logger.info(f"Date job added: {job_id} (run_date={run_date}, type={task_type})")

        return job

    async def _schedule_task(self, task_type: str, **params):
        """
        调度任务(由APScheduler调用)

        Args:
            task_type: 任务类型
            **params: 任务参数
        """
        await self.add_task(task_type, **params)

    def remove_job(self, job_id: str) -> bool:
        """
        移除定时任务

        Args:
            job_id: 任务ID

        Returns:
            是否成功移除
        """
        try:
            self.scheduler.remove_job(job_id)
            logger.info(f"Job removed: {job_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to remove job {job_id}: {e}")
            return False

    def get_job(self, job_id: str) -> Job | None:
        """
        获取定时任务

        Args:
            job_id: 任务ID

        Returns:
            APScheduler Job对象
        """
        return self.scheduler.get_job(job_id)

    def get_jobs(self) -> list[Job]:
        """
        获取所有定时任务

        Returns:
            任务列表
        """
        return self.scheduler.get_jobs()

    def get_task_history(self, task_type: str | None = None, limit: int = 50) -> list[TaskInfo]:
        """
        获取任务历史记录

        Args:
            task_type: 任务类型(可选)
            limit: 最大返回数量

        Returns:
            任务信息列表
        """
        history = self.task_history

        if task_type:
            history = [task for task in history if task.task_type == task_type]

        return history[-limit:]

    def get_stats(self) -> dict[str, Any]:
        """
        获取统计信息

        Returns:
            统计信息字典
        """
        jobs = self.get_jobs()

        return {
            "running": self._running,
            "scheduled_jobs": len(jobs),
            "running_tasks": len(self.running_tasks),
            "queue_size": self.task_queue.qsize(),
            "history_size": len(self.task_history),
            "jobs": [
                {
                    "id": job.id,
                    "name": job.name,
                    "next_run_time": (job.next_run_time.isoformat() if job.next_run_time else None),
                }
                for job in jobs
            ],
        }


# 全局定时任务服务实例
_global_cron_service: CronService | None = None
_test_cron_services: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, CronService]" = weakref.WeakKeyDictionary()


def _is_test_env() -> bool:
    return os.getenv("PYTEST_CURRENT_TEST") is not None


def get_cron_service() -> CronService:
    """获取全局定时任务服务实例"""
    global _global_cron_service

    if _is_test_env():
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return CronService()
        service = _test_cron_services.get(loop)
        if service is None:
            service = CronService()
            _test_cron_services[loop] = service
        return service

    if _global_cron_service is None:
        _global_cron_service = CronService()

    return _global_cron_service
