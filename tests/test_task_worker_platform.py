from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.models.task import Task
from app.services.platform.task_worker import PersistentTaskWorker


@pytest.fixture
def session_factory(tmp_path: Path):
    engine = create_engine(
        f"sqlite:///{(tmp_path / 'worker.db').as_posix()}",
        connect_args={"check_same_thread": False},
        poolclass=NullPool,
    )
    Task.__table__.create(bind=engine)
    Session = sessionmaker(bind=engine)
    try:
        yield Session
    finally:
        Task.__table__.drop(bind=engine)
        engine.dispose()


@pytest.mark.asyncio
async def test_persistent_worker_claims_and_runs_pending_task(session_factory) -> None:
    session = session_factory()
    task = Task(task_type="sync", status="pending", params={})
    session.add(task)
    session.commit()
    task_id = task.id
    session.close()
    ran: list[int] = []

    class FakeRunner:
        @staticmethod
        async def run_task(received_task_id: int) -> None:
            ran.append(received_task_id)
            run_session = session_factory()
            try:
                current = run_session.get(Task, received_task_id)
                current.status = "completed"
                current.progress = 100
                run_session.commit()
            finally:
                run_session.close()

    worker = PersistentTaskWorker(
        owner="worker-test",
        poll_interval_seconds=0.01,
        lease_seconds=2,
        session_factory=session_factory,
        runner=FakeRunner,
    )

    await worker.start()
    for _ in range(50):
        if ran:
            break
        await asyncio.sleep(0.01)
    await worker.stop()

    verify_session = session_factory()
    try:
        refreshed = verify_session.get(Task, task_id)
        assert ran == [task_id]
        assert refreshed.status == "completed"
        assert refreshed.lease_owner is None
        assert refreshed.lease_until is None
        assert refreshed.heartbeat_at is None
        assert refreshed.attempt == 1
    finally:
        verify_session.close()


@pytest.mark.asyncio
async def test_persistent_worker_schedules_retry_after_runner_failure(session_factory) -> None:
    session = session_factory()
    task = Task(task_type="sync", status="pending", params={}, max_attempts=2)
    session.add(task)
    session.commit()
    task_id = task.id
    session.close()
    ran: list[int] = []

    class FakeRunner:
        @staticmethod
        async def run_task(received_task_id: int) -> None:
            ran.append(received_task_id)
            run_session = session_factory()
            try:
                current = run_session.get(Task, received_task_id)
                current.status = "failed"
                current.error_message = "boom"
                run_session.commit()
            finally:
                run_session.close()

    worker = PersistentTaskWorker(
        owner="worker-test",
        poll_interval_seconds=0.01,
        lease_seconds=2,
        session_factory=session_factory,
        runner=FakeRunner,
    )

    await worker.start()
    for _ in range(50):
        if ran:
            break
        await asyncio.sleep(0.01)
    await worker.stop()

    verify_session = session_factory()
    try:
        refreshed = verify_session.get(Task, task_id)
        assert ran == [task_id]
        assert refreshed.status == "retry_scheduled"
        assert refreshed.next_run_at is not None
        assert refreshed.error_message == "boom"
        assert refreshed.lease_owner is None
        assert refreshed.attempt == 1
    finally:
        verify_session.close()
