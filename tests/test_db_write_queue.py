from __future__ import annotations

import heapq
from dataclasses import dataclass
from typing import Any

import pytest

from app.core import db_write_queue


@pytest.fixture(autouse=True)
def reset_write_queue_singletons() -> None:
    db_write_queue.AsyncWriteQueue._instance = None
    db_write_queue._write_queue = None
    yield
    db_write_queue.AsyncWriteQueue._instance = None
    db_write_queue._write_queue = None


class DummyModel:
    def __init__(self, **kwargs: Any) -> None:
        if kwargs.get("raise_on_init"):
            raise RuntimeError("init failed")
        for key, value in kwargs.items():
            setattr(self, key, value)


class DummyModelWithUpsert:
    calls: list[dict[str, Any]] = []

    @classmethod
    def create_or_update(cls, _db: Any, **kwargs: Any) -> None:
        cls.calls.append(kwargs)


class FieldExpr:
    def __init__(self, name: str) -> None:
        self.name = name

    def __eq__(self, other: object) -> tuple[str, str, Any]:
        return ("eq", self.name, other)


class DummyUpsertFallbackModel:
    file_id = FieldExpr("file_id")

    def __init__(self, **_kwargs: Any) -> None:
        raise RuntimeError("insert fail")


@dataclass
class DummyRecord:
    id: int | None = None
    file_id: str | None = None
    name: str = ""


class FakeQuery:
    def __init__(self, records: list[DummyRecord]) -> None:
        self.records = records
        self._filter_by: dict[str, Any] = {}
        self.deleted = 0
        self._filter_expr: tuple[str, str, Any] | None = None

    def filter_by(self, **kwargs: Any) -> FakeQuery:
        self._filter_by = kwargs
        return self

    def first(self) -> DummyRecord | None:
        if self._filter_expr:
            _, field_name, value = self._filter_expr
            for record in self.records:
                if getattr(record, field_name) == value:
                    return record
            return None

        for record in self.records:
            if all(getattr(record, k) == v for k, v in self._filter_by.items()):
                return record
        return None

    def delete(self) -> int:
        before = len(self.records)
        self.records[:] = [
            record for record in self.records if not all(getattr(record, k) == v for k, v in self._filter_by.items())
        ]
        self.deleted = before - len(self.records)
        return self.deleted

    def filter(self, expr: tuple[str, str, Any]) -> FakeQuery:
        self._filter_expr = expr
        return self


class FakeSession:
    def __init__(self, records: list[DummyRecord] | None = None) -> None:
        self.records = records or []
        self.added: list[Any] = []
        self.rollback_calls = 0

    def add(self, instance: Any) -> None:
        self.added.append(instance)

    def query(self, _model: type) -> FakeQuery:
        return FakeQuery(self.records)

    def rollback(self) -> None:
        self.rollback_calls += 1


class FakeSessionContext:
    def __init__(self, session: FakeSession) -> None:
        self.session = session

    def __enter__(self) -> FakeSession:
        return self.session

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        return False


def make_task(
    *,
    operation: db_write_queue.WriteOperation,
    model_class: str = "DummyModel",
    data: dict[str, Any] | None = None,
    callback: Any = None,
    priority: int = -db_write_queue.WritePriority.NORMAL.value,
    retry_count: int = 0,
    max_retries: int = 3,
    task_id: str = "task-id",
) -> db_write_queue.WriteTask:
    return db_write_queue.WriteTask(
        priority=priority,
        sequence=1,
        operation=operation,
        model_class=model_class,
        data=data or {},
        callback=callback,
        retry_count=retry_count,
        max_retries=max_retries,
        task_id=task_id,
    )


def test_metrics_to_dict_handles_zero_and_average() -> None:
    metrics = db_write_queue.WriteQueueMetrics()
    assert metrics.to_dict()["performance"]["avg_wait_time_ms"] == 0

    metrics.completed_tasks = 2
    metrics.total_wait_time_ms = 9
    metrics.total_process_time_ms = 3
    as_dict = metrics.to_dict()
    assert as_dict["performance"]["avg_wait_time_ms"] == 4.5
    assert as_dict["performance"]["avg_process_time_ms"] == 1.5


def test_singleton_start_stop_and_submit_batch(monkeypatch: pytest.MonkeyPatch) -> None:
    queue = db_write_queue.AsyncWriteQueue()
    queue._max_workers = 2
    assert queue is db_write_queue.AsyncWriteQueue.get_instance()

    starts: list[str] = []
    joins: list[float | None] = []

    class DummyThread:
        def __init__(self, target: Any, name: str, daemon: bool) -> None:
            self.target = target
            self.name = name
            self.daemon = daemon

        def start(self) -> None:
            starts.append(self.name)

        def join(self, timeout: float | None = None) -> None:
            joins.append(timeout)

    monkeypatch.setattr(db_write_queue.threading, "Thread", DummyThread)

    queue.start()
    queue.start()
    assert queue._running is True
    assert starts == ["write-queue-worker-0", "write-queue-worker-1"]

    queue.stop(wait=True)
    assert queue._running is False
    assert joins == [5.0, 5.0]
    assert queue._workers == []

    calls: list[tuple[Any, ...]] = []
    monkeypatch.setattr(
        queue,
        "submit",
        lambda operation, model_class, data, priority: (
            calls.append((operation, model_class, data, priority)) or f"id-{len(calls)}"
        ),
    )

    result = queue.submit_batch(
        [
            (db_write_queue.WriteOperation.INSERT, "A", {"id": 1}),
            (db_write_queue.WriteOperation.DELETE, "B", {"id": 2}),
        ],
        priority=db_write_queue.WritePriority.HIGH,
    )
    assert result == ["id-1", "id-2"]
    assert len(calls) == 2


def test_submit_paths_and_merge_behavior() -> None:
    queue = db_write_queue.AsyncWriteQueue()
    queue._max_queue_size = 1

    with pytest.raises(RuntimeError, match="not running"):
        queue.submit(db_write_queue.WriteOperation.INSERT, "DummyModel", {"id": 1})

    queue._running = True
    first_id = queue.submit(
        db_write_queue.WriteOperation.UPDATE,
        "DummyModel",
        {"id": 1, "name": "before"},
        merge_key="user-1",
    )
    assert len(queue._queue) == 1
    assert queue._metrics.total_tasks == 1
    assert queue._metrics.current_queue_size == 1
    assert queue._metrics.peak_queue_size == 1

    merged_id = queue.submit(
        db_write_queue.WriteOperation.UPDATE,
        "DummyModel",
        {"name": "after"},
        merge_key="user-1",
    )
    assert merged_id == first_id
    assert queue._merge_cache["user-1"].data["name"] == "after"
    assert queue._metrics.merged_writes == 1
    assert len(queue._queue) == 1

    with pytest.raises(RuntimeError, match="full"):
        queue.submit(db_write_queue.WriteOperation.DELETE, "DummyModel", {"id": 2})


def test_get_batch_pops_tasks_updates_wait_time_and_clears_merge_cache() -> None:
    queue = db_write_queue.AsyncWriteQueue()
    queue._batch_size = 2
    queue._batch_timeout_ms = 10

    task_a = make_task(
        operation=db_write_queue.WriteOperation.INSERT,
        task_id="a",
        priority=-db_write_queue.WritePriority.HIGH.value,
    )
    task_b = make_task(
        operation=db_write_queue.WriteOperation.INSERT,
        task_id="b",
        priority=-db_write_queue.WritePriority.NORMAL.value,
    )
    task_a.created_at -= 0.1
    task_b.created_at -= 0.1
    heapq.heappush(queue._queue, task_a)
    heapq.heappush(queue._queue, task_b)
    queue._merge_cache["merge-a"] = task_a

    batch = queue._get_batch()

    assert [task.task_id for task in batch] == ["a", "b"]
    assert queue._merge_cache == {}
    assert queue._metrics.total_wait_time_ms > 0


def test_execute_batch_groups_tasks_and_retries_failed_group(monkeypatch: pytest.MonkeyPatch) -> None:
    queue = db_write_queue.AsyncWriteQueue()
    calls: list[str] = []
    retried: list[str] = []

    def fake_execute_model_batch(model_class: str, tasks: list[db_write_queue.WriteTask]) -> None:
        calls.append(f"{model_class}:{len(tasks)}")
        if model_class == "B":
            raise RuntimeError("group fail")

    monkeypatch.setattr(queue, "_execute_model_batch", fake_execute_model_batch)
    monkeypatch.setattr(queue, "_retry_task", lambda task, _error: retried.append(task.task_id))

    queue._execute_batch(
        [
            make_task(operation=db_write_queue.WriteOperation.INSERT, model_class="A", task_id="a1"),
            make_task(operation=db_write_queue.WriteOperation.INSERT, model_class="A", task_id="a2"),
            make_task(operation=db_write_queue.WriteOperation.INSERT, model_class="B", task_id="b1"),
        ]
    )

    assert calls == ["A:2", "B:1"]
    assert retried == ["b1"]


def test_execute_model_batch_unregistered_model(monkeypatch: pytest.MonkeyPatch) -> None:
    queue = db_write_queue.AsyncWriteQueue()
    callback_states: list[tuple[bool, str]] = []
    errors: list[str] = []

    def ok_callback(success: bool, err: Exception | None) -> None:
        callback_states.append((success, str(err)))

    def broken_callback(_success: bool, _err: Exception | None) -> None:
        raise RuntimeError("callback broke")

    monkeypatch.setattr(db_write_queue.logger, "error", lambda message: errors.append(message))

    queue._execute_model_batch(
        "NotRegistered",
        [
            make_task(operation=db_write_queue.WriteOperation.INSERT, callback=ok_callback, task_id="t1"),
            make_task(operation=db_write_queue.WriteOperation.INSERT, callback=broken_callback, task_id="t2"),
        ],
    )

    assert queue._metrics.failed_tasks == 2
    assert callback_states == [(False, "Model not registered: NotRegistered")]
    assert any("Callback error" in message for message in errors)


def test_execute_model_batch_success_and_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    queue = db_write_queue.AsyncWriteQueue()
    queue.register_model("DummyModel", DummyModel)

    session = FakeSession()
    retried: list[tuple[str, str]] = []
    errors: list[str] = []
    callback_hits: list[tuple[bool, str | None]] = []

    def ok_callback(success: bool, err: Exception | None) -> None:
        callback_hits.append((success, None if err is None else str(err)))

    def broken_callback(_success: bool, _err: Exception | None) -> None:
        raise RuntimeError("callback fail")

    monkeypatch.setattr(db_write_queue, "get_db_session", lambda: FakeSessionContext(session))
    monkeypatch.setattr(queue, "_retry_task", lambda task, error: retried.append((task.task_id, error)))
    monkeypatch.setattr(db_write_queue.logger, "error", lambda message: errors.append(message))

    queue._execute_model_batch(
        "DummyModel",
        [
            make_task(
                operation=db_write_queue.WriteOperation.INSERT,
                data={"id": 1, "name": "ok"},
                callback=ok_callback,
                task_id="ok",
            ),
            make_task(
                operation=db_write_queue.WriteOperation.INSERT,
                data={"id": 2, "raise_on_init": True},
                callback=broken_callback,
                task_id="failed",
            ),
        ],
    )

    assert len(session.added) == 1
    assert queue._metrics.completed_tasks == 1
    assert queue._metrics.current_queue_size == 0
    assert callback_hits == [(True, None)]
    assert retried == [("failed", "init failed")]
    assert any("Task execution failed" in message for message in errors)


def test_execute_single_task_update_delete_and_upsert_paths() -> None:
    queue = db_write_queue.AsyncWriteQueue()

    # UPDATE path
    update_target = DummyRecord(id=10, name="before")
    update_session = FakeSession(records=[update_target])
    update_task = make_task(
        operation=db_write_queue.WriteOperation.UPDATE,
        data={"id": 10, "name": "after"},
    )
    queue._execute_single_task(update_session, DummyModel, update_task)
    assert update_target.name == "after"
    assert "id" not in update_task.data

    # DELETE path
    delete_records = [DummyRecord(id=1, name="a"), DummyRecord(id=2, name="b")]
    delete_session = FakeSession(records=delete_records)
    delete_task = make_task(
        operation=db_write_queue.WriteOperation.DELETE,
        data={"id": 1},
    )
    queue._execute_single_task(delete_session, DummyModel, delete_task)
    assert [record.id for record in delete_records] == [2]

    # UPSERT via model method
    DummyModelWithUpsert.calls = []
    upsert_task = make_task(
        operation=db_write_queue.WriteOperation.UPSERT,
        data={"id": 7, "name": "u"},
    )
    queue._execute_single_task(FakeSession(), DummyModelWithUpsert, upsert_task)
    assert DummyModelWithUpsert.calls == [{"id": 7, "name": "u"}]

    # UPSERT fallback insert-fail then update existing
    fallback_target = DummyRecord(file_id="f-1", name="old")
    fallback_session = FakeSession(records=[fallback_target])
    fallback_task = make_task(
        operation=db_write_queue.WriteOperation.UPSERT,
        data={"file_id": "f-1", "name": "new"},
    )
    queue._execute_single_task(fallback_session, DummyUpsertFallbackModel, fallback_task)
    assert fallback_target.name == "new"
    assert fallback_session.rollback_calls == 1


def test_retry_task_requeue_and_terminal_failure() -> None:
    queue = db_write_queue.AsyncWriteQueue()
    callback_hits: list[tuple[bool, str]] = []

    task = make_task(
        operation=db_write_queue.WriteOperation.INSERT,
        callback=lambda success, err: callback_hits.append((success, str(err))),
        priority=0,
        retry_count=0,
        max_retries=2,
        task_id="retry-me",
    )

    queue._retry_task(task, "first error")
    assert task.retry_count == 1
    assert task.priority == -db_write_queue.WritePriority.HIGH.value
    assert len(queue._queue) == 1

    retried_task = heapq.heappop(queue._queue)
    queue._retry_task(retried_task, "final error")
    assert queue._metrics.failed_tasks == 1
    assert callback_hits == [(False, "final error")]


def test_worker_loop_updates_metrics_and_logs_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    queue = db_write_queue.AsyncWriteQueue()
    queue._running = True
    errors: list[str] = []
    executed: list[int] = []
    call_count = {"value": 0}

    def fake_get_batch() -> list[db_write_queue.WriteTask]:
        call_count["value"] += 1
        if call_count["value"] == 1:
            return [make_task(operation=db_write_queue.WriteOperation.INSERT, task_id="w1")]
        if call_count["value"] == 2:
            raise RuntimeError("worker boom")
        queue._running = False
        return []

    monkeypatch.setattr(queue, "_get_batch", fake_get_batch)
    monkeypatch.setattr(queue, "_execute_batch", lambda tasks: executed.append(len(tasks)))
    monkeypatch.setattr(db_write_queue.logger, "error", lambda message: errors.append(message))

    tick = iter([10.0, 10.2, 10.2])
    monkeypatch.setattr(db_write_queue.time, "time", lambda: next(tick))

    queue._worker_loop()

    assert executed == [1]
    assert queue._metrics.batch_writes == 1
    assert queue._metrics.total_process_time_ms == pytest.approx(200.0)
    assert any("Worker error" in message for message in errors)


def test_status_clear_and_global_helpers(monkeypatch: pytest.MonkeyPatch) -> None:
    queue = db_write_queue.AsyncWriteQueue()
    queue._max_queue_size = 9
    queue._batch_size = 3
    queue._batch_timeout_ms = 7
    queue._max_workers = 4
    queue._running = True

    task = make_task(operation=db_write_queue.WriteOperation.INSERT, task_id="status-task")
    heapq.heappush(queue._queue, task)
    queue._merge_cache["key"] = task

    status = queue.get_status()
    assert status["running"] is True
    assert status["queue_size"] == 1
    assert status["merge_cache_size"] == 1
    assert status["config"]["max_queue_size"] == 9
    assert queue.get_metrics() is queue._metrics

    cleared = queue.clear()
    assert cleared == 1
    assert queue.get_status()["queue_size"] == 0

    db_write_queue._write_queue = None
    global_queue = db_write_queue.get_write_queue()
    assert global_queue is db_write_queue.get_write_queue()

    starts: list[str] = []
    stops: list[bool] = []
    monkeypatch.setattr(global_queue, "start", lambda: starts.append("start"))
    monkeypatch.setattr(global_queue, "stop", lambda wait=True: stops.append(wait))

    db_write_queue.start_write_queue()
    db_write_queue.stop_write_queue(wait=False)

    assert starts == ["start"]
    assert stops == [False]
