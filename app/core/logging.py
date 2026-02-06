"""
日志系统模块

参考: AlistAutoStrm log.go
"""

from loguru import logger
import sys
import os
from typing import Optional
from app.core.security import redact_sensitive


def setup_logging(
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    colored: bool = True
) -> None:
    """
    设置日志系统

    参考: AlistAutoStrm log.go

    Args:
        log_level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: 日志文件路径 (可选)
        colored: 是否启用彩色日志
    """
    logger.remove()

    def _patcher(record):
        record["message"] = redact_sensitive(str(record["message"]))
        record.setdefault("extra", {})
        record["extra"].setdefault("request_id", "-")
        record["extra"].setdefault("method", "-")
        record["extra"].setdefault("path", "-")
        record["extra"].setdefault("status", "-")
        record["extra"].setdefault("elapsed_ms", "-")
        for key, value in record["extra"].items():
            if isinstance(value, str):
                record["extra"][key] = redact_sensitive(value)

    console_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "rid=<cyan>{extra[request_id]}</cyan> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    )

    file_format = (
        "{time:YYYY-MM-DD HH:mm:ss} | "
        "{level: <8} | "
        "rid={extra[request_id]} | "
        "{name}:{function}:{line} - "
        "{message}"
    )

    logger.configure(patcher=_patcher)

    logger.add(
        sys.stdout,
        format=console_format,
        level=log_level,
        colorize=colored,
        enqueue=True
    )

    if log_file:
        log_dir = os.path.dirname(log_file)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)

        logger.add(
            log_file,
            format=file_format,
            level=log_level,
            rotation="10 MB",
            retention="7 days",
            encoding="utf-8",
            enqueue=True
        )

    logger.info(f"Logging initialized - Level: {log_level}, File: {log_file or 'None'}")


def get_logger(name: str = None):
    """
    获取logger实例

    Args:
        name: logger名称 (可选)

    Returns:
        loguru logger实例
    """
    if name:
        return logger.bind(name=name)
    return logger
