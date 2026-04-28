from datetime import datetime, timedelta

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.task import TASK_ACTIVE_STATES, TASK_LEASEABLE_STATES, TASK_TERMINAL_STATES, Task
from app.schemas.task import TaskCreate


def _coerce_positive_int(value, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(1, parsed)


class TaskService:
    def __init__(self, db: Session):
        self.db = db

    def get_tasks(self, skip: int = 0, limit: int = 20, status: str | None = None):
        query = self.db.query(Task)
        if status:
            query = query.filter(Task.status == status)
        return query.order_by(Task.created_at.desc()).offset(skip).limit(limit).all()

    def get_task(self, task_id: int):
        return self.db.query(Task).filter(Task.id == task_id).first()

    def create_task(self, task_in: TaskCreate) -> Task:
        params = dict(task_in.params or {})
        task = Task(
            task_type=task_in.task_type,
            priority=task_in.priority,
            params=params,
            status="pending",
            max_attempts=_coerce_positive_int(params.get("max_attempts"), 3),
            idempotency_key=params.get("idempotency_key"),
        )
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return task

    def claim_next_task(self, lease_owner: str, lease_seconds: int = 300, now: datetime | None = None) -> Task | None:
        if not lease_owner:
            raise ValueError("lease_owner is required")

        now = now or datetime.now()
        lease_until = now + timedelta(seconds=lease_seconds)
        candidate = (
            self.db.query(Task)
            .filter(
                Task.status.in_(TASK_LEASEABLE_STATES),
                or_(Task.next_run_at.is_(None), Task.next_run_at <= now),
            )
            .order_by(Task.created_at.asc(), Task.id.asc())
            .first()
        )
        if candidate is None:
            return None

        updated = (
            self.db.query(Task)
            .filter(
                Task.id == candidate.id,
                Task.status.in_(TASK_LEASEABLE_STATES),
                or_(Task.next_run_at.is_(None), Task.next_run_at <= now),
            )
            .update(
                {
                    Task.status: "leased",
                    Task.lease_owner: lease_owner,
                    Task.lease_until: lease_until,
                    Task.heartbeat_at: now,
                    Task.started_at: now,
                    Task.attempt: func.coalesce(Task.attempt, 0) + 1,
                },
                synchronize_session=False,
            )
        )
        if updated != 1:
            self.db.rollback()
            return None

        self.db.commit()
        return self.get_task(candidate.id)

    def heartbeat_task(
        self,
        task_id: int,
        lease_owner: str,
        lease_seconds: int = 300,
        now: datetime | None = None,
    ) -> bool:
        now = now or datetime.now()
        updated = (
            self.db.query(Task)
            .filter(
                Task.id == task_id,
                Task.lease_owner == lease_owner,
                Task.status.in_(TASK_ACTIVE_STATES | {"leased"}),
            )
            .update(
                {
                    Task.heartbeat_at: now,
                    Task.lease_until: now + timedelta(seconds=lease_seconds),
                },
                synchronize_session=False,
            )
        )
        self.db.commit()
        return updated == 1

    def recover_expired_leases(self, now: datetime | None = None) -> int:
        now = now or datetime.now()
        expired_tasks = (
            self.db.query(Task)
            .filter(
                Task.status.in_(TASK_ACTIVE_STATES | {"leased", "cancel_requested"}),
                Task.lease_until.is_not(None),
                Task.lease_until <= now,
            )
            .all()
        )

        recovered = 0
        for task in expired_tasks:
            if task.status == "cancel_requested":
                task.status = "cancelled"
                task.completed_at = now
                task.error_message = "Cancelled after worker lease expired"
            elif int(task.attempt or 0) >= int(task.max_attempts or 1):
                task.status = "failed"
                task.completed_at = now
                task.error_message = "Task lease expired after max attempts"
            else:
                task.status = "retry_scheduled"
                task.next_run_at = now
                task.error_message = "Task lease expired; retry scheduled"

            task.lease_owner = None
            task.lease_until = None
            task.heartbeat_at = None
            recovered += 1

        if recovered:
            self.db.commit()
        return recovered

    def record_task_failure(
        self,
        task_id: int,
        lease_owner: str,
        error_message: str,
        now: datetime | None = None,
        base_delay_seconds: int = 30,
        max_delay_seconds: int = 3600,
    ) -> bool:
        task = self.get_task(task_id)
        if not task or task.lease_owner != lease_owner or task.status in TASK_TERMINAL_STATES:
            return False

        now = now or datetime.now()
        if int(task.attempt or 0) >= int(task.max_attempts or 1):
            task.status = "failed"
            task.completed_at = now
        else:
            retry_delay = min(base_delay_seconds * (2 ** max(int(task.attempt or 1) - 1, 0)), max_delay_seconds)
            task.status = "retry_scheduled"
            task.next_run_at = now + timedelta(seconds=retry_delay)

        task.error_message = error_message
        task.lease_owner = None
        task.lease_until = None
        task.heartbeat_at = None
        self.db.commit()
        return True

    def cancel_task(self, task_id: int) -> bool:
        task = self.get_task(task_id)
        if not task:
            return False

        if task.status in TASK_TERMINAL_STATES:
            return False

        if task.status in TASK_ACTIVE_STATES | {"leased"}:
            task.status = "cancel_requested"
            task.error_message = "Cancel requested by user"
        elif task.status != "cancel_requested":
            task.status = "cancelled"
            task.completed_at = datetime.now()
            task.error_message = "Cancelled by user"

        self.db.commit()
        return True

    def delete_task(self, task_id: int) -> bool:
        task = self.get_task(task_id)
        if not task:
            return False
        self.db.delete(task)
        self.db.commit()
        return True
