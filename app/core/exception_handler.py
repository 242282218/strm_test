"""
异常处理中间件
"""

from fastapi import Request, status
from fastapi.responses import JSONResponse
from app.core.logging import get_logger
from app.core.response import ErrorResponse

logger = get_logger(__name__)


async def exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """全局异常处理"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    
    error_response = ErrorResponse(
        code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        message="Internal server error",
        detail=str(exc)
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_response.model_dump()
    )


async def http_exception_handler(request: Request, exc) -> JSONResponse:
    """HTTP异常处理"""
    logger.warning(f"HTTP exception: {exc.status_code} - {exc.detail}")
    
    error_response = ErrorResponse(
        code=exc.status_code,
        message="Request failed",
        detail=exc.detail
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response.model_dump()
    )


async def validation_exception_handler(request: Request, exc) -> JSONResponse:
    """验证异常处理"""
    logger.warning(f"Validation exception: {exc}")
    
    error_response = ErrorResponse(
        code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        message="Validation failed",
        detail=str(exc)
    )
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=error_response.model_dump()
    )
