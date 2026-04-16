"""
FastAPI 主应用入口

参考：MediaHelp main.py
"""

import os

from fastapi import Depends, HTTPException, Request

from app.config.application import create_fastapi_app, register_exception_handlers, register_routers
from app.config.lifecycle import create_lifespan_context
from app.config.middleware import (
    deprecation_warning_middleware,
    prometheus_middleware,
    request_id_middleware,
)
from app.core.dependencies import require_api_key
from app.core.logging import get_logger
from app.core.rate_limiter import setup_rate_limiting
from app.services.config_service import get_config_service

logger = get_logger(__name__)

APP_TITLE = "夸克 STRM 系统"
APP_DESCRIPTION = "Emby/Jellyfin 可播放的夸克网盘 STRM 系统"
APP_VERSION = "0.1.0"

# 全局配置实例
config = None
config_service = None


def _resolve_startup_health() -> tuple[str, list[str], dict[str, dict[str, str | None]]]:
    warnings = list(getattr(app.state, "startup_warnings", []))
    components = getattr(app.state, "startup_components", {})
    if not isinstance(components, dict):
        components = {}

    degraded = False
    for component in components.values():
        if isinstance(component, dict) and component.get("status") in {"degraded", "failed"}:
            degraded = True
            break

    status = "degraded" if warnings or degraded else "ok"
    return status, warnings, components


def get_config_path() -> str:
    """获取配置文件路径"""
    return os.getenv("CONFIG_PATH", "config.yaml")


def initialize_app():
    """初始化应用配置和日志系统"""
    global config, config_service

    if config is not None and config_service is not None:
        return config_service, config

    config_path = get_config_path()
    config_service = get_config_service(config_path)
    config = config_service.get_config()

    # 设置日志
    log_format = os.getenv("SMART_MEDIA_LOG_FORMAT", config.log.format)
    from app.core.logging import setup_logging
    setup_logging(
        log_level=config.log_level,
        log_file=config.log_file,
        colored=config.colored_log,
        log_format=log_format,
        log_config=config.log.model_dump() if hasattr(config, "log") else None,
    )

    logger.info(f"Application initialized with config: {config_path}")

    # 记录配置警告
    config_warnings = config.validate_required_configs()
    if config_warnings:
        for warning in config_warnings:
            logger.warning(f"Configuration warning: {warning}")

    # 记录敏感字段状态
    sensitive_status = config.get_sensitive_fields_status()
    configured_count = sum(1 for value in sensitive_status.values() if value)
    total_count = len(sensitive_status)
    logger.info(f"Sensitive fields configured: {configured_count}/{total_count}")
    return config_service, config


# 创建 lifespan 上下文
lifespan_context = create_lifespan_context(config_service, config, initializer=initialize_app)

# 创建 FastAPI 应用
app = create_fastapi_app(APP_TITLE, APP_DESCRIPTION, APP_VERSION, lifespan_context)

# 注册中间件
from app.config.middleware import register_core_middleware
register_core_middleware(app, config_service)
app.middleware("http")(request_id_middleware)
app.middleware("http")(prometheus_middleware)
app.middleware("http")(deprecation_warning_middleware)

# 设置速率限制（默认 100 请求/分钟）
setup_rate_limiting(app, requests=100, seconds=60, block_duration=300)

# 注册路由
register_routers(app)

# 注册异常处理器
register_exception_handlers(app)


@app.get("/")
async def root(request: Request):
    """根路径。命中专用 Emby 代理入口时转发到 Emby 首页。"""
    is_dedicated_proxy_request = False
    try:
        from app.api import emby_gateway
        app_config = emby_gateway.config_service.get_config()
        is_dedicated_proxy_request = emby_gateway._is_dedicated_proxy_request(request, app_config)
        if is_dedicated_proxy_request:
            return await emby_gateway._forward_to_emby(request, app_config, "")
    except Exception as exc:
        logger.warning(f"Dedicated Emby gateway root forwarding failed: {exc}")
        if is_dedicated_proxy_request:
            raise HTTPException(status_code=502, detail="Failed to proxy Emby home") from exc

    return {"name": "夸克 STRM 系统", "version": "0.1.0", "status": "running"}


@app.get("/health")
async def health():
    """健康检查"""
    from datetime import datetime

    started_at = getattr(app.state, "started_at", None)
    uptime_seconds = None
    if started_at:
        uptime_seconds = int((datetime.utcnow() - started_at).total_seconds())

    health_status, startup_warnings, startup_components = _resolve_startup_health()

    return {
        "status": health_status,
        "timestamp": datetime.utcnow().isoformat(),
        "uptime_seconds": uptime_seconds,
        "version": "0.1.0",
        "startup_warnings": startup_warnings,
        "startup_components": startup_components,
    }


@app.get("/config")
async def get_config_endpoint(_auth: None = Depends(require_api_key)):
    """获取配置（敏感信息脱敏）"""
    active_config = config or getattr(app.state, "config", None)
    if active_config is None:
        return {"error": "Config not loaded"}

    return {
        "database": active_config.database,
        "log_level": active_config.log_level,
        "timeout": active_config.timeout,
        "exts": active_config.exts,
        "alt_exts": active_config.alt_exts,
        "endpoints_count": len(active_config.endpoints),
    }


if __name__ == "__main__":
    import uvicorn

    workers = int(os.getenv("WEB_CONCURRENCY", "1"))
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port, workers=workers)
