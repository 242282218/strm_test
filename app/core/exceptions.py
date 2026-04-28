"""
统一异常处理模块

提供完整的异常层次结构:
- AppException: 应用异常基类
- AuthException: 认证异常
- ExternalServiceException: 外部服务异常
- BusinessException: 业务逻辑异常
"""

from typing import Any

from app.core.error_codes import ErrorCode, get_error_message, get_http_status


class AppException(Exception):
    """
    应用异常基类

    Attributes:
        code: 错误码 (ErrorCode 枚举)
        message: 错误消息
        detail: 详细错误信息（用于调试）
        data: 附加数据
        retry_after: 建议重试时间（秒）
        cause: 原始异常
    """

    def __init__(
        self,
        code: ErrorCode = ErrorCode.SYSTEM_INTERNAL_ERROR,
        message: str | None = None,
        detail: str | None = None,
        data: dict | None = None,
        retry_after: int | None = None,
        cause: Exception | None = None,
        # 向后兼容参数
        status_code: int | None = None,
    ):
        self.code = code
        self.message = message or get_error_message(code)["message"]
        self.detail = detail
        self.data = data or {}
        self.retry_after = retry_after
        self.cause = cause

        # 向后兼容: 支持旧的 status_code 参数
        self._status_code = status_code

        super().__init__(self.message)

    @property
    def status_code(self) -> int:
        """获取 HTTP 状态码"""
        if self._status_code is not None:
            return self._status_code
        return get_http_status(self.code)

    def to_dict(self) -> dict[str, Any]:
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


class AuthException(AppException):
    """认证相关异常基类"""

    def __init__(self, code: ErrorCode = ErrorCode.AUTH_UNAUTHORIZED, **kwargs):
        super().__init__(code=code, **kwargs)


class CookieInvalidException(AuthException):
    """Cookie失效异常（夸克/115等）"""

    def __init__(self, service: str = "网盘", **kwargs):
        super().__init__(code=ErrorCode.AUTH_COOKIE_INVALID, message=f"{service}登录已失效，请更新Cookie", **kwargs)


# ==================== 外部服务异常 ====================


class ExternalServiceException(AppException):
    """外部服务异常基类"""

    def __init__(self, code: ErrorCode = ErrorCode.EXTERNAL_API_ERROR, **kwargs):
        super().__init__(code=code, **kwargs)


class TimeoutException(ExternalServiceException):
    """请求超时异常"""

    def __init__(self, service: str = "外部服务", timeout: float = None, **kwargs):
        message = f"{service}请求超时"
        if timeout:
            message += f" ({timeout}秒)"

        super().__init__(code=ErrorCode.EXTERNAL_TIMEOUT, message=message, **kwargs)


class RateLimitException(ExternalServiceException):
    """API频率限制异常 (429)"""

    def __init__(self, service: str = "API", retry_after: int = 60, **kwargs):
        super().__init__(
            code=ErrorCode.EXTERNAL_RATE_LIMIT,
            message=f"{service}调用频率超限，请{retry_after}秒后重试",
            retry_after=retry_after,
            **kwargs,
        )


class ServiceUnavailableException(ExternalServiceException):
    """服务不可用异常 (503)"""

    def __init__(self, service: str = "服务", retry_after: int = 300, **kwargs):
        super().__init__(
            code=ErrorCode.EXTERNAL_SERVICE_UNAVAILABLE,
            message=f"{service}暂时不可用，请稍后重试",
            retry_after=retry_after,
            **kwargs,
        )


class QuarkAPIException(ExternalServiceException):
    """夸克网盘API异常"""

    def __init__(self, message: str = None, error_code: int = None, **kwargs):
        detail = None
        if error_code:
            detail = f"夸克错误码: {error_code}"

        super().__init__(
            code=ErrorCode.EXTERNAL_QUARK_ERROR, message=message or "夸克网盘服务异常", detail=detail, **kwargs
        )


class Open115Exception(ExternalServiceException):
    """115网盘API异常"""

    def __init__(self, message: str = None, error_code: int = None, **kwargs):
        detail = None
        if error_code:
            detail = f"115错误码: {error_code}"

        super().__init__(
            code=ErrorCode.EXTERNAL_115_ERROR, message=message or "115网盘服务异常", detail=detail, **kwargs
        )


class NetworkException(ExternalServiceException):
    """网络错误异常"""

    def __init__(self, message: str = None, **kwargs):
        super().__init__(code=ErrorCode.EXTERNAL_NETWORK_ERROR, message=message or "网络连接异常", **kwargs)


# ==================== 业务异常 ====================


class BusinessException(AppException):
    """业务逻辑异常基类"""

    def __init__(self, code: ErrorCode = ErrorCode.BUSINESS_TASK_FAILED, **kwargs):
        super().__init__(code=code, **kwargs)


class TaskTimeoutException(BusinessException):
    """任务执行超时"""

    def __init__(self, task_name: str = "任务", **kwargs):
        super().__init__(code=ErrorCode.BUSINESS_TASK_TIMEOUT, message=f"{task_name}执行超时", **kwargs)


class RenameException(BusinessException):
    """重命名失败异常"""

    def __init__(self, filename: str = None, reason: str = None, **kwargs):
        message = "文件重命名失败"
        if filename:
            message = f"文件 '{filename}' 重命名失败"
        if reason:
            message += f": {reason}"

        super().__init__(code=ErrorCode.BUSINESS_RENAME_FAILED, message=message, **kwargs)


class ScrapeException(BusinessException):
    """刮削失败异常"""

    def __init__(self, filename: str = None, reason: str = None, **kwargs):
        message = "影片信息刮削失败"
        if filename:
            message = f"'{filename}' 刮削失败"
        if reason:
            message += f": {reason}"

        super().__init__(code=ErrorCode.BUSINESS_SCRAPE_FAILED, message=message, **kwargs)


# ==================== 辅助函数 ====================


def convert_http_exception(status_code: int, detail: str) -> AppException:
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
    if status_code == 503:
        return ServiceUnavailableException()
    if status_code == 504:
        return TimeoutException()
    if status_code == 401:
        return AuthException(code=ErrorCode.AUTH_UNAUTHORIZED)
    if status_code == 403:
        return AuthException(code=ErrorCode.AUTH_FORBIDDEN)
    return AppException(code=ErrorCode.EXTERNAL_API_ERROR, message=f"外部服务错误 (HTTP {status_code})", detail=detail)


def convert_aiohttp_error(error: Exception, service: str = "外部服务") -> AppException:
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
    if "connection" in error_str or "network" in error_str:
        return NetworkException()
    if "dns" in error_str:
        return ExternalServiceException(code=ErrorCode.EXTERNAL_DNS_ERROR, message="DNS解析失败")
    if "ssl" in error_str or "certificate" in error_str:
        return ExternalServiceException(code=ErrorCode.EXTERNAL_SSL_ERROR, message="SSL证书验证失败")
    return ExternalServiceException(message=f"{service}请求失败")


# ==================== 向后兼容别名 ====================
# 保留旧的类名，方便迁移
AppExceptionV2 = AppException
