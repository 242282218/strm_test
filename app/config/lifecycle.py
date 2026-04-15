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


def configure_emby_cron(container):
    """配置 Emby 定时任务"""
    try:
        from app.services.emby_service import EmbyService

        emby_service = container.get(EmbyService)
        emby_service.configure_cron()
        logger.info("Emby cron configured")
    except Exception as e:
        logger.warning(f"Failed to configure Emby cron: {e}")


def initialize_monitoring():
    """初始化监控系统"""
    try:
        from app.core.metrics_collector import setup_default_monitoring

        setup_default_monitoring()
        logger.info("Monitoring system initialized")
    except Exception as e:
        logger.error(f"Failed to initialize monitoring: {e}")


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
        app.state.started_at = datetime.utcnow()
        mount_webdav(app, config)
        if config_service is not None:
            config_service.start_watcher()
            watcher_started = True
        initialize_database()
        initialize_auth_system()
        container = await start_service_container()
        configure_emby_cron(container)
        initialize_monitoring()
        await get_http_pool()
    except Exception as e:
        await _cleanup_lifespan_resources(container, config_service, watcher_started)
        logger.error(f"App startup failed: {e}\n{traceback.format_exc()}")
        raise

    logger.info("Application started")
    try:
        yield
    finally:
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
