from __future__ import annotations

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.api.security as security_api
from app.core.dependencies import get_admin_user


class DummyEvent:
    def __init__(self, event_id: int = 1) -> None:
        self.event_id = event_id

    def to_dict(self) -> dict:
        return {
            "id": self.event_id,
            "event_type": "unauthorized_access",
            "severity": "medium",
            "status": "acknowledged",
            "user_id": None,
            "username": None,
            "ip_address": "127.0.0.1",
            "user_agent": "pytest",
            "title": "Unauthorized access",
            "description": "test",
            "details": {},
            "request_path": "/api/security/events/1/acknowledge",
            "request_method": "POST",
            "acknowledged_by": 7,
            "acknowledged_at": "2026-03-12T00:00:00",
            "resolved_by": None,
            "resolved_at": None,
            "resolution_note": "handled",
            "created_at": "2026-03-12T00:00:00",
            "updated_at": "2026-03-12T00:00:00",
        }


class DummySecurityAuditService:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def acknowledge_event(self, db, event_id: int, user_id: int, note: str | None = None) -> DummyEvent:
        self.calls.append(
            {
                "db": db,
                "event_id": event_id,
                "user_id": user_id,
                "note": note,
            }
        )
        return DummyEvent(event_id)


def test_acknowledge_uses_authenticated_admin_identity() -> None:
    app = FastAPI()
    app.include_router(security_api.router)

    fake_service = DummySecurityAuditService()
    fake_db = object()

    app.dependency_overrides[security_api.get_db] = lambda: fake_db
    app.dependency_overrides[get_admin_user] = lambda: SimpleNamespace(id=7, role="admin")

    original_factory = security_api.get_security_audit_service
    security_api.get_security_audit_service = lambda: fake_service
    try:
        client = TestClient(app)
        response = client.post("/api/security/events/5/acknowledge", json={"note": "handled"})
    finally:
        security_api.get_security_audit_service = original_factory

    assert response.status_code == 200
    assert fake_service.calls == [
        {
            "db": fake_db,
            "event_id": 5,
            "user_id": 7,
            "note": "handled",
        }
    ]


def test_events_endpoint_does_not_leak_internal_error_details() -> None:
    app = FastAPI()
    app.include_router(security_api.router)
    app.dependency_overrides[security_api.get_db] = lambda: object()
    app.dependency_overrides[get_admin_user] = lambda: SimpleNamespace(id=7, role="admin")

    original_factory = security_api.get_security_audit_service
    security_api.get_security_audit_service = lambda: SimpleNamespace(
        get_security_events=lambda **kwargs: (_ for _ in ()).throw(
            RuntimeError("security events exploded: secret stack")
        )
    )
    try:
        client = TestClient(app)
        response = client.get("/api/security/events")
    finally:
        security_api.get_security_audit_service = original_factory

    assert response.status_code == 500
    assert response.json() == {"detail": "Failed to get security events"}


def test_summary_endpoint_does_not_leak_internal_error_details() -> None:
    app = FastAPI()
    app.include_router(security_api.router)
    app.dependency_overrides[security_api.get_db] = lambda: object()
    app.dependency_overrides[get_admin_user] = lambda: SimpleNamespace(id=7, role="admin")

    original_factory = security_api.get_security_audit_service
    security_api.get_security_audit_service = lambda: SimpleNamespace(
        get_security_summary=lambda **kwargs: (_ for _ in ()).throw(RuntimeError("summary exploded: secret stack"))
    )
    try:
        client = TestClient(app)
        response = client.get("/api/security/summary")
    finally:
        security_api.get_security_audit_service = original_factory

    assert response.status_code == 500
    assert response.json() == {"detail": "Failed to get security summary"}
