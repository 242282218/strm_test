from __future__ import annotations

import types
from datetime import datetime

import pytest

from app.core import db_pool_monitor


def _health_result(
    *,
    healthy: bool = True,
    pool_type: str = "QueuePool",
    mode: str = "sqlite",
    pool_size: int = 10,
    checked_in: int = 8,
    checked_out: int = 2,
    overflow: int = 0,
    invalid: int = 0,
    message: str = "ok",
) -> dict:
    return {
        "healthy": healthy,
        "message": message,
        "pool_status": {
            "pool_type": pool_type,
            "mode": mode,
            "pool_size": pool_size,
            "checked_in": checked_in,
            "checked_out": checked_out,
            "overflow": overflow,
            "invalid": invalid,
        },
    }


def test_collect_metrics_and_history_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(db_pool_monitor, "check_pool_health", lambda: _health_result())
    monitor = db_pool_monitor.PoolMonitor(db_pool_monitor.MonitorConfig(history_size=2))

    metrics = monitor.collect_metrics()
    assert metrics.healthy is True
    assert metrics.pool_type == "QueuePool"
    assert metrics.pool_size == 10

    monitor._add_to_history(metrics)
    monitor._add_to_history(metrics)
    monitor._add_to_history(metrics)
    assert len(monitor._metrics_history) == 2


def test_check_alerts_for_critical_and_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    monitor = db_pool_monitor.PoolMonitor(
        db_pool_monitor.MonitorConfig(checkout_threshold=0.8, invalid_threshold=3)
    )
    monkeypatch.setattr(db_pool_monitor, "get_pool_config", lambda: types.SimpleNamespace(pool_size=10, max_overflow=0))

    unhealthy = db_pool_monitor.PoolMetrics(
        timestamp=datetime.utcnow(),
        pool_type="QueuePool",
        mode="sqlite",
        healthy=False,
        message="db down",
    )
    assert monitor._check_alerts(unhealthy) == "critical"

    high_checkout = db_pool_monitor.PoolMetrics(
        timestamp=datetime.utcnow(),
        pool_type="QueuePool",
        mode="sqlite",
        pool_size=10,
        checked_out=9,
        invalid=0,
        healthy=True,
    )
    assert monitor._check_alerts(high_checkout) == "warning"

    high_invalid = db_pool_monitor.PoolMetrics(
        timestamp=datetime.utcnow(),
        pool_type="QueuePool",
        mode="sqlite",
        pool_size=10,
        checked_out=1,
        invalid=4,
        healthy=True,
    )
    assert monitor._check_alerts(high_invalid) == "warning"


def test_trigger_alerts_respects_enable_flag_and_catches_callback_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monitor = db_pool_monitor.PoolMonitor(db_pool_monitor.MonitorConfig(enable_alerts=True))
    calls: list[str] = []
    errors: list[str] = []

    def ok_callback(level: str, _metrics: db_pool_monitor.PoolMetrics) -> None:
        calls.append(level)

    def bad_callback(_level: str, _metrics: db_pool_monitor.PoolMetrics) -> None:
        raise RuntimeError("callback failed")

    monitor.add_alert_callback(ok_callback)
    monitor.add_alert_callback(bad_callback)
    monkeypatch.setattr(db_pool_monitor.logger, "error", lambda message: errors.append(message))

    monitor._trigger_alerts(
        "warning",
        db_pool_monitor.PoolMetrics(
            timestamp=datetime.utcnow(),
            pool_type="QueuePool",
            mode="sqlite",
            healthy=True,
        ),
    )

    assert calls == ["warning"]
    assert any("Alert callback failed" in message for message in errors)

    disabled = db_pool_monitor.PoolMonitor(db_pool_monitor.MonitorConfig(enable_alerts=False))
    disabled.add_alert_callback(ok_callback)
    disabled._trigger_alerts(
        "warning",
        db_pool_monitor.PoolMetrics(
            timestamp=datetime.utcnow(),
            pool_type="QueuePool",
            mode="sqlite",
            healthy=True,
        ),
    )
    assert calls == ["warning"]


def test_start_and_stop_monitoring(monkeypatch: pytest.MonkeyPatch) -> None:
    monitor = db_pool_monitor.PoolMonitor(db_pool_monitor.MonitorConfig(check_interval=1))
    starts: list[str] = []

    class DummyThread:
        def __init__(self, target, daemon, name) -> None:
            self.target = target
            self.daemon = daemon
            self.name = name

        def start(self) -> None:
            starts.append(self.name)

        def join(self, timeout=None) -> None:
            starts.append(f"join:{timeout}")

    monkeypatch.setattr(db_pool_monitor.threading, "Thread", DummyThread)

    monitor.start()
    assert monitor._monitoring is True
    assert starts == ["PoolMonitor"]

    monitor.start()  # already running
    assert starts == ["PoolMonitor"]

    monitor.stop()
    assert monitor._monitoring is False
    assert starts[-1] == "join:5"


def test_get_status_and_health_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    health_ok = _health_result(healthy=True, checked_out=9, message="ok")
    monkeypatch.setattr(db_pool_monitor, "check_pool_health", lambda: health_ok)
    monkeypatch.setattr(db_pool_monitor, "get_pool_status", lambda: {"pool": "ok"})
    monkeypatch.setattr(db_pool_monitor, "get_pool_config", lambda: types.SimpleNamespace(pool_size=10, max_overflow=0))

    monitor = db_pool_monitor.PoolMonitor(db_pool_monitor.MonitorConfig(checkout_threshold=0.8))
    monitor._add_to_history(
        db_pool_monitor.PoolMetrics(
            timestamp=datetime.utcnow(),
            pool_type="QueuePool",
            mode="sqlite",
            healthy=True,
        )
    )

    status = monitor.get_status()
    assert status["monitoring"] is False
    assert status["history_count"] == 1
    assert status["current_metrics"]["pool_type"] == "QueuePool"

    summary = monitor.get_health_summary()
    assert summary["status"] == db_pool_monitor.HealthStatus.DEGRADED.value
    assert summary["healthy"] is True
    assert summary["pool_status"] == {"pool": "ok"}

    monkeypatch.setattr(
        db_pool_monitor,
        "check_pool_health",
        lambda: _health_result(healthy=False, checked_out=0, message="down"),
    )
    summary_unhealthy = monitor.get_health_summary()
    assert summary_unhealthy["status"] == db_pool_monitor.HealthStatus.UNHEALTHY.value


def test_global_monitor_helpers_and_default_alert_handler(monkeypatch: pytest.MonkeyPatch) -> None:
    db_pool_monitor._monitor_instance = None

    monitor = db_pool_monitor.get_pool_monitor(db_pool_monitor.MonitorConfig(check_interval=3))
    same_monitor = db_pool_monitor.get_pool_monitor()
    assert monitor is same_monitor
    assert monitor.config.check_interval == 3

    started: list[str] = []
    stopped: list[str] = []
    monkeypatch.setattr(monitor, "start", lambda: started.append("start"))
    monkeypatch.setattr(monitor, "stop", lambda: stopped.append("stop"))

    returned = db_pool_monitor.start_monitoring()
    assert returned is monitor
    assert started == ["start"]

    db_pool_monitor.stop_monitoring()
    assert stopped == ["stop"]

    critical: list[str] = []
    warnings: list[str] = []
    infos: list[str] = []
    monkeypatch.setattr(db_pool_monitor.logger, "critical", lambda msg: critical.append(msg))
    monkeypatch.setattr(db_pool_monitor.logger, "warning", lambda msg: warnings.append(msg))
    monkeypatch.setattr(db_pool_monitor.logger, "info", lambda msg: infos.append(msg))

    metrics = db_pool_monitor.PoolMetrics(
        timestamp=datetime.utcnow(),
        pool_type="QueuePool",
        mode="sqlite",
        checked_out=8,
        healthy=False,
        message="failure",
    )
    db_pool_monitor.default_alert_handler("critical", metrics)
    db_pool_monitor.default_alert_handler("warning", metrics)
    db_pool_monitor.default_alert_handler("info", metrics)

    assert any("POOL ALERT [critical]" in msg for msg in critical)
    assert any("Pool under pressure" in msg for msg in warnings)
    assert any("POOL ALERT [info]" in msg for msg in infos)
