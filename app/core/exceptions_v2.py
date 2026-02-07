# -*- coding: utf-8 -*-
"""
增强版异常处理模块

提供更细致的错误分类和前端友好的错误信息
"""

from typing import Any, Optional, Dict
from fastapi import Request, status
from fastapi.responses import JSONResponse
from app.core.error_codes import ErrorCode, get_error_message, get_http_status
from app.core.logging import get_logger

logger = get_logger(__name__)


class AppExceptionV2(Exception):
    """
    增强版应用异常基类
    
    Attributes:
        code: 错误码
        message: 错误消息
        detail: 详细错误信息（用于调试）
        data: 附加数据
        retry_after: 建议重试时间（秒）
    """
    
    def __init__(
        self,
        code: ErrorCode = ErrorCode.SYSTEM_INTERNAL_ERROR,
        message: Optional[str] = None,
        detail: Optional[str] = None,
        data: Optional[Dict] = None,
        retry_after: Optional[int] = None,
        cause: Optional[Exception] = None
    ):
        self.code = code
        self.message = message or get_error_message(code)["message"]
        self.detail = detail
        self.data = data or {}
        self.retry_after = retry_after
        self.cause = cause
        
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式（用于API响应）"""
        error_info = get_error_message(self.code)
        
        result = {
            "code": self.code.value,
            "error_code": self.code.name,
            "title": error_info["title"],
            "message": self.message,
            "action": error_info["action"],
            "category": (self.code.value // 100) * 100,
        }
        
        # 仅在开发环境或明确需要时返回详细错误
        if self.detail:
            result["detail"] = self.detail
        
        if self.data:
            result["data"] = self.data
        
        if self.retry_after:
            result["retry_after"] = self.retry_after
        
        return result


# ==================== 认证异常 ====================

class AuthException(AppExceptionV2):
    """认证相关异常基类"""
    def __init__(self, code: ErrorCode = ErrorCode.AUTH_UNAUTHORIZED, **kwargs):
        super().__init__(code=code, **kwargs)


class CookieInvalidException(AuthException):
    """Cookie失效异常（夸克/115等）"""
    def __init__(self, service: str = "网盘", **kwargs):
        super().__init__(
            code=ErrorCode.AUTH_COOKIE_INVALID,
            message=f"{service}登录已失效，请更新Cookie",
            **kwargs
        )


# ==================== 外部服务异常 ====================

class ExternalServiceException(AppExceptionV2):
    """外部服务异常基类"""
    def __init__(self, code: ErrorCode = ErrorCode.EXTERNAL_API_ERROR, **kwargs):
        super().__init__(code=code, **kwargs)


class TimeoutException(ExternalServiceException):
    """请求超时异常"""
    def __init__(self, service: str = "外部服务", timeout: float = None, **kwargs):
        message = f"{service}请求超时"
        if timeout:
            message += f" ({timeout}秒)"
        
        super().__init__(
            code=ErrorCode.EXTERNAL_TIMEOUT,
            message=message,
            **kwargs
        )


class RateLimitException(ExternalServiceException):
    """API频率限制异常 (429)"""
    def __init__(self, service: str = "API", retry_after: int = 60, **kwargs):
        super().__init__(
            code=ErrorCode.EXTERNAL_RATE_LIMIT,
            message=f"{service}调用频率超限，请{retry_after}秒后重试",
            retry_after=retry_after,
            **kwargs
        )


class ServiceUnavailableException(ExternalServiceException):
    """服务不可用异常 (503)"""
    def __init__(self, service: str = "服务", retry_after: int = 300, **kwargs):
        super().__init__(
            code=ErrorCode.EXTERNAL_SERVICE_UNAVAILABLE,
            message=f"{service}暂时不可用，请稍后重试",
            retry_after=retry_after,
            **kwargs
        )


class QuarkAPIException(ExternalServiceException):
    """夸克网盘API异常"""
    def __init__(self, message: str = None, error_code: int = None, **kwargs):
        detail = None
        if error_code:
            detail = f"夸克错误码: {error_code}"
        
        super().__init__(
            code=ErrorCode.EXTERNAL_QUARK_ERROR,
            message=message or "夸克网盘服务异常",
            detail=detail,
            **kwargs
        )


class Open115Exception(ExternalServiceException):
    """115网盘API异常"""
    def __init__(self, message: str = None, error_code: int = None, **kwargs):
        detail = None
        if error_code:
            detail = f"115错误码: {error_code}"
        
        super().__init__(
            code=ErrorCode.EXTERNAL_115_ERROR,
            message=message or "115网盘服务异常",
            detail=detail,
            **kwargs
        )


class NetworkException(ExternalServiceException):
    """网络错误异常"""
    def __init__(self, message: str = None, **kwargs):
        super().__init__(
            code=ErrorCode.EXTERNAL_NETWORK_ERROR,
            message=message or "网络连接异常",
            **kwargs
        )


# ==================== 业务异常 ====================

class BusinessException(AppExceptionV2):
    """业务逻辑异常基类"""
    def __init__(self, code: ErrorCode = ErrorCode.BUSINESS_TASK_FAILED, **kwargs):
        super().__init__(code=code, **kwargs)


class TaskTimeoutException(BusinessException):
    """任务执行超时"""
    def __init__(self, task_name: str = "任务", **kwargs):
        super().__init__(
            code=ErrorCode.BUSINESS_TASK_TIMEOUT,
            message=f"{task_name}执行超时",
            **kwargs
        )


class RenameException(BusinessException):
    """重命名失败异常"""
    def __init__(self, filename: str = None, reason: str = None, **kwargs):
        message = "文件重命名失败"
        if filename:
            message = f"文件 '{filename}' 重命名失败"
        if reason:
            message += f": {reason}"
        
        super().__init__(
            code=ErrorCode.BUSINESS_RENAME_FAILED,
            message=message,
            **kwargs
        )


class ScrapeException(BusinessException):
    """刮削失败异常"""
    def __init__(self, filename: str = None, reason: str = None, **kwargs):
        message = "影片信息刮削失败"
        if filename:
            message = f"'{filename}' 刮削失败"
        if reason:
            message += f": {reason}"
        
        super().__init__(
            code=ErrorCode.BUSINESS_SCRAPE_FAILED,
            message=message,
            **kwargs
        )


# ==================== 异常处理器 ====================

async def app_exception_v2_handler(request: Request, exc: AppExceptionV2) -> JSONResponse:
    """处理增强版应用异常"""
    request_id = getattr(request.state, "request_id", None)
    
    # 根据错误级别记录日志
    http_status = get_http_status(exc.code)
    if http_status >= 500:
        logger.error(
            f"AppException: {exc.code.name} | {exc.message} | "
            f"request_id={request_id} | detail={exc.detail}",
            exc_info=exc.cause
        )
    elif http_status >= 400:
        logger.warning(
            f"AppException: {exc.code.name} | {exc.message} | request_id={request_id}"
        )
    
    # 构建响应
    content = exc.to_dict()
    content["request_id"] = request_id
    
    headers = {}
    if exc.retry_after:
        headers["Retry-After"] = str(exc.retry_after)
    
    return JSONResponse(
        status_code=http_status,
        content=content,
        headers=headers
    )


async def external_exception_handler(request: Request, exc: ExternalServiceException) -> JSONResponse:
    """专门处理外部服务异常"""
    request_id = getattr(request.state, "request_id", None)
    
    # 记录详细的错误信息，便于排查
    logger.error(
        f"External service error: {exc.code.name} | Service: {exc.message} | "
        f"request_id={request_id}",
        exc_info=exc.cause
    )
    
    content = exc.to_dict()
    content["request_id"] = request_id
    
    # 添加建议操作
    content["suggestions"] = [
        "检查网络连接",
        "确认服务配置正确",
        "稍后重试"
    ]
    
    headers = {}
    if exc.retry_after:
        headers["Retry-After"] = str(exc.retry_after)
    
    return JSONResponse(
        status_code=get_http_status(exc.code),
        content=content,
        headers=headers
    )


# ==================== 辅助函数 ====================

def convert_http_exception(status_code: int, detail: str) -> AppExceptionV2:
    """
    将HTTP异常转换为应用异常
    
    Args:
        status_code: HTTP状态码
        detail: 错误详情
        
    Returns:
        对应的应用异常
    """
    if status_code == 429:
        return RateLimitException(retry_after=60)
    elif status_code == 503:
        return ServiceUnavailableException()
    elif status_code == 504:
        return TimeoutException()
    elif status_code == 401:
        return AuthException(code=ErrorCode.AUTH_UNAUTHORIZED)
    elif status_code == 403:
        return AuthException(code=ErrorCode.AUTH_FORBIDDEN)
    else:
        return AppExceptionV2(
            code=ErrorCode.EXTERNAL_API_ERROR,
            message=f"外部服务错误 (HTTP {status_code})",
            detail=detail
        )


def convert_aiohttp_error(error: Exception, service: str = "外部服务") -> AppExceptionV2:
    """
    转换aiohttp错误为应用异常
    
    Args:
        error: aiohttp异常
        service: 服务名称
        
    Returns:
        对应的应用异常
    """
    error_str = str(error).lower()
    
    if "timeout" in error_str:
        return TimeoutException(service=service)
    elif "connection" in error_str or "network" in error_str:
        return NetworkException()
    elif "dns" in error_str:
        return ExternalServiceException(
            code=ErrorCode.EXTERNAL_DNS_ERROR,
            message="DNS解析失败"
        )
    elif "ssl" in error_str or "certificate" in error_str:
        return ExternalServiceException(
            code=ErrorCode.EXTERNAL_SSL_ERROR,
            message="SSL证书验证失败"
        )
    else:
        return ExternalServiceException(
            message=f"{service}请求失败"
        )
