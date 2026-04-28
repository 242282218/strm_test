from __future__ import annotations

import asyncio
import os
import socket
import uuid
from collections.abc import Callable
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.core.logging import get_logger
from app.models.task import TASK_TERMINAL_STATES, Task
from app.services.platform.task_queue import TaskService
from app.services.platform.task_runner import TaskRunner


logger = get_logger(__name__)


class PersistentTaskWorker:
    def __init__(
        self,
        *,
        owner: str | None = None,
        poll_interval_seconds: float = 1.0,
        lease_seconds: int = 300,
        concurrency: int = 1,
        session_factory: Callable[[], Session] = SessionLocal,
        runner=TaskRunner,
        service_cls=TaskService,
    ) -> None:
        self.owner = owner or f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:8]}"
        self.poll_interval_seconds = poll_interval_seconds
        self.lease_seconds = lease_seconds
        self.concurrency = max(1, concurrency)
        self.session_factory = session_factory
        self.runner = runner
        self.service_cls = service_cls
        self._stop_event = asyncio.Event()
        self._loop_task: asyncio.Task | None = None
        self._active_tasks: set[asyncio.Task] = set()

    @property
    def running(self) -> bool:
        return self._loop_task is not None and not self._loop_task.done()

    async def start(self) -> None:
        if self.running:
            return
        self._stop_event.clear()
        recovered = self._recover_expired_leases()
        logger.info(f"Persistent task worker starting owner={self.owner} recovered={recovered}")
        self._loop_task = asyncio.create_task(self._run_loop(), name="persistent-task-worker")

    async def stop(self, timeout_seconds: float = 5.0) -> None:
        self._stop_event.set()
        if self._loop_task is not None:
            self._loop_task.cancel()
            try:
                await self._loop_task
            except asyncio.CancelledError:
                pass
            self._loop_task = None

        if self._active_tasks:
            _done, pending = await asyncio.wait(self._active_tasks, timeout=timeout_seconds)
            for task in pending:
                task.cancel()
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)
            self._active_tasks.clear()
        logger.info(f"Persistent task worker stopped owner={self.owner}")

    def _with_service(self) -> tuple[Session, TaskService]:
        session = self.session_factory()
        return session, self.service_cls(session)

    def _recover_expired_leases(self) -> int:
        session, service = self._with_service()
        try:
            return service.recover_expired_leases()
        finally:
            session.close()

    def _claim_next_task_id(self) -> int | None:
        session, service = self._with_service()
        try:
            task = service.claim_next_task(self.owner, lease_seconds=self.lease_seconds)
            return int(task.id) if task is not None else None
        finally:
            session.close()

    async def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            self._active_tasks = {task for task in self._active_tasks if not task.done()}
            if len(self._active_tasks) < self.concurrency:
                task_id = self._claim_next_task_id()
                if task_id is not None:
                    self._active_tasks.add(asyncio.create_task(self._run_claimed_task(task_id)))
                    continue
            await asyncio.sleep(self.poll_interval_seconds)

    async def _run_claimed_task(self, task_id: int) -> None:
        heartbeat_task = asyncio.create_task(self._heartbeat_loop(task_id))
        try:
            await self.runner.run_task(task_id)
        finally:
            heartbeat_task.cancel()
            await asyncio.gather(heartbeat_task, return_exceptions=True)
            self._clear_finished_lease(task_id)

    async def _heartbeat_loop(self, task_id: int) -> None:
        interval = max(1.0, self.lease_seconds / 3)
        while not self._stop_event.is_set():
            await asyncio.sleep(interval)
            session, service = self._with_service()
            try:
                service.heartbeat_task(task_id, self.owner, lease_seconds=self.lease_seconds)
            finally:
                session.close()

    def _clear_finished_lease(self, task_id: int) -> None:
        session = self.session_factory()
        try:
            task = session.get(Task, task_id)
            if not task or task.lease_owner != self.owner:
                return

            if task.status == "failed" and int(task.attempt or 0) < int(task.max_attempts or 1):
                retry_delay = min(30 * (2 ** max(int(task.attempt or 1) - 1, 0)), 3600)
                task.status = "retry_scheduled"
                task.next_run_at = datetime.now() + timedelta(seconds=retry_delay)
                task.lease_owner = None
                task.lease_until = None
                task.heartbeat_at = None
                session.commit()
                return

            if task.status in TASK_TERMINAL_STATES:
                task.lease_owner = None
                task.lease_until = None
                task.heartbeat_at = None
                session.commit()
        finally:
            session.close()
