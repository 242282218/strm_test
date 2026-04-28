from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from app.core import db_utils


class DummyField:
    def __init__(self, name: str) -> None:
        self.name = name

    def in_(self, values: list[Any]) -> tuple[str, str, tuple[Any, ...]]:
        return ("in", self.name, tuple(values))


class DummyModel:
    id = DummyField("id")
    category = DummyField("category")

    def __init__(self, record_id: int, category: str) -> None:
        self.id = record_id
        self.category = category


@dataclass
class FakeQuery:
    records: list[Any]
    applied_filters: list[tuple[str, str, tuple[Any, ...]]]
    options_calls: list[str]
    offset_value: int | None = None
    limit_value: int | None = None

    def filter(self, filter_expr: tuple[str, str, tuple[Any, ...]]) -> FakeQuery:
        self.applied_filters.append(filter_expr)
        return self

    def all(self) -> list[Any]:
        if not self.applied_filters:
            return self.records

        _, field_name, allowed_values = self.applied_filters[-1]
        allowed = set(allowed_values)
        return [record for record in self.records if getattr(record, field_name) in allowed]

    def options(self, option: str) -> FakeQuery:
        self.options_calls.append(option)
        return self

    def offset(self, value: int) -> FakeQuery:
        self.offset_value = value
        return self

    def limit(self, value: int) -> FakeQuery:
        self.limit_value = value
        return self


class FakeSession:
    def __init__(self, records: list[Any]) -> None:
        self.records = records
        self.created_queries: list[FakeQuery] = []

    def query(self, _model_class: type[Any]) -> FakeQuery:
        query = FakeQuery(records=self.records, applied_filters=[], options_calls=[])
        self.created_queries.append(query)
        return query


def test_batch_get_by_ids_returns_records_in_batches() -> None:
    session = FakeSession(
        [
            DummyModel(1, "tv"),
            DummyModel(2, "movie"),
            DummyModel(3, "tv"),
        ]
    )

    result = db_utils.BatchQueryHelper.batch_get_by_ids(
        session=session,
        model_class=DummyModel,
        ids=[1, 3, 2],
        batch_size=2,
    )

    assert set(result.keys()) == {1, 2, 3}
    assert len(session.created_queries) == 2


def test_batch_get_by_ids_returns_empty_for_empty_ids() -> None:
    session = FakeSession([])

    result = db_utils.BatchQueryHelper.batch_get_by_ids(
        session=session,
        model_class=DummyModel,
        ids=[],
    )

    assert result == {}
    assert session.created_queries == []


def test_batch_get_by_field_groups_records_by_requested_values() -> None:
    session = FakeSession(
        [
            DummyModel(1, "tv"),
            DummyModel(2, "movie"),
            DummyModel(3, "tv"),
        ]
    )

    result = db_utils.BatchQueryHelper.batch_get_by_field(
        session=session,
        model_class=DummyModel,
        field_name="category",
        values=["tv", "movie", "anime"],
        batch_size=2,
    )

    assert [item.id for item in result["tv"]] == [1, 3]
    assert [item.id for item in result["movie"]] == [2]
    assert result["anime"] == []
    assert len(session.created_queries) == 2


def test_apply_eager_loading_uses_joinedload_for_nested_relationships(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    query = FakeQuery(records=[], applied_filters=[], options_calls=[])
    monkeypatch.setattr(db_utils, "selectinload", lambda rel: f"selectin:{rel}")
    monkeypatch.setattr(db_utils, "joinedload", lambda rel: f"joined:{rel}")

    result = db_utils.QueryOptimizer.apply_eager_loading(query, ["owner", "owner.profile"])

    assert result is query
    assert query.options_calls == ["selectin:owner", "joined:owner.profile"]


def test_paginate_query_sets_offset_and_limit() -> None:
    query = FakeQuery(records=[], applied_filters=[], options_calls=[])

    result = db_utils.QueryOptimizer.paginate_query(query, page=3, page_size=20)

    assert result is query
    assert query.offset_value == 40
    assert query.limit_value == 20


def test_add_performance_hints_returns_original_query() -> None:
    query = FakeQuery(records=[], applied_filters=[], options_calls=[])

    assert db_utils.QueryOptimizer.add_performance_hints(query) is query


@pytest.mark.asyncio
async def test_async_batch_processor_with_async_function() -> None:
    async def processor(batch: list[int]) -> list[int]:
        return [item * 10 for item in batch]

    batch_processor = db_utils.AsyncBatchProcessor(batch_size=2, delay=0)
    result = await batch_processor.process_items_batched([1, 2, 3], processor)

    assert result == [10, 20, 30]


@pytest.mark.asyncio
async def test_async_batch_processor_with_sync_function() -> None:
    def processor(batch: list[int]) -> int:
        return sum(batch)

    batch_processor = db_utils.AsyncBatchProcessor(batch_size=2, delay=0)
    result = await batch_processor.process_items_batched([1, 2, 3], processor)

    assert result == [3, 3]


@pytest.mark.asyncio
async def test_async_batch_processor_logs_and_raises_on_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    errors: list[str] = []
    monkeypatch.setattr(db_utils.logger, "error", lambda message: errors.append(message))

    async def broken_processor(_batch: list[int]) -> list[int]:
        raise RuntimeError("broken")

    batch_processor = db_utils.AsyncBatchProcessor(batch_size=2, delay=0)

    with pytest.raises(RuntimeError, match="broken"):
        await batch_processor.process_items_batched([1, 2], broken_processor)

    assert any("Batch processing failed" in message for message in errors)


@pytest.mark.asyncio
async def test_async_batch_processor_returns_empty_for_empty_input() -> None:
    batch_processor = db_utils.AsyncBatchProcessor(batch_size=2, delay=0)
    result = await batch_processor.process_items_batched([], lambda batch: batch)
    assert result == []


@pytest.mark.asyncio
async def test_scan_directory_streaming_without_batch_processor(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")
    (tmp_path / "b.log").write_text("b", encoding="utf-8")

    results = await db_utils.MemoryEfficientScanner.scan_directory_streaming(
        str(tmp_path),
        file_filter=lambda file_path: file_path.endswith(".txt"),
    )

    assert results == [str(tmp_path / "a.txt")]


@pytest.mark.asyncio
async def test_scan_directory_streaming_with_batch_processor(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")
    (tmp_path / "b.txt").write_text("b", encoding="utf-8")

    class RecordingBatchProcessor:
        def __init__(self) -> None:
            self.received: list[str] = []

        async def process_items_batched(self, items: list[str], _processor_func: Any) -> list[str]:
            self.received = items
            return [f"count={len(items)}"]

    batch_processor = RecordingBatchProcessor()
    results = await db_utils.MemoryEfficientScanner.scan_directory_streaming(
        str(tmp_path),
        batch_processor=batch_processor,
    )

    assert results == ["count=2"]
    assert len(batch_processor.received) == 2


@pytest.mark.asyncio
async def test_scan_directory_streaming_logs_error_when_walk_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    errors: list[str] = []
    monkeypatch.setattr(db_utils.logger, "error", lambda message: errors.append(message))
    monkeypatch.setattr(os, "walk", lambda _path: (_ for _ in ()).throw(RuntimeError("walk failed")))

    results = await db_utils.MemoryEfficientScanner.scan_directory_streaming("unused-path")

    assert results == []
    assert any("Error scanning directory" in message for message in errors)


def test_performance_monitor_records_batch_and_single_queries() -> None:
    monitor = db_utils.PerformanceMonitor()

    monitor.record_query(0.1, is_batch=True)
    monitor.record_query(0.3, is_batch=False)
    stats = monitor.get_stats()

    assert stats["query_stats"]["total_queries"] == 2
    assert stats["query_stats"]["batch_queries"] == 1
    assert stats["query_stats"]["single_queries"] == 1
    assert stats["query_stats"]["avg_query_time"] == pytest.approx(0.2)


def test_get_performance_monitor_returns_singleton_instance() -> None:
    assert db_utils.get_performance_monitor() is db_utils.get_performance_monitor()


def test_wrapper_functions_delegate_to_underlying_implementations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    by_ids_calls: list[tuple[Any, Any, Any]] = []
    eager_calls: list[tuple[Any, Any]] = []

    def fake_batch_get_by_ids(session: Any, model_class: Any, ids: list[int]) -> dict[int, str]:
        by_ids_calls.append((session, model_class, tuple(ids)))
        return {1: "ok"}

    def fake_apply_eager_loading(query: Any, relationships: list[str]) -> str:
        eager_calls.append((query, tuple(relationships)))
        return "optimized"

    monkeypatch.setattr(db_utils.BatchQueryHelper, "batch_get_by_ids", fake_batch_get_by_ids)
    monkeypatch.setattr(db_utils.QueryOptimizer, "apply_eager_loading", fake_apply_eager_loading)

    result_by_ids = db_utils.batch_get_models_by_ids("session", "model", [1])
    result_query = db_utils.optimize_query_with_relationships("query", ["a.b"])

    assert result_by_ids == {1: "ok"}
    assert by_ids_calls == [("session", "model", (1,))]
    assert result_query == "optimized"
    assert eager_calls == [("query", ("a.b",))]


@pytest.mark.asyncio
async def test_process_items_in_batches_wrapper() -> None:
    async def processor(batch: list[int]) -> list[int]:
        return [item + 1 for item in batch]

    result = await db_utils.process_items_in_batches([1, 2, 3], processor, batch_size=2)

    assert result == [2, 3, 4]
