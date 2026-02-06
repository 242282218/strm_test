from fastapi import Request, status
from fastapi.responses import JSONResponse
from enum import IntEnum
from app.core.response import ErrorResponse
from app.core.logging import get_logger

class AppErrorCode(IntEnum):
    """全局错误码定义"""
    SUCCESS = 0
    UNKNOWN_ERROR = 1000
    
    # 认证/权限 1001-1999
    AUTH_ERROR = 1001
    PERMISSION_DENIED = 1002
    
    # 参数校验 2001-2999
    VALIDATION_ERROR = 2001
    RESOURCE_NOT_FOUND = 2004
    RESOURCE_ALREADY_EXISTS = 2009
    
    # 外部服务 3001-3999
    EXTERNAL_API_ERROR = 3001
    TMDB_API_ERROR = 3002
    QUARK_API_ERROR = 3003
    
    # 系统内部 4001-4999
    SYSTEM_ERROR = 4001
    DB_ERROR = 4002
    IO_ERROR = 4003
    
    # 业务逻辑 5001-5999
    TASK_EXECUTION_ERROR = 5001
    TASK_TIMEOUT = 5002

class AppException(Exception):
    """通用业务异常"""
    def __init__(
        self, 
        code: AppErrorCode = AppErrorCode.SYSTEM_ERROR,
        message: str = "System Error",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        data: any = None
    ):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.data = data
        super().__init__(self.message)

logger = get_logger(__name__)

async def app_exception_handler(request: Request, exc: AppException):
    """全局业务异常处理器"""
    error_response = ErrorResponse(
        code=exc.status_code,
        message=exc.message,
        error_code=str(exc.code),
        request_id=getattr(request.state, "request_id", None),
        data=exc.data,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response.model_dump(),
    )

async def general_exception_handler(request: Request, exc: Exception):
    """兜底异常处理器"""
    logger.exception("Unhandled Exception: %s", exc)
    error_response = ErrorResponse(
        code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        message="服务器内部错误",
        error_code=str(AppErrorCode.UNKNOWN_ERROR),
        request_id=getattr(request.state, "request_id", None),
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_response.model_dump(),
    )
