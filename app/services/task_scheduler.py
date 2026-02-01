"""
定时任务调度模块

参考: alist-strm task_scheduler.py
"""

import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any
from enum import Enum
from app.core.logging import get_logger

logger = get_logger(__name__)


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"


class TaskMode(Enum):
    """任务模式"""
    STRM_CREATION = "strm_creation"
    STRM_VALIDATION_QUICK = "strm_validation_quick"
    STRM_VALIDATION_SLOW = "strm_validation_slow"


class Task:
    """定时任务"""

    def __init__(
        self,
        task_id: str,
        name: str,
        mode: TaskMode,
        interval_type: str,
        interval_value: int,
        config_id: str,
        enabled: bool = True
    ):
        """
        初始化任务

        Args:
            task_id: 任务ID
            name: 任务名称
            mode: 任务模式
            interval_type: 间隔类型（minute/hourly/daily/weekly/monthly）
            interval_value: 间隔值
            config_id: 配置ID
            enabled: 是否启用
        """
        self.task_id = task_id
        self.name = name
        self.mode = mode
        self.interval_type = interval_type
        self.interval_value = interval_value
        self.config_id = config_id
        self.enabled = enabled
        self.status = TaskStatus.PENDING
        self.last_run: Optional[datetime] = None
        self.next_run: Optional[datetime] = None
        self.error_message: Optional[str] = None
        self._task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()

        # 计算下次运行时间
        self._calculate_next_run()

        logger.info(f"Task created: {self.task_id} ({self.name})")

    def _calculate_next_run(self):
        """计算下次运行时间"""
        now = datetime.now()

        if self.interval_type == "minute":
            self.next_run = now + timedelta(minutes=self.interval_value)
        elif self.interval_type == "hourly":
            self.next_run = now.replace(minute=0, second=0, microsecond=0)
            self.next_run += timedelta(hours=self.interval_value)
        elif self.interval_type == "daily":
            self.next_run = now.replace(hour=0, minute=0, second=0, microsecond=0)
            self.next_run += timedelta(days=self.interval_value)
        elif self.interval_type == "weekly":
            self.next_run = now.replace(hour=0, minute=0, second=0, microsecond=0)
            days_ahead = (self.interval_value - now.weekday()) % 7
            self.next_run += timedelta(days=days_ahead)
        elif self.interval_type == "monthly":
            self.next_run = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            self.next_run += timedelta(days=32 * self.interval_value)
            self.next_run = self.next_run.replace(day=1)
        else:
            logger.warning(f"Unknown interval type: {self.interval_type}")
            self.next_run = None

    def should_run(self) -> bool:
        """检查是否应该运行"""
        if not self.enabled or self.next_run is None:
            return False
        return datetime.now() >= self.next_run

    async def run(self, handler: Callable):
        """
        运行任务

        Args:
            handler: 任务处理函数
        """
        if self.status == TaskStatus.RUNNING:
            logger.warning(f"Task {self.task_id} is already running")
            return

        self.status = TaskStatus.RUNNING
        self.last_run = datetime.now()
        self.error_message = None

        logger.info(f"Task {self.task_id} started")

        try:
            await handler(self)
            self.status = TaskStatus.COMPLETED
            logger.info(f"Task {self.task_id} completed successfully")
        except Exception as e:
            self.status = TaskStatus.FAILED
            self.error_message = str(e)
            logger.error(f"Task {self.task_id} failed: {str(e)}")
        finally:
            # 计算下次运行时间
            self._calculate_next_run()

    def stop(self):
        """停止任务"""
        self._stop_event.set()
        self.enabled = False
        self.status = TaskStatus.STOPPED
        logger.info(f"Task {self.task_id} stopped")

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "task_id": self.task_id,
            "name": self.name,
            "mode": self.mode.value,
            "interval_type": self.interval_type,
            "interval_value": self.interval_value,
            "config_id": self.config_id,
            "enabled": self.enabled,
            "status": self.status.value,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "next_run": self.next_run.isoformat() if self.next_run else None,
            "error_message": self.error_message
        }


class TaskScheduler:
    """定时任务调度器"""

    def __init__(self):
        """初始化任务调度器"""
        self.tasks: Dict[str, Task] = {}
        self._running = False
        self._scheduler_task: Optional[asyncio.Task] = None
        self._handlers: Dict[TaskMode, Callable] = {}
        logger.info("TaskScheduler initialized")

    def register_handler(self, mode: TaskMode, handler: Callable):
        """
        注册任务处理函数

        Args:
            mode: 任务模式
            handler: 处理函数
        """
        self._handlers[mode] = handler
        logger.info(f"Handler registered for mode: {mode.value}")

    def add_task(
        self,
        name: str,
        mode: TaskMode,
        interval_type: str,
        interval_value: int,
        config_id: str,
        enabled: bool = True
    ) -> Task:
        """
        添加任务

        Args:
            name: 任务名称
            mode: 任务模式
            interval_type: 间隔类型
            interval_value: 间隔值
            config_id: 配置ID
            enabled: 是否启用

        Returns:
            任务对象
        """
        task_id = str(uuid.uuid4())
        task = Task(
            task_id=task_id,
            name=name,
            mode=mode,
            interval_type=interval_type,
            interval_value=interval_value,
            config_id=config_id,
            enabled=enabled
        )
        self.tasks[task_id] = task
        logger.info(f"Task added: {task_id}")
        return task

    def update_task(
        self,
        task_id: str,
        name: Optional[str] = None,
        interval_type: Optional[str] = None,
        interval_value: Optional[int] = None,
        enabled: Optional[bool] = None
    ) -> bool:
        """
        更新任务

        Args:
            task_id: 任务ID
            name: 任务名称
            interval_type: 间隔类型
            interval_value: 间隔值
            enabled: 是否启用

        Returns:
            是否更新成功
        """
        task = self.tasks.get(task_id)
        if not task:
            logger.error(f"Task not found: {task_id}")
            return False

        if name is not None:
            task.name = name
        if interval_type is not None:
            task.interval_type = interval_type
        if interval_value is not None:
            task.interval_value = interval_value
        if enabled is not None:
            task.enabled = enabled

        # 重新计算下次运行时间
        task._calculate_next_run()

        logger.info(f"Task updated: {task_id}")
        return True

    def delete_task(self, task_id: str) -> bool:
        """
        删除任务

        Args:
            task_id: 任务ID

        Returns:
            是否删除成功
        """
        if task_id in self.tasks:
            self.tasks[task_id].stop()
            del self.tasks[task_id]
            logger.info(f"Task deleted: {task_id}")
            return True
        logger.error(f"Task not found: {task_id}")
        return False

    def get_task(self, task_id: str) -> Optional[Task]:
        """
        获取任务

        Args:
            task_id: 任务ID

        Returns:
            任务对象
        """
        return self.tasks.get(task_id)

    def list_tasks(self) -> List[Dict[str, Any]]:
        """
        列出所有任务

        Returns:
            任务列表
        """
        return [task.to_dict() for task in self.tasks.values()]

    async def run_task_immediately(self, task_id: str) -> bool:
        """
        立即运行任务

        Args:
            task_id: 任务ID

        Returns:
            是否运行成功
        """
        task = self.tasks.get(task_id)
        if not task:
            logger.error(f"Task not found: {task_id}")
            return False

        handler = self._handlers.get(task.mode)
        if not handler:
            logger.error(f"Handler not found for mode: {task.mode.value}")
            return False

        await task.run(handler)
        return True

    async def _scheduler_loop(self):
        """调度器循环"""
        logger.info("Scheduler loop started")
        while self._running:
            for task in self.tasks.values():
                if task.should_run():
                    handler = self._handlers.get(task.mode)
                    if handler:
                        asyncio.create_task(task.run(handler))

            # 每分钟检查一次
            await asyncio.sleep(60)

    async def start(self):
        """启动调度器"""
        if self._running:
            logger.warning("Scheduler is already running")
            return

        self._running = True
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())
        logger.info("TaskScheduler started")

    async def stop(self):
        """停止调度器"""
        if not self._running:
            logger.warning("Scheduler is not running")
            return

        self._running = False

        # 停止所有任务
        for task in self.tasks.values():
            task.stop()

        # 停止调度器
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass

        logger.info("TaskScheduler stopped")

    def get_status(self) -> Dict[str, Any]:
        """
        获取调度器状态

        Returns:
            状态字典
        """
        return {
            "running": self._running,
            "task_count": len(self.tasks),
            "tasks": self.list_tasks()
        }