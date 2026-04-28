from __future__ import annotations

import importlib
from types import SimpleNamespace
from unittest.mock import patch

import pytest

import app.core.prometheus_metrics as metrics


@pytest.fixture
def fresh_metrics_module():
    module = importlib.reload(metrics)
    yield module
    importlib.reload(module)


def test_track_helpers_record_expected_samples(fresh_metrics_module) -> None:
    fresh_metrics_module.track_request("GET", "/health", 200, 0.12)
    fresh_metrics_module.track_strm_generation("success", "quark", duration=1.5)
    fresh_metrics_module.track_scrape_job("success", "tmdb", duration=2.5, items_count=3)
    fresh_metrics_module.track_cache_operation("link", hit=True)
    fresh_metrics_module.track_cache_operation("link", hit=False)
    fresh_metrics_module.update_connection_pool_metrics("http", "aiohttp", active=4, pool_size=20)
    fresh_metrics_module.update_cache_size("link", size_bytes=2048, items=8)
    fresh_metrics_module.update_system_metrics(11.0, 22.0, 333, 44.0)
    fresh_metrics_module.update_db_pool_metrics(size=10, overflow=1, checked_out=3)
    fresh_metrics_module.track_db_query("select", 0.05)

    request_total = fresh_metrics_module.REQUEST_COUNT.labels(
        method="GET", endpoint="/health", status="200"
    )._value.get()
    scrape_total = fresh_metrics_module.SCRAPE_ITEMS_PROCESSED.labels(source="tmdb", status="success")._value.get()

    assert request_total == 1.0
    assert fresh_metrics_module.CACHE_HITS.labels(cache_type="link")._value.get() == 1.0
    assert fresh_metrics_module.CACHE_MISSES.labels(cache_type="link")._value.get() == 1.0
    assert fresh_metrics_module.ACTIVE_CONNECTIONS.labels(pool_type="http", client_type="aiohttp")._value.get() == 4
    assert fresh_metrics_module.CONNECTION_POOL_SIZE.labels(pool_type="http", client_type="aiohttp")._value.get() == 20
    assert fresh_metrics_module.CACHE_SIZE.labels(cache_type="link")._value.get() == 2048
    assert fresh_metrics_module.CACHE_ITEMS.labels(cache_type="link")._value.get() == 8
    assert fresh_metrics_module.SYSTEM_CPU_PERCENT._value.get() == 11.0
    assert fresh_metrics_module.SYSTEM_MEMORY_PERCENT._value.get() == 22.0
    assert fresh_metrics_module.SYSTEM_MEMORY_AVAILABLE._value.get() == 333
    assert fresh_metrics_module.SYSTEM_DISK_PERCENT._value.get() == 44.0
    assert fresh_metrics_module.DB_POOL_SIZE._value.get() == 10
    assert fresh_metrics_module.DB_POOL_OVERFLOW._value.get() == 1
    assert fresh_metrics_module.DB_POOL_CHECKED_OUT._value.get() == 3
    assert scrape_total == 3.0


@pytest.mark.parametrize(
    ("helper_name", "args"),
    [
        ("track_request", ("GET", "/x", 200, 0.1)),
        ("track_strm_generation", ("success", "quark", 0.2)),
        ("track_scrape_job", ("success", "tmdb", 0.3, 2)),
        ("track_cache_operation", ("link", True)),
        ("update_connection_pool_metrics", ("http", "client", 1, 2)),
        ("update_cache_size", ("link", 128, 2)),
        ("update_system_metrics", (1.0, 2.0, 3, 4.0)),
        ("update_db_pool_metrics", (5, 1, 2)),
        ("track_db_query", ("select", 0.01)),
    ],
)
def test_track_helpers_swallow_metric_errors_and_log(
    fresh_metrics_module,
    helper_name: str,
    args: tuple,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    log_calls: list[str] = []

    def _record_log(message: str) -> None:
        log_calls.append(message)

    monkeypatch.setattr(fresh_metrics_module, "logger", SimpleNamespace(error=_record_log))

    class _BrokenMetric:
        def labels(self, **_kwargs):
            raise RuntimeError("boom")

        def set(self, _value):
            raise RuntimeError("boom")

    if helper_name == "track_request":
        monkeypatch.setattr(fresh_metrics_module, "REQUEST_COUNT", _BrokenMetric())
    elif helper_name == "track_strm_generation":
        monkeypatch.setattr(fresh_metrics_module, "STRM_GENERATED", _BrokenMetric())
    elif helper_name == "track_scrape_job":
        monkeypatch.setattr(fresh_metrics_module, "SCRAPE_JOBS_TOTAL", _BrokenMetric())
    elif helper_name == "track_cache_operation":
        monkeypatch.setattr(fresh_metrics_module, "CACHE_HITS", _BrokenMetric())
        monkeypatch.setattr(fresh_metrics_module, "CACHE_MISSES", _BrokenMetric())
    elif helper_name == "update_connection_pool_metrics":
        monkeypatch.setattr(fresh_metrics_module, "ACTIVE_CONNECTIONS", _BrokenMetric())
    elif helper_name == "update_cache_size":
        monkeypatch.setattr(fresh_metrics_module, "CACHE_SIZE", _BrokenMetric())
    elif helper_name == "update_system_metrics":
        monkeypatch.setattr(fresh_metrics_module, "SYSTEM_CPU_PERCENT", _BrokenMetric())
    elif helper_name == "update_db_pool_metrics":
        monkeypatch.setattr(fresh_metrics_module, "DB_POOL_SIZE", _BrokenMetric())
    elif helper_name == "track_db_query":
        monkeypatch.setattr(fresh_metrics_module, "DB_QUERY_DURATION", _BrokenMetric())

    getattr(fresh_metrics_module, helper_name)(*args)

    assert log_calls


@pytest.mark.asyncio
async def test_prometheus_track_async_success_and_error(fresh_metrics_module) -> None:
    with patch.object(fresh_metrics_module, "track_request") as track_request:

        @fresh_metrics_module.prometheus_track("/async-ok")
        async def ok_handler():
            return "ok"

        @fresh_metrics_module.prometheus_track("/async-fail")
        async def fail_handler():
            raise RuntimeError("failed")

        assert await ok_handler() == "ok"
        track_request.assert_any_call(
            method="INTERNAL", endpoint="/async-ok", status=200, duration=pytest.approx(0, abs=1)
        )

        with pytest.raises(RuntimeError, match="failed"):
            await fail_handler()
        track_request.assert_any_call(
            method="INTERNAL",
            endpoint="/async-fail",
            status=500,
            duration=pytest.approx(0, abs=1),
        )


def test_prometheus_track_sync_success_and_error(fresh_metrics_module) -> None:
    with patch.object(fresh_metrics_module, "track_request") as track_request:

        @fresh_metrics_module.prometheus_track("/sync-ok")
        def ok_handler():
            return 42

        @fresh_metrics_module.prometheus_track("/sync-fail")
        def fail_handler():
            raise ValueError("oops")

        assert ok_handler() == 42
        track_request.assert_any_call(
            method="INTERNAL", endpoint="/sync-ok", status=200, duration=pytest.approx(0, abs=1)
        )

        with pytest.raises(ValueError, match="oops"):
            fail_handler()
        track_request.assert_any_call(
            method="INTERNAL",
            endpoint="/sync-fail",
            status=500,
            duration=pytest.approx(0, abs=1),
        )
