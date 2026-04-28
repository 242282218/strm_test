from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, Field


T = TypeVar("T")


class BaseResponse(BaseModel, Generic[T]):
    """
    通用 API 响应结构
    """

    code: int = Field(default=200, description="业务状态码")
    message: str = Field(default="Success", description="响应消息")
    data: T | None = Field(default=None, description="业务数据")
    request_id: str | None = Field(default=None, description="请求ID")
    timestamp: datetime = Field(default_factory=datetime.now, description="响应时间")


class PageMeta(BaseModel):
    """分页元数据"""

    total: int
    page: int
    size: int
    pages: int


class PageResponse(BaseResponse[T], Generic[T]):
    """
    分页 API 响应结构
    """

    meta: PageMeta
