"""
统一异常处理中间件

提供所有异常的统一处理:
- AppException: 应用异常
- HTTPException: HTTP异常
- RequestValidationError: 请求验证异常
- InputValidationError: 输入校验异常
- Exception: 兜底异常
"""

from fastapi import HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.constants import REQUEST_ID_HEADER
from app.core.exceptions import AppException, ExternalServiceException
from app.core.logging import get_logger
from app.core.response import ErrorResponse
from app.core.security import redact_sensitive
from app.core.validators import InputValidationError


logger = get_logger(__name__)


# ==================== 状态码映射 ====================
# Why: FastAPI/Starlette expose different 422 names across versions.
HTTP_422 = getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422)

_STATUS_MESSAGE = {
    status.HTTP_400_BAD_REQUEST: "请求参数错误",
    status.HTTP_401_UNAUTHORIZED: "未授权",
    status.HTTP_403_FORBIDDEN: "禁止访问",
    status.HTTP_404_NOT_FOUND: "资源不存在",
    status.HTTP_409_CONFLICT: "请求冲突",
    HTTP_422: "参数校验失败",
    status.HTTP_502_BAD_GATEWAY: "上游服务异常",
    status.HTTP_503_SERVICE_UNAVAILABLE: "服务暂时不可用",
    status.HTTP_504_GATEWAY_TIMEOUT: "上游服务超时",
}

_STATUS_CODE = {
    status.HTTP_400_BAD_REQUEST: "ERR_BAD_REQUEST",
    status.HTTP_401_UNAUTHORIZED: "ERR_UNAUTHORIZED",
    status.HTTP_403_FORBIDDEN: "ERR_FORBIDDEN",
    status.HTTP_404_NOT_FOUND: "ERR_NOT_FOUND",
    status.HTTP_409_CONFLICT: "ERR_CONFLICT",
    HTTP_422: "ERR_VALIDATION",
    status.HTTP_502_BAD_GATEWAY: "ERR_BAD_GATEWAY",
    status.HTTP_503_SERVICE_UNAVAILABLE: "ERR_SERVICE_UNAVAILABLE",
    status.HTTP_504_GATEWAY_TIMEOUT: "ERR_GATEWAY_TIMEOUT",
    status.HTTP_500_INTERNAL_SERVER_ERROR: "ERR_INTERNAL",
}

_PASSTHROUGH_HTTP_SERVER_ERRORS = {
    status.HTTP_502_BAD_GATEWAY,
    status.HTTP_503_SERVICE_UNAVAILABLE,
    status.HTTP_504_GATEWAY_TIMEOUT,
}


# ==================== 辅助函数 ====================


def _get_request_id(request: Request) -> str | None:
    """获取请求ID"""
    return getattr(request.state, "request_id", None)


def _sanitize_validation_errors(errors):
    """清理验证错误信息"""
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


# ==================== 异常处理器 ====================


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """
    统一应用异常处理器

    处理所有 AppException 及其子类
    """
    request_id = _get_request_id(request)
    http_status = exc.status_code

    # 根据错误级别记录日志
    if http_status >= 500:
        logger.error(
            f"AppException: {exc.code.name} | {exc.message} | request_id={request_id} | detail={exc.detail}",
            exc_info=exc.cause,
        )
    elif http_status >= 400:
        logger.warning(f"AppException: {exc.code.name} | {exc.message} | request_id={request_id}")

    # 构建响应
    content = exc.to_dict()
    content["request_id"] = request_id

    # 外部服务异常添加建议
    if isinstance(exc, ExternalServiceException):
        content["suggestions"] = ["检查网络连接", "确认服务配置正确", "稍后重试"]

    headers = {}
    if exc.retry_after:
        headers["Retry-After"] = str(exc.retry_after)

    response = JSONResponse(
        status_code=http_status,
        content=content,
        headers=headers if headers else None,
    )

    if request_id:
        response.headers[REQUEST_ID_HEADER] = request_id

    return response


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """HTTP异常处理"""
    request_id = _get_request_id(request)
    status_code = exc.status_code

    if status_code >= 500 and status_code not in _PASSTHROUGH_HTTP_SERVER_ERRORS:
        logger.exception(f"HTTP exception: {status_code} | request_id={request_id}")
        message = "服务器内部错误"
        detail = None
    elif status_code in _PASSTHROUGH_HTTP_SERVER_ERRORS:
        # Why: explicit gateway/service errors are operational contracts, not hidden internal faults.
        logger.warning(f"HTTP exception: {status_code} - {exc.detail} | request_id={request_id}")
        message = _STATUS_MESSAGE[status_code]
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
        code=HTTP_422,
        message=_STATUS_MESSAGE[HTTP_422],
        error_code=_STATUS_CODE[HTTP_422],
        request_id=request_id,
        errors=errors,
    )

    response = JSONResponse(
        status_code=HTTP_422,
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


async def exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """全局异常处理（兜底）"""
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


# ==================== 向后兼容别名 ====================
# 保留旧的处理器名称
external_exception_handler = app_exception_handler
