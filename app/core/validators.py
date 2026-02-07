"""
Input validation utilities
"""

from __future__ import annotations

import os
import re
from typing import Optional, List
from urllib.parse import urlparse
from app.core.constants import MAX_PATH_LENGTH, MAX_URL_LENGTH, MAX_ID_LENGTH


class InputValidationError(ValueError):
    """Input validation error"""


_CONTROL_CHAR_PATTERN = re.compile(r"[\x00-\x1F\x7F]")
_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]+$")


def _validate_basic_string(value: str, field_name: str, max_length: int) -> str:
    if value is None:
        raise InputValidationError(f"{field_name} is required")
    if not isinstance(value, str):
        raise InputValidationError(f"{field_name} must be a string")
    v = value.strip()
    if not v:
        raise InputValidationError(f"{field_name} is required")
    if len(v) > max_length:
        raise InputValidationError(f"{field_name} length must be <= {max_length}")
    if _CONTROL_CHAR_PATTERN.search(v):
        raise InputValidationError(f"{field_name} contains invalid characters")
    return v


def validate_path(
    value: str,
    field_name: str = "path",
    max_length: int = MAX_PATH_LENGTH,
    base_dir: Optional[str] = None,
    allowed_dirs: Optional[List[str]] = None
) -> str:
    """
    验证路径，防止路径遍历攻击
    
    Args:
        value: 待验证的路径
        field_name: 字段名称，用于错误提示
        max_length: 最大长度限制
        base_dir: 基础目录，验证路径必须在此目录下
        allowed_dirs: 允许的目录列表，路径必须在其中一个目录下
    
    Returns:
        验证后的路径字符串
    
    Raises:
        InputValidationError: 验证失败时抛出
    """
    # 基础字符串验证
    v = _validate_basic_string(value, field_name, max_length)
    
    # 检查路径遍历攻击特征
    # 1. 检查是否包含 .. 路径段
    normalized = os.path.normpath(v)
    parts = normalized.replace('\\', '/').split('/')
    if any(p == '..' for p in parts):
        raise InputValidationError(f"{field_name} contains invalid path traversal sequence")
    
    # 2. 检查是否以 / 或 \ 开头（绝对路径）
    # 如果指定了 allowed_dirs，允许绝对路径（后续会验证是否在允许范围内）
    if os.path.isabs(v) and allowed_dirs is None:
        raise InputValidationError(f"{field_name} must be a relative path")
    
    # 3. 检查是否包含空字节（用于绕过某些检查）
    if '\x00' in v:
        raise InputValidationError(f"{field_name} contains null bytes")
    
    # 4. 如果指定了基础目录，验证路径是否在基础目录下
    if base_dir is not None:
        abs_base = os.path.abspath(base_dir)
        abs_path = os.path.abspath(os.path.join(base_dir, v))
        if not abs_path.startswith(abs_base + os.sep) and abs_path != abs_base:
            raise InputValidationError(f"{field_name} is outside of allowed base directory")
    
    # 5. 如果指定了允许目录列表，验证路径是否在允许范围内
    if allowed_dirs is not None:
        abs_path = os.path.abspath(v)
        in_allowed = False
        for allowed_dir in allowed_dirs:
            abs_allowed = os.path.abspath(allowed_dir)
            if abs_path.startswith(abs_allowed + os.sep) or abs_path == abs_allowed:
                in_allowed = True
                break
        if not in_allowed:
            raise InputValidationError(f"{field_name} is not in allowed directories")
    
    return v


def validate_identifier(value: str, field_name: str = "id", max_length: int = MAX_ID_LENGTH) -> str:
    v = _validate_basic_string(value, field_name, max_length)
    if not _ID_PATTERN.match(v):
        raise InputValidationError(f"{field_name} has invalid format")
    return v


def validate_http_url(value: str, field_name: str = "url", max_length: int = MAX_URL_LENGTH) -> str:
    v = _validate_basic_string(value, field_name, max_length)
    parsed = urlparse(v)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise InputValidationError(f"{field_name} must be a valid http/https URL")
    return v


def validate_proxy_path(value: str, field_name: str = "path", max_length: int = MAX_URL_LENGTH) -> str:
    v = _validate_basic_string(value, field_name, max_length)
    if "://" in v or v.startswith("//"):
        raise InputValidationError(f"{field_name} contains invalid scheme")
    parts = [p for p in v.split("/") if p]
    if any(p == ".." for p in parts):
        raise InputValidationError(f"{field_name} contains invalid path segment")
    return v
