"""
应用生命周期管理

负责 FastAPI 应用的启动和关闭流程。
"""

import traceback
from contextlib import asynccontextmanager
from datetime import datetime
from typing import AsyncIterator

from fastapi import FastAPI

from app.core.db import Base, get_engine
from app.core.dependencies import initialize_service_container
from app.core.http_pool import get_http_pool
from app.core.logging import get_logger

logger = get_logger(__name__)


def _ensure_startup_tracking_state(app: FastAPI) -> None:
    if not hasattr(app.state, "startup_components"):
        app.state.startup_components = {}
    if not hasattr(app.state, "startup_warnings"):
        app.state.startup_warnings = []


def _reset_startup_tracking_state(app: FastAPI) -> None:
    app.state.startup_components = {}
    app.state.startup_warnings = []


def _record_startup_component(app: FastAPI, component: str, status: str, detail: str | None = None) -> None:
    _ensure_startup_tracking_state(app)
    app.state.startup_components[component] = {"status": status, "detail": detail}


def _record_startup_warning(app: FastAPI, component: str, detail: str | None) -> None:
    _ensure_startup_tracking_state(app)
    if detail:
        app.state.startup_warnings.append(f"{component}: {detail}")
    else:
        app.state.startup_warnings.append(component)


def initialize_database():
    """初始化数据库表"""
    Base.metadata.create_all(bind=get_engine())
    logger.info("Database tables created")


def initialize_auth_system():
    """初始化认证系统"""
    from app.services.auth_service import init_auth_system

    init_auth_system()
    logger.info("Auth system initialized")


async def start_service_container():
    """启动服务容器"""
    container = initialize_service_container()
    await container.start_services()
    return container


def configure_emby_cron(container) -> tuple[bool, str | None]:
    """配置 Emby 定时任务"""
    try:
        from app.services.emby_service import EmbyService

        emby_service = container.get(EmbyService)
        emby_service.configure_cron()
        logger.info("Emby cron configured")
        return True, None
    except Exception as e:
        logger.warning(f"Failed to configure Emby cron: {e}")
        return False, str(e)


def initialize_monitoring() -> tuple[bool, str | None]:
    """初始化监控系统"""
    try:
        from app.core.metrics_collector import setup_default_monitoring

        setup_default_monitoring()
        logger.info("Monitoring system initialized")
        return True, None
    except Exception as e:
        logger.error(f"Failed to initialize monitoring: {e}")
        return False, str(e)


def mount_webdav(app: FastAPI, config):
    """挂载 WebDAV 服务"""
    if config is None or not config.webdav.enabled:
        return

    if getattr(app.state, "webdav_mounted", False):
        return

    from asgiref.wsgi import WsgiToAsgi

    from app.services.webdav.service import get_webdav_app

    mount_path = config.webdav.mount_path
    wsgi_app = get_webdav_app()
    if wsgi_app is None:
        logger.error("WebDAV is enabled but app initialization failed. WebDAV mount is skipped.")
        return
    app.mount(mount_path, WsgiToAsgi(wsgi_app))
    app.state.webdav_mounted = True
    logger.info(f"WebDAV mounted at {mount_path}")


async def _cleanup_lifespan_resources(container, config_service, watcher_started: bool) -> None:
    """Release startup resources in both shutdown and startup-failure paths."""
    if container is not None:
        await container.stop_services()
    if watcher_started and config_service is not None:
        config_service.stop_watcher()


@asynccontextmanager
async def lifespan(app: FastAPI, config_service, config) -> AsyncIterator[None]:
    """
    应用生命周期管理

    Args:
        app: FastAPI 应用实例
        config_service: 配置服务实例
        config: 应用配置实例
    """
    container = None
    watcher_started = False
    try:
        app.state.ready = False
        app.state.started_at = datetime.utcnow()
        _reset_startup_tracking_state(app)

        mount_webdav(app, config)
        webdav_enabled = bool(getattr(getattr(config, "webdav", None), "enabled", False))
        webdav_mounted = bool(getattr(app.state, "webdav_mounted", False))
        if not webdav_enabled:
            _record_startup_component(app, "webdav", "skipped", "webdav disabled")
        elif webdav_mounted:
            _record_startup_component(app, "webdav", "ok")
        else:
            _record_startup_component(app, "webdav", "degraded", "webdav enabled but mount skipped")
            _record_startup_warning(app, "webdav", "enabled but mount skipped")

        if config_service is not None:
            config_service.start_watcher()
            watcher_started = True
            _record_startup_component(app, "config_watcher", "ok")
        else:
            _record_startup_component(app, "config_watcher", "skipped", "config service unavailable")

        initialize_database()
        _record_startup_component(app, "database", "ok")
        initialize_auth_system()
        _record_startup_component(app, "auth_system", "ok")
        container = await start_service_container()
        _record_startup_component(app, "service_container", "ok")

        cron_ok, cron_error = configure_emby_cron(container)
        if cron_ok:
            _record_startup_component(app, "emby_cron", "ok")
        else:
            _record_startup_component(app, "emby_cron", "degraded", cron_error)
            _record_startup_warning(app, "emby_cron", cron_error)

        monitoring_ok, monitoring_error = initialize_monitoring()
        if monitoring_ok:
            _record_startup_component(app, "monitoring", "ok")
        else:
            _record_startup_component(app, "monitoring", "degraded", monitoring_error)
            _record_startup_warning(app, "monitoring", monitoring_error)

        await get_http_pool()
        _record_startup_component(app, "http_pool", "ok")
        app.state.ready = True
    except Exception as e:
        app.state.ready = False
        _record_startup_component(app, "startup", "failed", str(e))
        await _cleanup_lifespan_resources(container, config_service, watcher_started)
        logger.error(f"App startup failed: {e}\n{traceback.format_exc()}")
        raise

    logger.info("Application started")
    try:
        yield
    finally:
        app.state.ready = False
        await _cleanup_lifespan_resources(container, config_service, watcher_started)
        logger.info("Application shutting down")


def create_lifespan_context(config_service, config, initializer=None):
    """
    创建 lifespan 上下文管理器

    Args:
        config_service: 配置服务实例
        config: 应用配置实例
        initializer: 可选初始化函数，返回 (config_service, config)

    Returns:
        lifespan 异步上下文管理器
    """
    @asynccontextmanager
    async def lifespan_context(app: FastAPI) -> AsyncIterator[None]:
        resolved_config_service = config_service
        resolved_config = config
        if (resolved_config_service is None or resolved_config is None) and initializer is not None:
            resolved_config_service, resolved_config = initializer()
        app.state.config_service = resolved_config_service
        app.state.config = resolved_config
        async with lifespan(app, resolved_config_service, resolved_config):
            yield

    return lifespan_context
