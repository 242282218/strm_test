"""
FastAPI主应用

参考: MediaHelp main.py
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from asgiref.wsgi import WsgiToAsgi
from app.api import quark, strm, proxy, emby, tasks, strm_validator, quark_sdk, search, rename, dashboard, tmdb, monitoring, smart_rename, file_manager
from app.api.v1 import api_router as v1_router
from app.config.settings import AppConfig
from app.services.config_service import get_config_service
from app.core.logging import setup_logging, get_logger
from app.core.exception_handler import (
    exception_handler,
    http_exception_handler,
    validation_exception_handler,
    input_validation_exception_handler,
)
from app.core.exceptions import AppException, app_exception_handler, general_exception_handler
from app.core.constants import REQUEST_ID_HEADER
from app.core.validators import InputValidationError
from app.services.cache_service import get_cache_service
from app.services.cron_service import get_cron_service
from app.services.notification_service import get_notification_service
from app.services.webdav.service import get_webdav_app
from app.core.db import engine, Base
# 确保导入模型以便创建表
import app.models.notification
import app.models.emby
import app.models.scrape
import app.models.cloud_drive
import app.models.task
from app.api import notification as notification_router
from app.api import cloud_drive
import os

logger = get_logger(__name__)

config: AppConfig = None
config_service = None


def init_app():
    """
    初始化应用

    Args:
        无

    Returns:
        无

    Side Effects:
        初始化配置服务、日志系统
    """
    global config, config_service

    config_path = os.getenv("CONFIG_PATH", "config.yaml")
    config_service = get_config_service(config_path)
    config = config_service.get_config()

    setup_logging(
        log_level=config.log_level,
        log_file=config.log_file,
        colored=config.colored_log
    )

    logger.info(f"Application initialized with config: {config_path}")


def _mount_webdav(app: FastAPI):
    if config is None or not config.webdav.enabled:
        return

    if getattr(app.state, "webdav_mounted", False):
        return

    mount_path = config.webdav.mount_path
    wsgi_app = get_webdav_app()
    app.mount(mount_path, WsgiToAsgi(wsgi_app))
    app.state.webdav_mounted = True
    logger.info(f"WebDAV mounted at {mount_path}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    try:
        init_app()
        _mount_webdav(app)

        # 启动配置文件监控（热加载）
        if config_service:
            config_service.start_watcher()
        
        # 初始化数据库表
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created")
        
        # 启动缓存服务
        cache_service = get_cache_service()
        await cache_service.start()
        logger.info("Cache service started")
        
        # 启动定时任务服务
        cron_service = get_cron_service()
        await cron_service.start()
        logger.info("Cron service started")
        
        # 启动通知服务
        notification_service = get_notification_service()
        await notification_service.initialize()
        logger.info("Notification service started")
        
        # 初始化监控系统
        try:
            from app.core.metrics_collector import setup_default_monitoring
            setup_default_monitoring()
            logger.info("Monitoring system initialized")
        except Exception as e:
            logger.error(f"Failed to initialize monitoring: {e}")
        
        logger.info("Application started")
        yield
        
        # 停止服务
        await cron_service.stop()
        logger.info("Cron service stopped")
        
        await cache_service.stop()
        logger.info("Cache service stopped")

        if config_service:
            config_service.stop_watcher()
        
        logger.info("Application shutting down")
    except Exception as e:
        import traceback
        logger.error(f"App startup failed: {e}\n{traceback.format_exc()}")
        raise


app = FastAPI(
    title="夸克STRM系统",
    description="Emby/Jellyfin可播放的夸克网盘STRM系统",
    version="0.1.0",
    lifespan=lifespan
)


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get(REQUEST_ID_HEADER)
    if not request_id or len(request_id) > 64:
        import uuid
        request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers[REQUEST_ID_HEADER] = request_id
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册全局异常处理器
app.add_exception_handler(Exception, general_exception_handler)
app.add_exception_handler(AppException, app_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(InputValidationError, input_validation_exception_handler)

app.include_router(quark.router)
app.include_router(strm.router)
app.include_router(proxy.router)
app.include_router(emby.router)
# 设置 prefix 以符合 API 设计
app.include_router(tasks.router, prefix="/api/tasks", tags=["Tasks"])
app.include_router(cloud_drive.router, prefix="/api/drives", tags=["Cloud Drives"])
app.include_router(strm_validator.router)
app.include_router(quark_sdk.router)
app.include_router(search.router)
app.include_router(rename.router)
app.include_router(smart_rename.router)
app.include_router(dashboard.router)
app.include_router(file_manager.router, prefix="/api", tags=["FileManager"])
from app.api import transfer
app.include_router(transfer.router)

app.include_router(tmdb.router)
app.include_router(notification_router.router)
from app.api import system_config
app.include_router(system_config.router)

# V1 API routes
app.include_router(v1_router, prefix="/api/v1", tags=["API V1"])

# Monitoring API
app.include_router(monitoring.router, prefix="/api", tags=["monitoring"])


@app.get("/")
async def root():
    """根路径"""
    return {
        "name": "夸克STRM系统",
        "version": "0.1.0",
        "status": "running"
    }


@app.get("/health")
async def health():
    """健康检查"""
    from datetime import datetime
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "0.1.0"
    }


@app.get("/config")
async def get_config():
    """获取配置（敏感信息脱敏）"""
    if config is None:
        return {"error": "Config not loaded"}

    return {
        "database": config.database,
        "log_level": config.log_level,
        "timeout": config.timeout,
        "exts": config.exts,
        "alt_exts": config.alt_exts,
        "endpoints_count": len(config.endpoints)
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
