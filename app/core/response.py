"""
统一API响应格式
"""

from typing import Generic, TypeVar, Optional, Any
from pydantic import BaseModel

T = TypeVar('T')


class ApiResponse(BaseModel, Generic[T]):
    """统一API响应格式"""
    code: int = 200
    message: str = "success"
    data: Optional[T] = None
    timestamp: int = 0

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        import time
        self.timestamp = int(time.time())


class PaginationResponse(BaseModel, Generic[T]):
    """分页响应格式"""
    items: list[T] = []
    total: int = 0
    page: int = 1
    page_size: int = 20


class ErrorResponse(BaseModel):
    """错误响应格式"""
    code: int
    message: str
    detail: Optional[str] = None
    timestamp: int = 0

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        import time
        self.timestamp = int(time.time())


def success_response(data: Any = None, message: str = "success") -> ApiResponse:
    """成功响应"""
    return ApiResponse(data=data, message=message)


def error_response(code: int, message: str, detail: str = None) -> ErrorResponse:
    """错误响应"""
    return ErrorResponse(code=code, message=message, detail=detail)
