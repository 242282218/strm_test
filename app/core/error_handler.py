"""
废弃模块 - 请使用 app.core.exception_handler

此文件仅用于向后兼容，所有内容已迁移到 exception_handler.py
将在未来版本中移除。

迁移指南:
    旧: from app.core.error_handler import ErrorCode, ErrorHandler, ...
    新: from app.core.error_codes import ErrorCode, get_http_status
        from app.core.exception_handler import app_exception_handler
"""

import warnings


# 发出弃用警告
warnings.warn(
    "app.core.error_handler 已废弃，请使用 app.core.error_codes 和 app.core.exception_handler",
    DeprecationWarning,
    stacklevel=2,
)

import re
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.core.logging import get_logger


logger = get_logger(__name__)


# ==================== 保留的工具类 ====================
# 这些类在 error_handler.py 中定义，但不在其他地方重复


class LogSanitizer:
    """日志脱敏工具类"""

    # 敏感信息模式定义
    SENSITIVE_PATTERNS = {
        "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
        "phone": r"\b1[3-9]\d{9}\b|\b\d{3}-\d{4}-\d{4}\b",
        "api_key": r"\b[A-Fa-f0-9]{32,}\b",
        "password": r'["\']password["\']\s*[:=]\s*["\'][^"\']*["\']',
        "jwt_token": r"\beyJ[A-Za-z0-9-_]*\.[A-Za-z0-9-_]*\.[A-Za-z0-9-_]*\b",
        "cookie": r"(?:^|;\s*)(?:auth|session|token)=([^;]+)",
        "ip_address": r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b",
        "id_card": r"\b\d{17}[\dXx]\b|\b\d{15}\b",
        "bank_card": r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4,7}\b",
    }

    MASK_REPLACEMENTS = {
        "email": "[EMAIL_MASKED]",
        "phone": "[PHONE_MASKED]",
        "api_key": "[API_KEY_MASKED]",
        "password": '"password":"[PASSWORD_MASKED]"',
        "jwt_token": "[JWT_TOKEN_MASKED]",
        "cookie": "[COOKIE_VALUE_MASKED]",
        "ip_address": "[IP_ADDRESS_MASKED]",
        "id_card": "[ID_CARD_MASKED]",
        "bank_card": "[BANK_CARD_MASKED]",
    }

    @classmethod
    def sanitize(cls, message: str | dict | Any, level: str = "info") -> str | dict | Any:
        """脱敏日志消息"""
        if level == "debug":
            critical_patterns = ["password", "api_key", "jwt_token"]
            patterns_to_use = {k: v for k, v in cls.SENSITIVE_PATTERNS.items() if k in critical_patterns}
        else:
            patterns_to_use = cls.SENSITIVE_PATTERNS

        if isinstance(message, dict):
            return {k: cls.sanitize(v, level) for k, v in message.items()}

        if isinstance(message, str):
            sanitized = message
            for pattern_name, pattern in patterns_to_use.items():
                try:
                    sanitized = re.sub(pattern, cls.MASK_REPLACEMENTS[pattern_name], sanitized, flags=re.IGNORECASE)
                except Exception as e:
                    logger.warning(f"Pattern sanitization failed for {pattern_name}: {e}")
            return sanitized

        return message

    @classmethod
    def sanitize_headers(cls, headers: dict[str, str]) -> dict[str, str]:
        """脱敏HTTP头部信息"""
        sensitive_headers = {"authorization", "cookie", "x-api-key", "x-auth-token"}

        sanitized = {}
        for key, value in headers.items():
            key_lower = key.lower()
            if key_lower in sensitive_headers:
                sanitized[key] = "[HEADER_VALUE_MASKED]"
            else:
                sanitized[key] = value

        return sanitized


class SuccessResponse(BaseModel):
    """标准化成功响应模型"""

    success: bool = True
    data: dict[str, Any] | None = None
    message: str | None = None
    timestamp: str
    request_id: str | None = None


# ==================== 便捷函数 ====================


def create_success_response(
    data: dict[str, Any] | None = None, message: str | None = None, request_id: str | None = None
) -> dict[str, Any]:
    """创建标准化成功响应"""
    response = SuccessResponse(
        success=True,
        data=data,
        message=message,
        timestamp=datetime.utcnow().isoformat(),
        request_id=request_id or str(uuid.uuid4()),
    )
    return response.model_dump()


def sanitize_log(message: str | dict | Any, level: str = "info") -> str | dict | Any:
    """便捷的日志脱敏函数"""
    return LogSanitizer.sanitize(message, level)


# ==================== 向后兼容别名 ====================
# 重导出新的 ErrorCode（从 error_codes）
from app.core.error_codes import ErrorCode as NewErrorCode


# 旧版本曾暴露 ErrorCodeCompat 名称，这里保留别名避免导入崩溃。
# Python Enum 不允许通过继承扩展已有枚举，直接复用新枚举类型。
ErrorCodeCompat = NewErrorCode


# 将新的 ErrorCode 也导出，让用户可以选择
ErrorCode = NewErrorCode

__all__ = [
    "ErrorCode",
    "LogSanitizer",
    "SuccessResponse",
    "create_success_response",
    "sanitize_log",
]
