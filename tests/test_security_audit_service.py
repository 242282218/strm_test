from __future__ import annotations

import asyncio
import threading
from datetime import datetime

import pytest

import app.services.security_audit_service as security_audit
from app.models.security_event import SecurityEventSeverity, SecurityEventType


class DummyEvent:
    def __init__(
        self,
        *,
        event_id: int = 1,
        event_type: str = SecurityEventType.LOGIN_FAILED.value,
        severity: str = SecurityEventSeverity.LOW.value,
        status: str = "new",
        username: str | None = None,
        ip_address: str | None = None,
    ) -> None:
        self.id = event_id
        self.event_type = event_type
        self.severity = severity
        self.status = status
        self.username = username
        self.ip_address = ip_address
        self.title = "dummy"
        self.description = "dummy description"
        self.created_at = datetime(2026, 4, 16, 12, 0, 0)
        self.ack_calls: list[tuple[int, str | None]] = []
        self.resolve_calls: list[tuple[int, str | None]] = []

    def acknowledge(self, db, user_id: int, note: str | None) -> None:
        self.ack_calls.append((user_id, note))

    def resolve(self, db, user_id: int, note: str | None) -> None:
        self.resolve_calls.append((user_id, note))


class FakeQuery:
    def __init__(self, events: list[DummyEvent]) -> None:
        self._events = events

    def filter(self, *_args, **_kwargs) -> "FakeQuery":
        return self

    def all(self) -> list[DummyEvent]:
        return self._events

    def first(self):
        return self._events[0] if self._events else None


class FakeDB:
    def __init__(self, events: list[DummyEvent]) -> None:
        self._events = events

    def query(self, _model):
        return FakeQuery(self._events)


def test_get_instance_returns_singleton() -> None:
    security_audit.SecurityAuditService._instance = None
    first = security_audit.get_security_audit_service()
    second = security_audit.get_security_audit_service()
    assert first is second


@pytest.mark.asyncio
async def test_initialize_is_idempotent() -> None:
    service = security_audit.SecurityAuditService()
    assert service._initialized is False
    await service.initialize()
    await service.initialize()
    assert service._initialized is True


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ("SELECT * FROM users", "sql"),
        ("<script>alert(1)</script>", "xss"),
        ("cat /etc/passwd", "command"),
        ("hello-world", None),
    ],
)
def test_detect_injection_attempt(payload: str, expected: str | None) -> None:
    service = security_audit.SecurityAuditService()
    assert service.detect_injection_attempt(payload) == expected


def test_check_brute_force_uses_threshold(monkeypatch: pytest.MonkeyPatch) -> None:
    service = security_audit.SecurityAuditService()
    monkeypatch.setattr(
        security_audit.SecurityEvent,
        "count_by_type",
        lambda **kwargs: 9,
    )
    assert service.check_brute_force(db=object(), ip_address="1.1.1.1", threshold=10) is False
    assert service.check_brute_force(db=object(), ip_address="1.1.1.1", threshold=9) is True


@pytest.mark.parametrize(
    ("recent_failures", "expected_severity", "expect_alert"),
    [
        (2, SecurityEventSeverity.LOW, False),
        (3, SecurityEventSeverity.MEDIUM, False),
        (5, SecurityEventSeverity.HIGH, True),
    ],
)
def test_record_login_failed_sets_severity_and_alert(
    monkeypatch: pytest.MonkeyPatch,
    recent_failures: int,
    expected_severity: SecurityEventSeverity,
    expect_alert: bool,
) -> None:
    service = security_audit.SecurityAuditService()
    access_calls: list[dict] = []
    alert_calls: list[DummyEvent] = []
    create_calls: list[dict] = []

    monkeypatch.setattr(
        security_audit.IPAccessRecord,
        "record_access",
        lambda **kwargs: access_calls.append(kwargs),
    )
    monkeypatch.setattr(
        security_audit.SecurityEvent,
        "count_by_type",
        lambda **kwargs: recent_failures,
    )

    def fake_create(**kwargs):
        create_calls.append(kwargs)
        return DummyEvent(
            event_type=kwargs["event_type"].value,
            severity=kwargs["severity"].value,
            username=kwargs.get("username"),
            ip_address=kwargs.get("ip_address"),
        )

    monkeypatch.setattr(security_audit.SecurityEvent, "create", fake_create)
    monkeypatch.setattr(service, "_schedule_security_alert", lambda event: alert_calls.append(event))

    event = service.record_login_failed(
        db=object(),
        username="alice",
        ip_address="10.0.0.1",
        user_agent="pytest",
        failure_reason="bad password",
    )

    assert event.severity == expected_severity.value
    assert create_calls[0]["details"]["recent_failures"] == recent_failures
    assert len(access_calls) == 1
    assert len(alert_calls) == (1 if expect_alert else 0)


def test_record_login_success_marks_new_ip(monkeypatch: pytest.MonkeyPatch) -> None:
    service = security_audit.SecurityAuditService()
    create_calls: list[dict] = []

    monkeypatch.setattr(service, "_check_new_ip", lambda db, user_id, ip_address: True)
    monkeypatch.setattr(security_audit.IPAccessRecord, "record_access", lambda **kwargs: None)

    def fake_create(**kwargs):
        create_calls.append(kwargs)
        return DummyEvent(event_type=kwargs["event_type"].value, severity=kwargs["severity"].value)

    monkeypatch.setattr(security_audit.SecurityEvent, "create", fake_create)

    event = service.record_login_success(
        db=object(),
        user_id=7,
        username="alice",
        ip_address="10.0.0.2",
        user_agent="pytest",
    )

    assert event.severity == SecurityEventSeverity.MEDIUM.value
    assert create_calls[0]["details"]["is_new_ip"] is True


def test_record_unauthorized_access_sets_high_severity_at_threshold(monkeypatch: pytest.MonkeyPatch) -> None:
    service = security_audit.SecurityAuditService()
    create_calls: list[dict] = []

    monkeypatch.setattr(security_audit.IPAccessRecord, "record_access", lambda **kwargs: None)
    monkeypatch.setattr(security_audit.SecurityEvent, "count_by_type", lambda **kwargs: 10)

    def fake_create(**kwargs):
        create_calls.append(kwargs)
        return DummyEvent(event_type=kwargs["event_type"].value, severity=kwargs["severity"].value)

    monkeypatch.setattr(security_audit.SecurityEvent, "create", fake_create)

    event = service.record_unauthorized_access(
        db=object(),
        ip_address="10.0.0.3",
        request_path="/api/admin",
        request_method="GET",
    )

    assert event.severity == SecurityEventSeverity.HIGH.value
    assert create_calls[0]["details"]["recent_attempts"] == 10


def test_record_sensitive_config_change_masks_values_and_schedules_alert(monkeypatch: pytest.MonkeyPatch) -> None:
    service = security_audit.SecurityAuditService()
    alert_calls: list[DummyEvent] = []
    create_calls: list[dict] = []

    def fake_create(**kwargs):
        create_calls.append(kwargs)
        return DummyEvent(event_type=kwargs["event_type"].value, severity=kwargs["severity"].value)

    monkeypatch.setattr(security_audit.SecurityEvent, "create", fake_create)
    monkeypatch.setattr(service, "_schedule_security_alert", lambda event: alert_calls.append(event))

    service.record_sensitive_config_change(
        db=object(),
        user_id=1,
        username="admin",
        config_key="api_key",
        old_value="old-secret",
        new_value="new-secret",
    )

    assert create_calls[0]["details"]["old_value"] == "***"
    assert create_calls[0]["details"]["new_value"] == "***"
    assert len(alert_calls) == 1


def test_get_security_summary_aggregates_event_and_ip_data(monkeypatch: pytest.MonkeyPatch) -> None:
    service = security_audit.SecurityAuditService()
    events = [
        DummyEvent(event_type=SecurityEventType.LOGIN_FAILED.value, severity="high", status="new"),
        DummyEvent(event_type=SecurityEventType.LOGIN_FAILED.value, severity="high", status="resolved"),
        DummyEvent(event_type=SecurityEventType.LOGIN_SUCCESS.value, severity="low", status="new"),
    ]

    class SuspiciousIP:
        def __init__(self, ip: str) -> None:
            self.ip = ip

        def to_dict(self) -> dict[str, str]:
            return {"ip_address": self.ip}

    monkeypatch.setattr(
        security_audit.IPAccessRecord,
        "get_suspicious_ips",
        lambda db, limit=10: [SuspiciousIP("10.0.0.9")],
    )

    summary = service.get_security_summary(db=FakeDB(events), days=7)

    assert summary["total_events"] == 3
    assert summary["by_type"][SecurityEventType.LOGIN_FAILED.value] == 2
    assert summary["by_severity"]["high"] == 2
    assert summary["by_status"]["new"] == 2
    assert summary["suspicious_ips"] == [{"ip_address": "10.0.0.9"}]


def test_acknowledge_and_resolve_event(monkeypatch: pytest.MonkeyPatch) -> None:
    service = security_audit.SecurityAuditService()
    event = DummyEvent()

    monkeypatch.setattr(
        security_audit.SecurityEvent,
        "get_by_id",
        classmethod(lambda cls, db, event_id: event if event_id == 1 else None),
    )

    acknowledged = service.acknowledge_event(db=object(), event_id=1, user_id=9, note="checked")
    resolved = service.resolve_event(db=object(), event_id=1, user_id=9, note="fixed")
    missing = service.resolve_event(db=object(), event_id=99, user_id=9, note=None)

    assert acknowledged is event
    assert resolved is event
    assert missing is None
    assert event.ack_calls == [(9, "checked")]
    assert event.resolve_calls == [(9, "fixed")]


def test_schedule_security_alert_uses_running_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    service = security_audit.SecurityAuditService()
    event = DummyEvent()
    create_task_calls = {"count": 0}

    async def fake_send(_event: DummyEvent) -> None:
        return None

    class FakeLoop:
        def create_task(self, coro):
            create_task_calls["count"] += 1
            coro.close()

    monkeypatch.setattr(service, "_send_security_alert", fake_send)
    monkeypatch.setattr(asyncio, "get_running_loop", lambda: FakeLoop())

    service._schedule_security_alert(event)

    assert create_task_calls["count"] == 1


def test_schedule_security_alert_falls_back_to_thread(monkeypatch: pytest.MonkeyPatch) -> None:
    service = security_audit.SecurityAuditService()
    event = DummyEvent()
    started = {"value": False}

    class FakeThread:
        def __init__(self, target, args, daemon):
            self.target = target
            self.args = args
            self.daemon = daemon

        def start(self):
            started["value"] = True

    def raise_runtime_error():
        raise RuntimeError("no running loop")

    monkeypatch.setattr(asyncio, "get_running_loop", raise_runtime_error)
    monkeypatch.setattr(threading, "Thread", FakeThread)

    service._schedule_security_alert(event)

    assert started["value"] is True
