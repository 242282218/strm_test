from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.core.db import Base
from app.models.task import Task
from app.schemas.task import TaskCreate
from app.services.platform.task_queue import TaskService


@pytest.fixture
def db_session(tmp_path):
    engine = create_engine(
        f"sqlite:///{(tmp_path / 'tasks.db').as_posix()}",
        connect_args={"check_same_thread": False},
        poolclass=NullPool,
    )
    Task.__table__.create(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_get_tasks_filters_by_status() -> None:
    db = MagicMock()
    query = db.query.return_value
    filtered = query.filter.return_value
    ordered = filtered.order_by.return_value
    offsetted = ordered.offset.return_value
    offsetted.limit.return_value.all.return_value = ["task-a"]

    service = TaskService(db)
    result = service.get_tasks(status="running")

    assert result == ["task-a"]
    query.filter.assert_called_once()


def test_cancel_task_marks_task_cancelled() -> None:
    db = MagicMock()
    task = SimpleNamespace(status="running", completed_at=None, error_message=None)
    service = TaskService(db)
    service.get_task = MagicMock(return_value=task)

    cancelled = service.cancel_task(12)

    assert cancelled is True
    assert task.status == "cancel_requested"
    assert task.error_message == "Cancel requested by user"
    db.commit.assert_called_once()


@pytest.mark.parametrize("status", ["completed", "partial_success", "failed", "cancelled"])
def test_cancel_task_rejects_terminal_states(status: str) -> None:
    db = MagicMock()
    task = SimpleNamespace(status=status, completed_at=None, error_message=None)
    service = TaskService(db)
    service.get_task = MagicMock(return_value=task)

    cancelled = service.cancel_task(12)

    assert cancelled is False
    db.commit.assert_not_called()


def test_cancel_task_cancels_pending_without_worker_roundtrip() -> None:
    db = MagicMock()
    task = SimpleNamespace(status="pending", completed_at=None, error_message=None)
    service = TaskService(db)
    service.get_task = MagicMock(return_value=task)

    cancelled = service.cancel_task(12)

    assert cancelled is True
    assert task.status == "cancelled"
    assert task.completed_at is not None
    db.commit.assert_called_once()


def test_delete_task_returns_false_when_missing() -> None:
    db = MagicMock()
    service = TaskService(db)
    service.get_task = MagicMock(return_value=None)

    deleted = service.delete_task(99)

    assert deleted is False
    db.delete.assert_not_called()


def test_claim_next_task_creates_exclusive_lease(db_session) -> None:
    now = datetime(2026, 4, 27, 10, 0, 0)
    service = TaskService(db_session)
    created = service.create_task(TaskCreate(task_type="sync", priority="normal", params={}))

    claimed = service.claim_next_task("worker-a", lease_seconds=60, now=now)
    duplicate = service.claim_next_task("worker-b", lease_seconds=60, now=now)

    assert claimed is not None
    assert claimed.id == created.id
    assert claimed.status == "leased"
    assert claimed.lease_owner == "worker-a"
    assert claimed.lease_until == now + timedelta(seconds=60)
    assert claimed.heartbeat_at == now
    assert claimed.attempt == 1
    assert duplicate is None


def test_claim_next_task_skips_future_retry(db_session) -> None:
    now = datetime(2026, 4, 27, 10, 0, 0)
    db_session.add(
        Task(
            task_type="sync",
            status="retry_scheduled",
            next_run_at=now + timedelta(minutes=5),
            params={},
        )
    )
    db_session.commit()

    claimed = TaskService(db_session).claim_next_task("worker-a", now=now)

    assert claimed is None


def test_heartbeat_task_extends_owned_lease(db_session) -> None:
    now = datetime(2026, 4, 27, 10, 0, 0)
    service = TaskService(db_session)
    created = service.create_task(TaskCreate(task_type="sync", priority="normal", params={}))
    claimed = service.claim_next_task("worker-a", lease_seconds=30, now=now)
    assert claimed is not None

    ok = service.heartbeat_task(created.id, "worker-a", lease_seconds=120, now=now + timedelta(seconds=10))
    wrong_owner = service.heartbeat_task(created.id, "worker-b", now=now + timedelta(seconds=20))
    refreshed = service.get_task(created.id)

    assert ok is True
    assert wrong_owner is False
    assert refreshed.heartbeat_at == now + timedelta(seconds=10)
    assert refreshed.lease_until == now + timedelta(seconds=130)


def test_recover_expired_leases_reschedules_fails_and_cancels(db_session) -> None:
    now = datetime(2026, 4, 27, 10, 0, 0)
    db_session.add_all(
        [
            Task(
                task_type="retry",
                status="running",
                lease_owner="worker-a",
                lease_until=now - timedelta(seconds=1),
                attempt=1,
                max_attempts=3,
                params={},
            ),
            Task(
                task_type="failed",
                status="running",
                lease_owner="worker-a",
                lease_until=now - timedelta(seconds=1),
                attempt=3,
                max_attempts=3,
                params={},
            ),
            Task(
                task_type="cancel",
                status="cancel_requested",
                lease_owner="worker-a",
                lease_until=now - timedelta(seconds=1),
                attempt=1,
                max_attempts=3,
                params={},
            ),
        ]
    )
    db_session.commit()

    recovered = TaskService(db_session).recover_expired_leases(now=now)
    statuses = {task.task_type: task.status for task in db_session.query(Task).all()}

    assert recovered == 3
    assert statuses == {
        "retry": "retry_scheduled",
        "failed": "failed",
        "cancel": "cancelled",
    }
    assert all(task.lease_owner is None for task in db_session.query(Task).all())


def test_record_task_failure_uses_persistent_retry_budget(db_session) -> None:
    now = datetime(2026, 4, 27, 10, 0, 0)
    task = Task(
        task_type="sync",
        status="running",
        lease_owner="worker-a",
        lease_until=now + timedelta(minutes=5),
        attempt=1,
        max_attempts=2,
        params={},
    )
    db_session.add(task)
    db_session.commit()

    ok = TaskService(db_session).record_task_failure(task.id, "worker-a", "boom", now=now, base_delay_seconds=10)
    refreshed = db_session.get(Task, task.id)

    assert ok is True
    assert refreshed.status == "retry_scheduled"
    assert refreshed.next_run_at == now + timedelta(seconds=10)
    assert refreshed.error_message == "boom"
    assert refreshed.lease_owner is None
