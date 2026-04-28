import asyncio

import pytest

from app.services.platform.task_scheduler import TaskMode, TaskScheduler, TaskStatus


def test_add_task_registers_task_in_scheduler() -> None:
    scheduler = TaskScheduler()

    task = scheduler.add_task(
        name="nightly-strm",
        mode=TaskMode.STRM_CREATION,
        interval_type="minute",
        interval_value=5,
        config_id="default",
    )

    assert scheduler.get_task(task.task_id) is task
    assert task.status is TaskStatus.PENDING
    assert task.next_run is not None


@pytest.mark.asyncio
async def test_run_task_immediately_executes_registered_handler() -> None:
    scheduler = TaskScheduler()
    task = scheduler.add_task(
        name="validate",
        mode=TaskMode.STRM_VALIDATION_QUICK,
        interval_type="minute",
        interval_value=1,
        config_id="default",
    )
    called_with: list[str] = []

    async def handler(received_task):
        called_with.append(received_task.task_id)

    scheduler.register_handler(TaskMode.STRM_VALIDATION_QUICK, handler)

    ran = await scheduler.run_task_immediately(task.task_id)

    assert ran is True
    assert called_with == [task.task_id]
    assert task.status is TaskStatus.COMPLETED


@pytest.mark.asyncio
async def test_stop_marks_scheduler_and_tasks_stopped() -> None:
    scheduler = TaskScheduler()
    task = scheduler.add_task(
        name="scheduled-job",
        mode=TaskMode.STRM_CREATION,
        interval_type="minute",
        interval_value=1,
        config_id="cfg",
    )

    await scheduler.start()
    await asyncio.sleep(0)
    await scheduler.stop()

    assert scheduler.get_status()["running"] is False
    assert task.status is TaskStatus.STOPPED


@pytest.mark.asyncio
async def test_run_task_immediately_without_handler_returns_false() -> None:
    scheduler = TaskScheduler()
    task = scheduler.add_task(
        name="orphan",
        mode=TaskMode.STRM_VALIDATION_SLOW,
        interval_type="minute",
        interval_value=1,
        config_id="cfg",
    )

    ran = await scheduler.run_task_immediately(task.task_id)

    assert ran is False
