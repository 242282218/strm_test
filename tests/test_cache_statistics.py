from __future__ import annotations

import base64
import json
from dataclasses import asdict
from datetime import datetime
from typing import Any

import matplotlib
import pytest

matplotlib.use("Agg", force=True)

from app.services import cache_statistics


@pytest.fixture(autouse=True)
def reset_global_instances() -> None:
    cache_statistics._global_statistics = None
    cache_statistics._global_visualizer = None
    yield
    cache_statistics._global_statistics = None
    cache_statistics._global_visualizer = None


def _make_stat_point(
    *,
    ts: float,
    hits: int,
    misses: int,
    hit_rate: float,
    size: int,
    evictions: int,
    memory: float,
) -> cache_statistics.CacheStatPoint:
    return cache_statistics.CacheStatPoint(
        timestamp=ts,
        hits=hits,
        misses=misses,
        hit_rate=hit_rate,
        size=size,
        evictions=evictions,
        memory_usage_mb=memory,
    )


def test_recording_and_current_stats(monkeypatch: pytest.MonkeyPatch) -> None:
    stats = cache_statistics.CacheStatistics(max_history_points=3)
    timestamps = iter([1000.0, 1001.0])
    monkeypatch.setattr(cache_statistics.time, "time", lambda: next(timestamps))

    stats.record_hit(cache_size=5, memory_mb=1.2)
    stats.record_miss(cache_size=8, memory_mb=2.3)
    stats.record_set()
    stats.record_delete()
    stats.record_eviction()
    stats.record_expiration()

    current = stats.get_current_stats()
    assert current["hits"] == 1
    assert current["misses"] == 1
    assert current["sets"] == 1
    assert current["deletes"] == 1
    assert current["evictions"] == 1
    assert current["expirations"] == 1
    assert current["size"] == 8
    assert current["memory_usage_mb"] == 2.3
    assert current["total_requests"] == 2
    assert current["hit_rate"] == 50.0
    assert current["miss_rate"] == 50.0
    assert current["eviction_rate"] == 50.0
    assert len(stats.history) == 2


def test_get_history_stats_filters_by_hours(monkeypatch: pytest.MonkeyPatch) -> None:
    stats = cache_statistics.CacheStatistics()
    stats.history.extend(
        [
            _make_stat_point(
                ts=900.0,
                hits=1,
                misses=0,
                hit_rate=100.0,
                size=1,
                evictions=0,
                memory=1.0,
            ),
            _make_stat_point(
                ts=980.0,
                hits=2,
                misses=2,
                hit_rate=50.0,
                size=3,
                evictions=1,
                memory=1.5,
            ),
        ]
    )
    monkeypatch.setattr(cache_statistics.time, "time", lambda: 1000.0)

    recent = stats.get_history_stats(hours=0.01)  # 36 seconds
    assert len(recent) == 1
    assert recent[0]["timestamp"] == 980.0
    assert recent[0]["datetime"] == datetime.fromtimestamp(980.0).isoformat()
    assert recent[0]["memory_usage_mb"] == 1.5


def test_generate_performance_report_empty_history(monkeypatch: pytest.MonkeyPatch) -> None:
    stats = cache_statistics.CacheStatistics()
    monkeypatch.setattr(stats, "get_history_stats", lambda hours: [])

    report = stats.generate_performance_report(period="hour")
    assert report.period == "hour"
    assert report.total_requests == 0
    assert report.trends == {}


def test_generate_performance_report_and_trends() -> None:
    stats = cache_statistics.CacheStatistics()

    history_stats: list[dict[str, Any]] = [
        {"hits": 1, "misses": 1, "hit_rate": 50.0, "size": 10, "memory_usage_mb": 5.0, "evictions": 0},
        {"hits": 3, "misses": 1, "hit_rate": 75.0, "size": 15, "memory_usage_mb": 6.0, "evictions": 1},
        {"hits": 4, "misses": 1, "hit_rate": 80.0, "size": 20, "memory_usage_mb": 7.0, "evictions": 2},
    ]
    stats.get_history_stats = lambda hours: history_stats  # type: ignore[method-assign]

    report = stats.generate_performance_report(period="week")
    assert report.period == "week"
    assert report.total_requests == 11
    assert report.total_hits == 8
    assert report.total_misses == 3
    assert report.average_hit_rate == pytest.approx(68.33, abs=0.01)
    assert report.peak_hit_rate == 80.0
    assert report.lowest_hit_rate == 50.0
    assert report.average_size == 15.0
    assert report.peak_memory_mb == 7.0
    assert report.total_evictions == 3
    assert report.trends["hit_rate_trend"] == "increasing"
    assert report.trends["size_trend"] == "growing"


def test_calculate_trends_and_slope_edge_cases() -> None:
    stats = cache_statistics.CacheStatistics()

    assert stats._calculate_trends([{"hit_rate": 1, "size": 1}]) == {}
    assert stats._calculate_slope([1], [1, 2]) == 0.0
    assert stats._calculate_slope([1], [2]) == 0.0
    assert stats._calculate_slope([1, 1], [2, 2]) == 0.0
    assert stats._calculate_slope([0, 1, 2], [6, 4, 2]) < 0


def test_export_stats_json_and_clear_history(monkeypatch: pytest.MonkeyPatch) -> None:
    stats = cache_statistics.CacheStatistics()

    current = {
        "hits": 1,
        "misses": 1,
        "sets": 0,
        "deletes": 0,
        "evictions": 0,
        "expirations": 0,
        "size": 2,
        "memory_usage_mb": 1.1,
        "total_requests": 2,
        "hit_rate": 50.0,
        "miss_rate": 50.0,
        "eviction_rate": 0.0,
    }
    history = [{"timestamp": 1.0, "datetime": "x", "hits": 1, "misses": 1, "hit_rate": 50.0, "size": 2, "evictions": 0, "memory_usage_mb": 1.1}]
    hourly = cache_statistics.CachePerformanceReport(
        period="hour",
        total_requests=2,
        total_hits=1,
        total_misses=1,
        average_hit_rate=50.0,
        peak_hit_rate=50.0,
        lowest_hit_rate=50.0,
        average_size=2.0,
        peak_memory_mb=1.1,
        total_evictions=0,
        trends={},
    )
    daily = cache_statistics.CachePerformanceReport(
        period="day",
        total_requests=2,
        total_hits=1,
        total_misses=1,
        average_hit_rate=50.0,
        peak_hit_rate=50.0,
        lowest_hit_rate=50.0,
        average_size=2.0,
        peak_memory_mb=1.1,
        total_evictions=0,
        trends={},
    )
    weekly = cache_statistics.CachePerformanceReport(
        period="week",
        total_requests=2,
        total_hits=1,
        total_misses=1,
        average_hit_rate=50.0,
        peak_hit_rate=50.0,
        lowest_hit_rate=50.0,
        average_size=2.0,
        peak_memory_mb=1.1,
        total_evictions=0,
        trends={},
    )

    monkeypatch.setattr(stats, "get_current_stats", lambda: current)
    monkeypatch.setattr(stats, "get_history_stats", lambda hours=24: history)

    def fake_report(period: str) -> cache_statistics.CachePerformanceReport:
        if period == "hour":
            return hourly
        if period == "day":
            return daily
        return weekly

    monkeypatch.setattr(stats, "generate_performance_report", fake_report)
    dumped = stats.export_stats_json()
    parsed = json.loads(dumped)

    assert parsed["current_stats"]["hit_rate"] == 50.0
    assert parsed["history"][0]["timestamp"] == 1.0
    assert parsed["reports"]["hourly"] == asdict(hourly)
    assert parsed["reports"]["daily"] == asdict(daily)
    assert parsed["reports"]["weekly"] == asdict(weekly)

    stats.history.extend(
        [
            _make_stat_point(
                ts=1.0,
                hits=1,
                misses=0,
                hit_rate=100.0,
                size=1,
                evictions=0,
                memory=1.0,
            )
        ]
    )
    stats.clear_history()
    assert len(stats.history) == 0


def test_visualizer_hit_rate_and_memory_chart(monkeypatch: pytest.MonkeyPatch) -> None:
    stats = cache_statistics.CacheStatistics()
    visualizer = cache_statistics.CacheVisualizer(stats)

    history = [
        {"timestamp": 1000.0, "hit_rate": 50.0, "memory_usage_mb": 10.0},
        {"timestamp": 1010.0, "hit_rate": 75.0, "memory_usage_mb": 12.0},
    ]
    monkeypatch.setattr(stats, "get_history_stats", lambda hours: history)

    hit_chart = visualizer.generate_hit_rate_chart(hours=24)
    mem_chart = visualizer.generate_memory_usage_chart(hours=24)

    assert isinstance(hit_chart, str)
    assert isinstance(mem_chart, str)
    assert base64.b64decode(hit_chart)[:8] == b"\x89PNG\r\n\x1a\n"
    assert base64.b64decode(mem_chart)[:8] == b"\x89PNG\r\n\x1a\n"


def test_visualizer_empty_chart_and_comparison_chart(monkeypatch: pytest.MonkeyPatch) -> None:
    stats = cache_statistics.CacheStatistics()
    visualizer = cache_statistics.CacheVisualizer(stats)

    monkeypatch.setattr(stats, "get_history_stats", lambda hours: [])
    empty_chart = visualizer.generate_hit_rate_chart(hours=1)
    assert base64.b64decode(empty_chart)[:8] == b"\x89PNG\r\n\x1a\n"

    daily = cache_statistics.CachePerformanceReport(
        period="day",
        total_requests=10,
        total_hits=6,
        total_misses=4,
        average_hit_rate=60.0,
        peak_hit_rate=80.0,
        lowest_hit_rate=40.0,
        average_size=30.0,
        peak_memory_mb=100.0,
        total_evictions=2,
        trends={},
    )
    weekly = cache_statistics.CachePerformanceReport(
        period="week",
        total_requests=70,
        total_hits=49,
        total_misses=21,
        average_hit_rate=70.0,
        peak_hit_rate=90.0,
        lowest_hit_rate=30.0,
        average_size=50.0,
        peak_memory_mb=150.0,
        total_evictions=8,
        trends={},
    )

    monkeypatch.setattr(
        stats,
        "generate_performance_report",
        lambda period: daily if period == "day" else weekly,
    )
    compare_chart = visualizer.generate_comparison_chart()
    assert base64.b64decode(compare_chart)[:8] == b"\x89PNG\r\n\x1a\n"


def test_global_statistics_and_visualizer_singletons() -> None:
    stats1 = cache_statistics.get_cache_statistics()
    stats2 = cache_statistics.get_cache_statistics()
    assert stats1 is stats2

    vis1 = cache_statistics.get_cache_visualizer()
    vis2 = cache_statistics.get_cache_visualizer()
    assert vis1 is vis2
    assert vis1.statistics is stats1
