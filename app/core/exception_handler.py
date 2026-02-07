"""
异常处理中间件
"""

from fastapi import Request, status, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from app.core.logging import get_logger
from app.core.response import ErrorResponse
from app.core.security import redact_sensitive
from app.core.constants import REQUEST_ID_HEADER
from app.core.validators import InputValidationError

logger = get_logger(__name__)

_STATUS_MESSAGE = {
    status.HTTP_400_BAD_REQUEST: "请求参数错误",
    status.HTTP_401_UNAUTHORIZED: "未授权",
    status.HTTP_403_FORBIDDEN: "禁止访问",
    status.HTTP_404_NOT_FOUND: "资源不存在",
    status.HTTP_409_CONFLICT: "请求冲突",
    status.HTTP_422_UNPROCESSABLE_ENTITY: "参数校验失败",
}

_STATUS_CODE = {
    status.HTTP_400_BAD_REQUEST: "ERR_BAD_REQUEST",
    status.HTTP_401_UNAUTHORIZED: "ERR_UNAUTHORIZED",
    status.HTTP_403_FORBIDDEN: "ERR_FORBIDDEN",
    status.HTTP_404_NOT_FOUND: "ERR_NOT_FOUND",
    status.HTTP_409_CONFLICT: "ERR_CONFLICT",
    status.HTTP_422_UNPROCESSABLE_ENTITY: "ERR_VALIDATION",
    status.HTTP_500_INTERNAL_SERVER_ERROR: "ERR_INTERNAL",
}


def _get_request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def _sanitize_validation_errors(errors):
    sanitized = []
    for err in errors:
        sanitized.append(
            {
                "loc": err.get("loc"),
                "msg": err.get("msg"),
                "type": err.get("type"),
            }
        )
    return sanitized


async def exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """全局异常处理"""
    request_id = _get_request_id(request)
    logger.exception(f"Unhandled exception: {exc} | request_id={request_id}")

    error_response = ErrorResponse(
        code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        message="服务器内部错误",
        error_code=_STATUS_CODE[status.HTTP_500_INTERNAL_SERVER_ERROR],
        request_id=request_id,
    )

    response = JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_response.model_dump(),
    )
    if request_id:
        response.headers[REQUEST_ID_HEADER] = request_id
    return response


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """HTTP异常处理"""
    request_id = _get_request_id(request)
    status_code = exc.status_code

    if status_code >= 500:
        logger.exception(f"HTTP exception: {status_code} | request_id={request_id}")
        message = "服务器内部错误"
        # Return sanitized detail for easier debugging in self-hosted deployments.
        # Sensitive values are redacted.
        detail = redact_sensitive(str(exc.detail)) if exc.detail else None
    else:
        logger.warning(f"HTTP exception: {status_code} - {exc.detail} | request_id={request_id}")
        message = _STATUS_MESSAGE.get(status_code, "请求失败")
        detail = redact_sensitive(str(exc.detail)) if exc.detail else None

    error_response = ErrorResponse(
        code=status_code,
        message=message,
        detail=detail,
        error_code=_STATUS_CODE.get(status_code, "ERR_UNKNOWN"),
        request_id=request_id,
    )

    response = JSONResponse(
        status_code=status_code,
        content=error_response.model_dump(),
    )
    if request_id:
        response.headers[REQUEST_ID_HEADER] = request_id
    return response


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """验证异常处理"""
    request_id = _get_request_id(request)
    logger.warning(f"Validation exception: {exc} | request_id={request_id}")

    errors = _sanitize_validation_errors(exc.errors())

    error_response = ErrorResponse(
        code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        message=_STATUS_MESSAGE[status.HTTP_422_UNPROCESSABLE_ENTITY],
        error_code=_STATUS_CODE[status.HTTP_422_UNPROCESSABLE_ENTITY],
        request_id=request_id,
        errors=errors,
    )

    response = JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=error_response.model_dump(),
    )
    if request_id:
        response.headers[REQUEST_ID_HEADER] = request_id
    return response


async def input_validation_exception_handler(request: Request, exc: InputValidationError) -> JSONResponse:
    """输入校验异常处理"""
    request_id = _get_request_id(request)
    logger.warning(f"Input validation error: {exc} | request_id={request_id}")

    error_response = ErrorResponse(
        code=status.HTTP_400_BAD_REQUEST,
        message=_STATUS_MESSAGE[status.HTTP_400_BAD_REQUEST],
        detail=redact_sensitive(str(exc)),
        error_code=_STATUS_CODE[status.HTTP_400_BAD_REQUEST],
        request_id=request_id,
    )

    response = JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=error_response.model_dump(),
    )
    if request_id:
        response.headers[REQUEST_ID_HEADER] = request_id
    return response
