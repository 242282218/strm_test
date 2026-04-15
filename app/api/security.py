"""
Security event API endpoints.

Provides query, management, and summary endpoints for security events.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from app.core.db import SessionLocal
from app.core.dependencies import get_admin_user
from app.core.logging import get_logger
from app.models.security_event import (
    SecurityEvent,
    SecurityEventSeverity,
    SecurityEventStatus,
    SecurityEventType,
)
from app.models.user import User
from app.services.security_audit_service import get_security_audit_service


logger = get_logger(__name__)

router = APIRouter(
    prefix="/api/security",
    tags=["Security"],
    dependencies=[Depends(get_admin_user)],
)


class SecurityEventResponse(BaseModel):
    """Security event response model."""

    id: int
    event_type: str
    severity: str
    status: str
    user_id: int | None = None
    username: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    title: str
    description: str | None = None
    details: dict | None = None
    request_path: str | None = None
    request_method: str | None = None
    acknowledged_by: int | None = None
    acknowledged_at: str | None = None
    resolved_by: int | None = None
    resolved_at: str | None = None
    resolution_note: str | None = None
    created_at: str
    updated_at: str

    model_config = ConfigDict(from_attributes=True)


class SecurityEventListResponse(BaseModel):
    """Security event list response model."""

    total: int
    events: list[SecurityEventResponse]


class SecuritySummaryResponse(BaseModel):
    """Security event summary response model."""

    total_events: int
    by_type: dict
    by_severity: dict
    by_status: dict
    suspicious_ips: list[dict]
    period_days: int


class AcknowledgeRequest(BaseModel):
    """Acknowledge request payload."""

    note: str | None = Field(None, description="Acknowledgement note")


class ResolveRequest(BaseModel):
    """Resolve request payload."""

    note: str | None = Field(None, description="Resolution note")


def get_db():
    """Yield a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/events", response_model=SecurityEventListResponse)
async def get_security_events(
    limit: int = Query(50, ge=1, le=500, description="Result limit"),
    event_type: str | None = Query(None, description="Event type filter"),
    severity: str | None = Query(None, description="Severity filter"),
    status: str | None = Query(None, description="Status filter"),
    user_id: int | None = Query(None, description="User ID filter"),
    ip_address: str | None = Query(None, description="IP address filter"),
    db=Depends(get_db),
):
    """Return security events with optional filters."""
    try:
        security_audit = get_security_audit_service()

        event_type_enum = None
        if event_type:
            try:
                event_type_enum = SecurityEventType(event_type)
            except ValueError:
                pass

        severity_enum = None
        if severity:
            try:
                severity_enum = SecurityEventSeverity(severity)
            except ValueError:
                pass

        status_enum = None
        if status:
            try:
                status_enum = SecurityEventStatus(status)
            except ValueError:
                pass

        events = security_audit.get_security_events(
            db=db,
            limit=limit,
            event_type=event_type_enum,
            severity=severity_enum,
            status=status_enum,
            user_id=user_id,
            ip_address=ip_address,
        )

        return SecurityEventListResponse(
            total=len(events),
            events=[SecurityEventResponse(**event.to_dict()) for event in events],
        )
    except Exception as exc:
        logger.error(f"Failed to get security events: {exc}")
        raise HTTPException(status_code=500, detail="Failed to get security events")


@router.get("/events/{event_id}", response_model=SecurityEventResponse)
async def get_security_event(event_id: int, db=Depends(get_db)):
    """Return details for a single security event."""
    event = SecurityEvent.get_by_id(db, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    return SecurityEventResponse(**event.to_dict())


@router.post("/events/{event_id}/acknowledge", response_model=SecurityEventResponse)
async def acknowledge_security_event(
    event_id: int,
    request: AcknowledgeRequest,
    db=Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    """Acknowledge a security event as the authenticated admin."""
    security_audit = get_security_audit_service()
    event = security_audit.acknowledge_event(
        db=db,
        event_id=event_id,
        user_id=current_user.id,
        note=request.note,
    )

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    return SecurityEventResponse(**event.to_dict())


@router.post("/events/{event_id}/resolve", response_model=SecurityEventResponse)
async def resolve_security_event(
    event_id: int,
    request: ResolveRequest,
    db=Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    """Resolve a security event as the authenticated admin."""
    security_audit = get_security_audit_service()
    event = security_audit.resolve_event(
        db=db,
        event_id=event_id,
        user_id=current_user.id,
        note=request.note,
    )

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    return SecurityEventResponse(**event.to_dict())


@router.post("/events/{event_id}/false-positive", response_model=SecurityEventResponse)
async def mark_false_positive(
    event_id: int,
    request: ResolveRequest,
    db=Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    """Mark a security event as false positive as the authenticated admin."""
    event = SecurityEvent.get_by_id(db, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    event.mark_false_positive(db, current_user.id, request.note)
    return SecurityEventResponse(**event.to_dict())


@router.get("/summary", response_model=SecuritySummaryResponse)
async def get_security_summary(
    days: int = Query(7, ge=1, le=30, description="Summary window in days"),
    db=Depends(get_db),
):
    """Return security event summary statistics."""
    try:
        security_audit = get_security_audit_service()
        summary = security_audit.get_security_summary(db=db, days=days)
        return SecuritySummaryResponse(**summary)
    except Exception as exc:
        logger.error(f"Failed to get security summary: {exc}")
        raise HTTPException(status_code=500, detail="Failed to get security summary")


@router.get("/event-types")
async def get_event_types():
    """Return available security event types."""
    return {"types": [{"value": event.value, "label": event.name} for event in SecurityEventType]}


@router.get("/severities")
async def get_severities():
    """Return available severity levels."""
    return {"severities": [{"value": severity.value, "label": severity.name} for severity in SecurityEventSeverity]}


@router.get("/statuses")
async def get_statuses():
    """Return available event statuses."""
    return {"statuses": [{"value": status.value, "label": status.name} for status in SecurityEventStatus]}
