from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.api.security as security_api
from app.core.dependencies import get_admin_user
from app.models.security_event import SecurityEventSeverity, SecurityEventStatus, SecurityEventType


class DummyEvent:
    def __init__(self, event_id: int = 1) -> None:
        self.event_id = event_id

    def to_dict(self) -> dict:
        return {
            "id": self.event_id,
            "event_type": "login_failed",
            "severity": "high",
            "status": "new",
            "user_id": None,
            "username": None,
            "ip_address": "127.0.0.1",
            "user_agent": "pytest",
            "title": "Security event",
            "description": "test event",
            "details": {},
            "request_path": "/api/security/events",
            "request_method": "GET",
            "acknowledged_by": None,
            "acknowledged_at": None,
            "resolved_by": None,
            "resolved_at": None,
            "resolution_note": None,
            "created_at": "2026-03-12T00:00:00",
            "updated_at": "2026-03-12T00:00:00",
        }


class CapturingSecurityAuditService:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def get_security_events(self, **kwargs):
        self.calls.append(kwargs)
        return [DummyEvent()]


def build_client() -> TestClient:
    app = FastAPI()
    app.include_router(security_api.router)
    app.dependency_overrides[security_api.get_db] = lambda: object()
    app.dependency_overrides[get_admin_user] = lambda: SimpleNamespace(id=9, role="admin")
    return TestClient(app)


def test_events_endpoint_parses_valid_filters_to_enum(monkeypatch) -> None:
    service = CapturingSecurityAuditService()
    monkeypatch.setattr(security_api, "get_security_audit_service", lambda: service)

    client = build_client()
    response = client.get(
        "/api/security/events",
        params={
            "event_type": SecurityEventType.LOGIN_FAILED.value,
            "severity": SecurityEventSeverity.HIGH.value,
            "status": SecurityEventStatus.RESOLVED.value,
            "limit": 25,
            "user_id": 8,
            "ip_address": "10.0.0.5",
        },
    )

    assert response.status_code == 200
    assert service.calls[0]["event_type"] == SecurityEventType.LOGIN_FAILED
    assert service.calls[0]["severity"] == SecurityEventSeverity.HIGH
    assert service.calls[0]["status"] == SecurityEventStatus.RESOLVED
    assert service.calls[0]["limit"] == 25
    assert service.calls[0]["user_id"] == 8
    assert service.calls[0]["ip_address"] == "10.0.0.5"


def test_events_endpoint_ignores_invalid_filters(monkeypatch) -> None:
    service = CapturingSecurityAuditService()
    monkeypatch.setattr(security_api, "get_security_audit_service", lambda: service)

    client = build_client()
    response = client.get(
        "/api/security/events",
        params={
            "event_type": "not-a-type",
            "severity": "not-a-severity",
            "status": "not-a-status",
        },
    )

    assert response.status_code == 200
    assert service.calls[0]["event_type"] is None
    assert service.calls[0]["severity"] is None
    assert service.calls[0]["status"] is None


def test_get_security_event_returns_404_when_missing(monkeypatch) -> None:
    monkeypatch.setattr(
        security_api.SecurityEvent,
        "get_by_id",
        classmethod(lambda cls, db, event_id: None),
    )
    client = build_client()

    response = client.get("/api/security/events/999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Event not found"}


def test_mark_false_positive_returns_404_when_missing(monkeypatch) -> None:
    monkeypatch.setattr(
        security_api.SecurityEvent,
        "get_by_id",
        classmethod(lambda cls, db, event_id: None),
    )
    client = build_client()

    response = client.post("/api/security/events/1000/false-positive", json={"note": "not found"})

    assert response.status_code == 404
    assert response.json() == {"detail": "Event not found"}


def test_enum_metadata_endpoints_return_values() -> None:
    client = build_client()

    event_types = client.get("/api/security/event-types")
    severities = client.get("/api/security/severities")
    statuses = client.get("/api/security/statuses")

    assert event_types.status_code == 200
    assert severities.status_code == 200
    assert statuses.status_code == 200

    type_values = {item["value"] for item in event_types.json()["types"]}
    severity_values = {item["value"] for item in severities.json()["severities"]}
    status_values = {item["value"] for item in statuses.json()["statuses"]}

    assert SecurityEventType.LOGIN_FAILED.value in type_values
    assert SecurityEventSeverity.CRITICAL.value in severity_values
    assert SecurityEventStatus.FALSE_POSITIVE.value in status_values
