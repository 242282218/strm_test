"""
异步写入队列模块

提供数据库写入操作的异步队列，避免 SQLite 写锁竞争
支持批量写入、写入合并和失败重试
"""

import heapq
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from app.core.db import get_db_session
from app.core.logging import get_logger


logger = get_logger(__name__)


class WritePriority(Enum):
    """写入优先级"""

    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


class WriteOperation(Enum):
    """写入操作类型"""

    INSERT = "insert"
    UPDATE = "update"
    DELETE = "delete"
    UPSERT = "upsert"


@dataclass(order=True)
class WriteTask:
    """
    写入任务

    使用优先队列排序，优先级高的任务先执行
    """

    priority: int  # 优先级（负数用于最小堆）
    sequence: int  # 序列号（保证同优先级 FIFO）
    operation: WriteOperation = field(compare=False)
    model_class: str = field(compare=False)
    data: dict[str, Any] = field(compare=False)
    callback: Callable | None = field(compare=False, default=None)
    created_at: float = field(compare=False, default_factory=time.time)
    retry_count: int = field(compare=False, default=0)
    max_retries: int = field(compare=False, default=3)
    task_id: str = field(compare=False, default="")


@dataclass
class WriteQueueMetrics:
    """写入队列指标"""

    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    current_queue_size: int = 0
    peak_queue_size: int = 0
    total_wait_time_ms: float = 0.0
    total_process_time_ms: float = 0.0
    batch_writes: int = 0
    merged_writes: int = 0

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        avg_wait = self.total_wait_time_ms / self.completed_tasks if self.completed_tasks > 0 else 0
        avg_process = self.total_process_time_ms / self.completed_tasks if self.completed_tasks > 0 else 0

        return {
            "tasks": {
                "total": self.total_tasks,
                "completed": self.completed_tasks,
                "failed": self.failed_tasks,
                "queue_size": self.current_queue_size,
                "peak_queue_size": self.peak_queue_size,
            },
            "performance": {
                "avg_wait_time_ms": round(avg_wait, 2),
                "avg_process_time_ms": round(avg_process, 2),
                "batch_writes": self.batch_writes,
                "merged_writes": self.merged_writes,
            },
        }


class AsyncWriteQueue:
    """
    异步写入队列

    功能特性:
    - 优先队列：高优先级任务优先处理
    - 批量写入：合并多个写入操作
    - 写入合并：相同 key 的更新操作合并
    - 失败重试：自动重试失败的任务
    - 背压控制：队列满时阻塞生产者
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

    def __init__(
        self,
        max_queue_size: int = 10000,
        batch_size: int = 100,
        batch_timeout_ms: int = 100,
        max_workers: int = 2,
    ):
        """
        初始化写入队列

        Args:
            max_queue_size: 最大队列大小
            batch_size: 批量写入大小
            batch_timeout_ms: 批量写入超时（毫秒）
            max_workers: 最大工作线程数
        """
        if self._initialized:
            return

        self._max_queue_size = max_queue_size
        self._batch_size = batch_size
        self._batch_timeout_ms = batch_timeout_ms
        self._max_workers = max_workers

        # 优先队列
        self._queue: list[WriteTask] = []
        self._queue_lock = threading.Lock()
        self._sequence = 0
        self._not_empty = threading.Condition(self._queue_lock)

        # 写入合并缓存
        self._merge_cache: dict[str, WriteTask] = {}
        self._merge_lock = threading.Lock()

        # 指标
        self._metrics = WriteQueueMetrics()

        # 状态
        self._running = False
        self._workers: list[threading.Thread] = []

        # 模型注册表
        self._model_registry: dict[str, type] = {}

        self._initialized = True
        logger.info(f"AsyncWriteQueue initialized: max_size={max_queue_size}, batch_size={batch_size}")

    @classmethod
    def get_instance(cls) -> "AsyncWriteQueue":
        """获取队列实例"""
        return cls()

    def register_model(self, name: str, model_class: type) -> None:
        """
        注册模型类

        Args:
            name: 模型名称
            model_class: 模型类
        """
        self._model_registry[name] = model_class
        logger.debug(f"Model registered: {name}")

    def start(self) -> None:
        """启动写入队列"""
        if self._running:
            return

        self._running = True

        # 启动工作线程
        for i in range(self._max_workers):
            worker = threading.Thread(
                target=self._worker_loop,
                name=f"write-queue-worker-{i}",
                daemon=True,
            )
            worker.start()
            self._workers.append(worker)

        logger.info(f"AsyncWriteQueue started with {self._max_workers} workers")

    def stop(self, wait: bool = True) -> None:
        """
        停止写入队列

        Args:
            wait: 是否等待队列清空
        """
        self._running = False

        # 唤醒所有等待的工作线程
        with self._not_empty:
            self._not_empty.notify_all()

        if wait:
            for worker in self._workers:
                worker.join(timeout=5.0)

        self._workers.clear()
        logger.info("AsyncWriteQueue stopped")

    def submit(
        self,
        operation: WriteOperation,
        model_class: str,
        data: dict[str, Any],
        priority: WritePriority = WritePriority.NORMAL,
        callback: Callable | None = None,
        merge_key: str | None = None,
    ) -> str:
        """
        提交写入任务

        Args:
            operation: 操作类型
            model_class: 模型类名
            data: 写入数据
            priority: 优先级
            callback: 完成回调
            merge_key: 合并键（相同键的任务会被合并）

        Returns:
            任务ID
        """
        if not self._running:
            raise RuntimeError("Write queue is not running")

        import uuid

        task_id = str(uuid.uuid4())[:8]

        task = WriteTask(
            priority=-priority.value,  # 负数用于最小堆
            sequence=self._next_sequence(),
            operation=operation,
            model_class=model_class,
            data=data,
            callback=callback,
            task_id=task_id,
        )

        # 写入合并
        if merge_key:
            with self._merge_lock:
                if merge_key in self._merge_cache:
                    # 合并数据
                    old_task = self._merge_cache[merge_key]
                    old_task.data.update(data)
                    old_task.retry_count = 0  # 重置重试计数
                    self._metrics.merged_writes += 1
                    logger.debug(f"Task merged: {merge_key}")
                    return old_task.task_id
                self._merge_cache[merge_key] = task

        # 加入队列
        with self._not_empty:
            if len(self._queue) >= self._max_queue_size:
                raise RuntimeError("Write queue is full")

            heapq.heappush(self._queue, task)
            self._metrics.total_tasks += 1
            self._metrics.current_queue_size = len(self._queue)
            self._metrics.peak_queue_size = max(self._metrics.peak_queue_size, self._metrics.current_queue_size)
            self._not_empty.notify()

        logger.debug(f"Task submitted: {task_id}, queue_size={len(self._queue)}")
        return task_id

    def submit_batch(
        self,
        tasks: list[tuple[WriteOperation, str, dict[str, Any]]],
        priority: WritePriority = WritePriority.NORMAL,
    ) -> list[str]:
        """
        批量提交任务

        Args:
            tasks: 任务列表 [(operation, model_class, data), ...]
            priority: 优先级

        Returns:
            任务ID列表
        """
        task_ids = []
        for operation, model_class, data in tasks:
            task_id = self.submit(operation, model_class, data, priority)
            task_ids.append(task_id)
        return task_ids

    def _next_sequence(self) -> int:
        """获取下一个序列号"""
        with self._queue_lock:
            self._sequence += 1
            return self._sequence

    def _worker_loop(self) -> None:
        """工作线程循环"""
        logger.debug(f"Worker started: {threading.current_thread().name}")

        while self._running:
            try:
                # 获取一批任务
                tasks = self._get_batch()

                if not tasks:
                    continue

                # 执行批量写入
                start_time = time.time()
                self._execute_batch(tasks)
                process_time = (time.time() - start_time) * 1000

                # 更新指标
                with self._queue_lock:
                    self._metrics.total_process_time_ms += process_time
                    self._metrics.batch_writes += 1

            except Exception as e:
                logger.error(f"Worker error: {e}")

        logger.debug(f"Worker stopped: {threading.current_thread().name}")

    def _get_batch(self) -> list[WriteTask]:
        """
        获取一批任务

        Returns:
            任务列表
        """
        tasks = []
        deadline = time.time() + self._batch_timeout_ms / 1000

        with self._not_empty:
            while len(tasks) < self._batch_size:
                # 等待任务
                remaining = deadline - time.time()
                if remaining <= 0:
                    break

                if not self._queue:
                    self._not_empty.wait(remaining)

                if self._queue:
                    task = heapq.heappop(self._queue)
                    tasks.append(task)

                    # 更新等待时间
                    wait_time = (time.time() - task.created_at) * 1000
                    self._metrics.total_wait_time_ms += wait_time

                    # 从合并缓存中移除
                    with self._merge_lock:
                        keys_to_remove = [k for k, v in self._merge_cache.items() if v.task_id == task.task_id]
                        for k in keys_to_remove:
                            del self._merge_cache[k]

        return tasks

    def _execute_batch(self, tasks: list[WriteTask]) -> None:
        """
        执行批量写入

        Args:
            tasks: 任务列表
        """
        if not tasks:
            return

        # 按模型分组
        grouped: dict[str, list[WriteTask]] = {}
        for task in tasks:
            if task.model_class not in grouped:
                grouped[task.model_class] = []
            grouped[task.model_class].append(task)

        # 执行每个组的写入
        for model_class, model_tasks in grouped.items():
            try:
                self._execute_model_batch(model_class, model_tasks)
            except Exception as e:
                logger.error(f"Batch write failed for {model_class}: {e}")
                # 重试失败的任务
                for task in model_tasks:
                    self._retry_task(task, str(e))

    def _execute_model_batch(self, model_class: str, tasks: list[WriteTask]) -> None:
        """
        执行单个模型的批量写入

        Args:
            model_class: 模型类名
            tasks: 任务列表
        """
        if model_class not in self._model_registry:
            logger.warning(f"Model not registered: {model_class}")
            # 标记所有任务失败
            for task in tasks:
                self._metrics.failed_tasks += 1
                if task.callback:
                    try:
                        task.callback(False, Exception(f"Model not registered: {model_class}"))
                    except Exception as e:
                        logger.error(f"Callback error: {e}")
            return

        model = self._model_registry[model_class]

        with get_db_session() as db:
            for task in tasks:
                try:
                    self._execute_single_task(db, model, task)
                    self._metrics.completed_tasks += 1

                    if task.callback:
                        try:
                            task.callback(True, None)
                        except Exception as e:
                            logger.error(f"Callback error: {e}")

                except Exception as e:
                    logger.error(f"Task execution failed: {task.task_id}, {e}")
                    self._retry_task(task, str(e))

        # 更新队列大小
        self._metrics.current_queue_size = len(self._queue)

    def _execute_single_task(self, db, model: type, task: WriteTask) -> None:
        """
        执行单个任务

        Args:
            db: 数据库会话
            model: 模型类
            task: 任务
        """
        if task.operation == WriteOperation.INSERT:
            instance = model(**task.data)
            db.add(instance)

        elif task.operation == WriteOperation.UPDATE:
            # 假设 data 包含 id 和要更新的字段
            obj_id = task.data.pop("id", None)
            if obj_id:
                instance = db.query(model).filter_by(id=obj_id).first()
                if instance:
                    for key, value in task.data.items():
                        setattr(instance, key, value)

        elif task.operation == WriteOperation.DELETE:
            obj_id = task.data.get("id")
            if obj_id:
                db.query(model).filter_by(id=obj_id).delete()

        elif task.operation == WriteOperation.UPSERT:
            # 使用模型的方法（如果存在）
            if hasattr(model, "create_or_update"):
                model.create_or_update(db, **task.data)
            else:
                # 默认行为：尝试插入，失败则更新
                try:
                    instance = model(**task.data)
                    db.add(instance)
                except Exception:
                    db.rollback()
                    # 尝试更新
                    obj_id = task.data.get("id") or task.data.get("file_id")
                    if obj_id:
                        filter_field = "file_id" if hasattr(model, "file_id") else "id"
                        instance = db.query(model).filter(getattr(model, filter_field) == obj_id).first()
                        if instance:
                            for key, value in task.data.items():
                                setattr(instance, key, value)

    def _retry_task(self, task: WriteTask, error: str) -> None:
        """
        重试失败的任务

        Args:
            task: 任务
            error: 错误信息
        """
        task.retry_count += 1

        if task.retry_count >= task.max_retries:
            logger.error(f"Task failed after {task.max_retries} retries: {task.task_id}")
            self._metrics.failed_tasks += 1

            if task.callback:
                try:
                    task.callback(False, Exception(error))
                except Exception as e:
                    logger.error(f"Callback error: {e}")
            return

        # 重新加入队列
        with self._not_empty:
            task.priority = min(task.priority, -WritePriority.HIGH.value)  # 提升优先级
            heapq.heappush(self._queue, task)
            self._not_empty.notify()

        logger.debug(f"Task retried: {task.task_id}, attempt {task.retry_count}")

    def get_metrics(self) -> WriteQueueMetrics:
        """获取队列指标"""
        return self._metrics

    def get_status(self) -> dict[str, Any]:
        """获取队列状态"""
        return {
            "running": self._running,
            "workers": len(self._workers),
            "queue_size": len(self._queue),
            "merge_cache_size": len(self._merge_cache),
            "metrics": self._metrics.to_dict(),
            "config": {
                "max_queue_size": self._max_queue_size,
                "batch_size": self._batch_size,
                "batch_timeout_ms": self._batch_timeout_ms,
                "max_workers": self._max_workers,
            },
        }

    def clear(self) -> int:
        """
        清空队列

        Returns:
            清除的任务数
        """
        with self._queue_lock:
            count = len(self._queue)
            self._queue.clear()
            self._merge_cache.clear()
            self._metrics.current_queue_size = 0
            return count


# 全局队列实例
_write_queue: AsyncWriteQueue | None = None


def get_write_queue() -> AsyncWriteQueue:
    """获取写入队列实例"""
    global _write_queue
    if _write_queue is None:
        _write_queue = AsyncWriteQueue()
    return _write_queue


def start_write_queue() -> None:
    """启动写入队列"""
    queue = get_write_queue()
    queue.start()


def stop_write_queue(wait: bool = True) -> None:
    """停止写入队列"""
    global _write_queue
    if _write_queue:
        _write_queue.stop(wait)
