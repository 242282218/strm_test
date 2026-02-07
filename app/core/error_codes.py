# -*- coding: utf-8 -*-
"""
错误码定义模块

提供详细的错误分类和前端友好的错误消息
"""

from enum import IntEnum
from typing import Dict, Optional


class ErrorCategory(IntEnum):
    """错误分类"""
    SUCCESS = 0
    
    # 1xxx - 认证/权限错误
    AUTH_ERROR = 1000
    
    # 2xxx - 参数/请求错误
    VALIDATION_ERROR = 2000
    
    # 3xxx - 外部服务错误
    EXTERNAL_SERVICE_ERROR = 3000
    
    # 4xxx - 系统内部错误
    SYSTEM_ERROR = 4000
    
    # 5xxx - 业务逻辑错误
    BUSINESS_ERROR = 5000


class ErrorCode(IntEnum):
    """
    详细错误码定义
    
    格式: XXYY
    - XX: 错误分类 (10=认证, 20=参数, 30=外部服务, 40=系统, 50=业务)
    - YY: 具体错误
    """
    # 成功
    SUCCESS = 0
    
    # 10xx - 认证/权限
    AUTH_UNAUTHORIZED = 1001           # 未授权
    AUTH_FORBIDDEN = 1002              # 禁止访问
    AUTH_TOKEN_EXPIRED = 1003          # Token过期
    AUTH_INVALID_CREDENTIALS = 1004    # 凭据无效
    AUTH_COOKIE_INVALID = 1005         # Cookie失效（夸克/115等）
    AUTH_RATE_LIMITED = 1006           # 登录频率限制
    
    # 20xx - 参数/请求
    VALIDATION_INVALID_PARAM = 2001    # 参数无效
    VALIDATION_MISSING_FIELD = 2002    # 缺少必填字段
    VALIDATION_TYPE_ERROR = 2003       # 类型错误
    VALIDATION_FORMAT_ERROR = 2004     # 格式错误
    REQUEST_NOT_FOUND = 2005           # 资源不存在
    REQUEST_CONFLICT = 2006            # 资源冲突
    REQUEST_TOO_LARGE = 2007           # 请求体过大
    
    # 30xx - 外部服务错误
    EXTERNAL_API_ERROR = 3001          # 外部API通用错误
    EXTERNAL_TIMEOUT = 3002            # 请求超时
    EXTERNAL_RATE_LIMIT = 3003         # API频率限制 (429)
    EXTERNAL_SERVICE_UNAVAILABLE = 3004 # 服务不可用 (503)
    EXTERNAL_QUARK_ERROR = 3010        # 夸克网盘错误
    EXTERNAL_115_ERROR = 3011          # 115网盘错误
    EXTERNAL_TMDB_ERROR = 3012         # TMDB错误
    EXTERNAL_NETWORK_ERROR = 3013      # 网络错误
    EXTERNAL_DNS_ERROR = 3014          # DNS解析错误
    EXTERNAL_SSL_ERROR = 3015          # SSL证书错误
    EXTERNAL_PROXY_ERROR = 3016        # 代理错误
    
    # 40xx - 系统内部错误
    SYSTEM_INTERNAL_ERROR = 4001       # 内部错误
    SYSTEM_DB_ERROR = 4002             # 数据库错误
    SYSTEM_CACHE_ERROR = 4003          # 缓存错误
    SYSTEM_IO_ERROR = 4004             # IO错误
    SYSTEM_MEMORY_ERROR = 4005         # 内存不足
    SYSTEM_DISK_FULL = 4006            # 磁盘已满
    
    # 50xx - 业务逻辑错误
    BUSINESS_TASK_FAILED = 5001        # 任务执行失败
    BUSINESS_TASK_TIMEOUT = 5002       # 任务超时
    BUSINESS_FILE_NOT_FOUND = 5003     # 文件不存在
    BUSINESS_FILE_TOO_LARGE = 5004     # 文件过大
    BUSINESS_RENAME_FAILED = 5005      # 重命名失败
    BUSINESS_SCRAPE_FAILED = 5006      # 刮削失败
    BUSINESS_TRANSFER_FAILED = 5007    # 传输失败
    BUSINESS_STRM_FAILED = 5008        # STRM生成失败


# 错误码到HTTP状态码的映射
ERROR_HTTP_STATUS: Dict[ErrorCode, int] = {
    # 认证错误 -> 401/403
    ErrorCode.AUTH_UNAUTHORIZED: 401,
    ErrorCode.AUTH_FORBIDDEN: 403,
    ErrorCode.AUTH_TOKEN_EXPIRED: 401,
    ErrorCode.AUTH_INVALID_CREDENTIALS: 401,
    ErrorCode.AUTH_COOKIE_INVALID: 401,
    
    # 参数错误 -> 400/404/409
    ErrorCode.VALIDATION_INVALID_PARAM: 400,
    ErrorCode.VALIDATION_MISSING_FIELD: 400,
    ErrorCode.VALIDATION_TYPE_ERROR: 400,
    ErrorCode.VALIDATION_FORMAT_ERROR: 400,
    ErrorCode.REQUEST_NOT_FOUND: 404,
    ErrorCode.REQUEST_CONFLICT: 409,
    ErrorCode.REQUEST_TOO_LARGE: 413,
    
    # 外部服务错误 -> 502/504/429
    ErrorCode.EXTERNAL_API_ERROR: 502,
    ErrorCode.EXTERNAL_TIMEOUT: 504,
    ErrorCode.EXTERNAL_RATE_LIMIT: 429,
    ErrorCode.EXTERNAL_SERVICE_UNAVAILABLE: 503,
    ErrorCode.EXTERNAL_QUARK_ERROR: 502,
    ErrorCode.EXTERNAL_115_ERROR: 502,
    ErrorCode.EXTERNAL_TMDB_ERROR: 502,
    ErrorCode.EXTERNAL_NETWORK_ERROR: 502,
    
    # 系统错误 -> 500
    ErrorCode.SYSTEM_INTERNAL_ERROR: 500,
    ErrorCode.SYSTEM_DB_ERROR: 500,
    ErrorCode.SYSTEM_CACHE_ERROR: 500,
    ErrorCode.SYSTEM_IO_ERROR: 500,
    
    # 业务错误 -> 400/422
    ErrorCode.BUSINESS_TASK_FAILED: 422,
    ErrorCode.BUSINESS_TASK_TIMEOUT: 408,
    ErrorCode.BUSINESS_FILE_NOT_FOUND: 404,
    ErrorCode.BUSINESS_RENAME_FAILED: 422,
    ErrorCode.BUSINESS_SCRAPE_FAILED: 422,
}


# 错误码到前端消息的映射
ERROR_MESSAGES: Dict[ErrorCode, Dict[str, str]] = {
    # 认证错误
    ErrorCode.AUTH_UNAUTHORIZED: {
        "title": "未授权",
        "message": "请先登录后再操作",
        "action": "前往登录"
    },
    ErrorCode.AUTH_COOKIE_INVALID: {
        "title": "登录已失效",
        "message": "您的登录状态已过期，请重新登录",
        "action": "重新登录"
    },
    
    # 外部服务错误
    ErrorCode.EXTERNAL_TIMEOUT: {
        "title": "请求超时",
        "message": "服务器响应时间过长，请稍后重试",
        "action": "重试"
    },
    ErrorCode.EXTERNAL_RATE_LIMIT: {
        "title": "请求过于频繁",
        "message": "API调用频率超限，请稍后再试",
        "action": "稍后再试"
    },
    ErrorCode.EXTERNAL_SERVICE_UNAVAILABLE: {
        "title": "服务暂时不可用",
        "message": "第三方服务维护中，请稍后重试",
        "action": "稍后再试"
    },
    ErrorCode.EXTERNAL_QUARK_ERROR: {
        "title": "夸克网盘错误",
        "message": "夸克网盘服务异常，请检查Cookie是否有效",
        "action": "检查配置"
    },
    ErrorCode.EXTERNAL_115_ERROR: {
        "title": "115网盘错误",
        "message": "115网盘服务异常，请检查Cookie是否有效",
        "action": "检查配置"
    },
    ErrorCode.EXTERNAL_NETWORK_ERROR: {
        "title": "网络错误",
        "message": "网络连接异常，请检查网络设置",
        "action": "重试"
    },
    
    # 业务错误
    ErrorCode.BUSINESS_TASK_TIMEOUT: {
        "title": "任务执行超时",
        "message": "操作耗时过长，请稍后查看结果",
        "action": "查看任务状态"
    },
    ErrorCode.BUSINESS_RENAME_FAILED: {
        "title": "重命名失败",
        "message": "文件重命名操作失败，请检查文件权限",
        "action": "重试"
    },
    ErrorCode.BUSINESS_SCRAPE_FAILED: {
        "title": "刮削失败",
        "message": "无法获取影片信息，请检查文件名或手动匹配",
        "action": "手动匹配"
    },
}


def get_error_message(code: ErrorCode) -> Dict[str, str]:
    """
    获取错误码对应的前端消息
    
    Args:
        code: 错误码
        
    Returns:
        包含title、message、action的字典
    """
    return ERROR_MESSAGES.get(code, {
        "title": "操作失败",
        "message": "发生未知错误，请稍后重试",
        "action": "重试"
    })


def get_http_status(code: ErrorCode) -> int:
    """获取错误码对应的HTTP状态码"""
    return ERROR_HTTP_STATUS.get(code, 500)


def get_error_category(code: ErrorCode) -> ErrorCategory:
    """获取错误码所属分类"""
    category_code = (code.value // 100) * 100
    try:
        return ErrorCategory(category_code)
    except ValueError:
        return ErrorCategory.SYSTEM_ERROR
