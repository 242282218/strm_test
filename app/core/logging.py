"""
日志系统模块

参考: AlistAutoStrm log.go
支持 JSON 结构化日志输出，便于日志聚合和分析
"""

import json
import os
import sys

from loguru import logger

from app.core.security import redact_sensitive


class JsonSink:
    """
    JSON 输出 sink

    将日志记录转换为 JSON 格式，便于日志聚合工具（如 ELK、Loki）解析
    """

    def __init__(self, stream=None):
        self.stream = stream or sys.stdout

    def write(self, message):
        """
        写入 JSON 格式的日志

        Args:
            message: loguru 日志消息对象
        """
        record = message.record
        log_data = {
            "timestamp": record["time"].isoformat(),
            "level": record["level"].name,
            "message": redact_sensitive(str(record["message"])),
            "logger": record["name"],
            "function": record["function"],
            "line": record["line"],
        }

        # 添加额外字段
        extra = record.get("extra", {})
        if extra:
            # 处理 request_id
            if "request_id" in extra and extra["request_id"] != "-":
                log_data["request_id"] = extra["request_id"]

            # 处理 HTTP 请求相关字段
            if "method" in extra and extra["method"] != "-":
                log_data["method"] = extra["method"]
            if "path" in extra and extra["path"] != "-":
                log_data["path"] = extra["path"]
            if "status" in extra and extra["status"] != "-":
                log_data["status"] = extra["status"]
            if "elapsed_ms" in extra and extra["elapsed_ms"] != "-":
                log_data["elapsed_ms"] = extra["elapsed_ms"]

            # 添加其他额外字段（排除已处理的字段）
            excluded_keys = {"request_id", "method", "path", "status", "elapsed_ms", "name"}
            for key, value in extra.items():
                if key not in excluded_keys and value is not None:
                    if isinstance(value, str):
                        log_data[key] = redact_sensitive(value)
                    else:
                        log_data[key] = value

        # 添加异常信息
        if record["exception"]:
            log_data["exception"] = {
                "type": record["exception"].type.__name__ if record["exception"].type else None,
                "message": str(record["exception"].value) if record["exception"].value else None,
                "traceback": record["exception"].traceback if record["exception"].traceback else None,
            }

        self.stream.write(json.dumps(log_data, ensure_ascii=False, default=str) + "\n")
        self.stream.flush()

    def flush(self):
        """刷新缓冲区"""
        if hasattr(self.stream, "flush"):
            self.stream.flush()


def get_text_format(colored: bool = True) -> str:
    """
    获取文本格式模板

    Args:
        colored: 是否启用彩色输出

    Returns:
        文本格式的日志模板字符串
    """
    if colored:
        return (
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "rid=<cyan>{extra[request_id]}</cyan> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>\n"
        )
    return "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | rid={extra[request_id]} | {name}:{function}:{line} - {message}\n"


def setup_logging(
    log_level: str = "INFO",
    log_file: str | None = None,
    colored: bool = True,
    log_format: str = "text",
    log_config: dict | None = None,
) -> None:
    """
    设置日志系统

    参考: AlistAutoStrm log.go

    Args:
        log_level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: 日志文件路径 (可选)
        colored: 是否启用彩色日志
        log_format: 日志格式 (text, json)
        log_config: 日志配置字典 (可选，用于更细粒度的控制)
    """
    logger.remove()

    # 解析日志配置
    if log_config is None:
        log_config = {}

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

    logger.configure(patcher=_patcher)

    # 控制台输出
    if log_format.lower() == "json":
        # JSON 格式输出到控制台
        json_sink = JsonSink(sys.stdout)
        logger.add(json_sink, level=log_level, format="{message}", enqueue=True)
    else:
        # 文本格式输出到控制台
        console_format = get_text_format(colored)
        logger.add(sys.stdout, format=console_format, level=log_level, colorize=colored, enqueue=True)

    # 文件输出
    if log_file:
        log_dir = os.path.dirname(log_file)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)

        # 文件始终使用 JSON 格式（便于日志聚合）
        # 使用 serialize=True 输出 JSON 格式
        logger.add(
            log_file,
            level=log_level,
            format="{message}",
            rotation="10 MB",
            retention="7 days",
            enqueue=True,
            serialize=True,
        )

    format_info = f"Format: {log_format}"
    if log_file:
        format_info += f", File: {log_file} (JSON)"
    logger.info(f"Logging initialized - Level: {log_level}, {format_info}")


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
