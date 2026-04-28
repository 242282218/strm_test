from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services.platform.task_runner import TaskRunner


def test_ensure_orchestration_params_adds_defaults() -> None:
    task = SimpleNamespace(id=7, params={})

    orchestration = TaskRunner._ensure_orchestration_params(task)

    assert orchestration["planner"] == "planner"
    assert orchestration["router"] == "router"
    assert orchestration["worker"] == "worker"
    assert orchestration["reviewer"] == "reviewer"
    assert "trace_id" in orchestration
    assert task.params["orchestration"] is orchestration


def test_append_log_persists_log_entry() -> None:
    task = SimpleNamespace(logs=[])
    db = MagicMock()

    log_entry = TaskRunner._append_log(
        task,
        db,
        level="info",
        message="worker started",
        agent="worker",
        stage="execution",
        extra={"trace_id": "abc123"},
    )

    assert task.logs == [log_entry]
    assert log_entry["message"] == "worker started"
    assert log_entry["agent"] == "worker"
    assert log_entry["stage"] == "execution"
    assert log_entry["trace_id"] == "abc123"
    db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_check_cancelled_treats_cancel_requested_as_stop_signal() -> None:
    task = SimpleNamespace(status="cancel_requested")
    db = MagicMock()

    assert await TaskRunner._check_cancelled(db, task) is True
    db.refresh.assert_called_once_with(task)
