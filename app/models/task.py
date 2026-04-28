from sqlalchemy import JSON, Column, DateTime, Integer, String, Text
from sqlalchemy.sql import func

from app.core.db import Base


TASK_TERMINAL_STATES = {"completed", "partial_success", "failed", "cancelled"}
TASK_LEASEABLE_STATES = {"pending", "retry_scheduled"}
TASK_ACTIVE_STATES = {"leased", "running", "planning", "reviewing"}


class Task(Base):
    """异步任务模型"""

    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    task_type = Column(String, nullable=False, comment="任务类型")
    status = Column(
        String,
        default="pending",
        index=True,
        comment="Status: pending, leased, running, cancel_requested, retry_scheduled, completed, failed, cancelled",
    )
    priority = Column(String, default="normal", comment="优先级: low, normal, high")

    progress = Column(Integer, default=0, comment="进度百分比 0-100")
    total_items = Column(Integer, default=0, comment="总项目数")
    processed_items = Column(Integer, default=0, comment="已处理项目数")

    error_message = Column(Text, nullable=True, comment="错误信息")
    logs = Column(JSON, default=list, comment="执行日志")
    params = Column(JSON, default=dict, comment="任务参数")
    resume_cursor = Column(JSON, default=dict, comment="Durable resume cursor for long-running tasks")

    lease_owner = Column(String, nullable=True, index=True, comment="Worker holding the current execution lease")
    lease_until = Column(DateTime(timezone=True), nullable=True, index=True, comment="Lease expiry time")
    heartbeat_at = Column(DateTime(timezone=True), nullable=True, comment="Last worker heartbeat time")
    attempt = Column(Integer, default=0, nullable=False, comment="Execution attempt count")
    max_attempts = Column(Integer, default=3, nullable=False, comment="Maximum execution attempts")
    idempotency_key = Column(String, nullable=True, index=True, comment="Task idempotency key")
    next_run_at = Column(DateTime(timezone=True), nullable=True, index=True, comment="Next retry eligibility time")

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
