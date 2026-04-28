from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TaskBase(BaseModel):
    task_type: str = Field(..., description="任务类型: strm_generation, scrape, file_sync")
    priority: str = Field("normal", description="优先级")
    params: dict[str, Any] = Field(default_factory=dict, description="任务参数")


class TaskCreate(TaskBase):
    pass


class TaskLog(BaseModel):
    ts: float
    level: str
    message: str


class TaskResponse(TaskBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    progress: int
    total_items: int
    processed_items: int
    error_message: str | None
    logs: list[Any] = []
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
