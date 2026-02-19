"""
FastAPI主应用

参考: MediaHelp main.py
"""

from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
import time
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import ORJSONResponse, FileResponse
from asgiref.wsgi import WsgiToAsgi
from app.api import quark, strm, proxy, emby, scrape, tasks, strm_validator, quark_sdk, search, rename, dashboard, tmdb, monitoring, smart_rename, file_manager
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
from app.core.exceptions import AppException, app_exception_handler
from app.core.constants import REQUEST_ID_HEADER
from app.core.validators import InputValidationError
from app.core.dependencies import require_api_key
from app.services.cache_service import get_cache_service
from app.services.link_cache import get_link_cache_service
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
import app.models.strm_record
from app.api import notification as notification_router
from app.api import cloud_drive
import os

logger = get_logger(__name__)

config: AppConfig = None
config_service = None
WEB_DIST_DIR = Path(__file__).resolve().parent.parent / "web_dist"
NON_SPA_PREFIXES = (
    "api",
    "dav",
    "docs",
    "redoc",
    "openapi.json",
    "health",
    "config",
)


def _get_frontend_file(relative_path: str) -> Path | None:
    if not WEB_DIST_DIR.exists():
        return None

    root = WEB_DIST_DIR.resolve()
    candidate = (WEB_DIST_DIR / relative_path).resolve()
    if not str(candidate).startswith(str(root)):
        return None

    if candidate.is_file():
        return candidate
    return None


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
    if wsgi_app is None:
        logger.error("WebDAV is enabled but app initialization failed. WebDAV mount is skipped.")
        return
    app.mount(mount_path, WsgiToAsgi(wsgi_app))
    app.state.webdav_mounted = True
    logger.info(f"WebDAV mounted at {mount_path}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    try:
        init_app()
        app.state.started_at = datetime.utcnow()
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

        link_cache = get_link_cache_service()
        await link_cache.start()
        logger.info("Link cache started")
        
        # 启动定时任务服务
        cron_service = get_cron_service()
        await cron_service.start()
        logger.info("Cron service started")

        # 配置Emby定时刷新（如启用）
        try:
            from app.services.emby_service import get_emby_service
            get_emby_service().configure_cron()
            logger.info("Emby cron configured")
        except Exception as e:
            logger.warning(f"Failed to configure Emby cron: {e}")
        
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
        
        await link_cache.stop()
        logger.info("Link cache stopped")

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
    default_response_class=ORJSONResponse,
    lifespan=lifespan
)


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get(REQUEST_ID_HEADER)
    if not request_id or len(request_id) > 64:
        import uuid
        request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = int((time.perf_counter() - start) * 1000)
    response.headers[REQUEST_ID_HEADER] = request_id
    response.headers["X-Response-Time"] = f"{elapsed_ms}ms"

    access_logger = logger.bind(
        request_id=request_id,
        method=request.method,
        path=request.url.path,
        status=response.status_code,
        elapsed_ms=elapsed_ms,
    )
    if response.status_code >= 500:
        access_logger.error(f"{request.method} {request.url.path} -> {response.status_code} ({elapsed_ms}ms)")
    elif response.status_code >= 400:
        access_logger.warning(f"{request.method} {request.url.path} -> {response.status_code} ({elapsed_ms}ms)")
    else:
        access_logger.info(f"{request.method} {request.url.path} -> {response.status_code} ({elapsed_ms}ms)")

    return response

# CORS 配置 - 默认只允许本地开发环境
cors_origins_env = os.getenv("CORS_ALLOW_ORIGINS", "")
cors_allow_credentials_env = os.getenv("CORS_ALLOW_CREDENTIALS", "")

config_for_cors = None
try:
    config_for_cors = get_config_service(os.getenv("CONFIG_PATH", "config.yaml")).get_config()
except Exception as exc:
    logger.warning(f"Failed to load config for CORS: {exc}")

# 默认只允许本地开发环境，生产环境必须显式配置
_default_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

if cors_origins_env:
    allow_origins = [origin.strip() for origin in cors_origins_env.split(",") if origin.strip()]
elif config_for_cors and getattr(config_for_cors, "cors", None) and config_for_cors.cors.allow_origins:
    allow_origins = config_for_cors.cors.allow_origins
    # 如果配置为 *，则使用默认值并发出警告
    if allow_origins == ["*"]:
        logger.warning("CORS allow_origins is '*' - using default safe origins instead")
        allow_origins = _default_origins
else:
    # 默认使用安全的本地开发环境配置
    allow_origins = _default_origins
    logger.info(f"Using default CORS origins: {allow_origins}")

if cors_allow_credentials_env:
    allow_credentials = cors_allow_credentials_env.lower() in {"1", "true", "yes"}
elif config_for_cors and getattr(config_for_cors, "cors", None):
    allow_credentials = bool(config_for_cors.cors.allow_credentials)
else:
    allow_credentials = True  # 默认允许凭证，因为默认来源是安全的

if allow_origins == ["*"] and allow_credentials:
    logger.warning("CORS allow_origins is '*' - disabling credentials to avoid invalid CORS config")
    allow_credentials = False

# 限制允许的 HTTP 方法
_default_methods = ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"]
if config_for_cors and getattr(config_for_cors, "cors", None) and config_for_cors.cors.allow_methods:
    allow_methods = config_for_cors.cors.allow_methods
    if allow_methods == ["*"]:
        allow_methods = _default_methods
else:
    allow_methods = _default_methods

# 限制允许的请求头
_default_headers = ["Authorization", "Content-Type", "X-Requested-With", "Accept", "Origin"]
if config_for_cors and getattr(config_for_cors, "cors", None) and config_for_cors.cors.allow_headers:
    allow_headers = config_for_cors.cors.allow_headers
    if allow_headers == ["*"]:
        allow_headers = _default_headers
else:
    allow_headers = _default_headers

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=allow_credentials,
    allow_methods=allow_methods,
    allow_headers=allow_headers,
)
app.add_middleware(GZipMiddleware, minimum_size=1024)

# 注册全局异常处理器
app.add_exception_handler(Exception, exception_handler)
app.add_exception_handler(AppException, app_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(InputValidationError, input_validation_exception_handler)

app.include_router(quark.router)
app.include_router(strm.router)
app.include_router(proxy.router)
app.include_router(emby.router)
app.include_router(scrape.router, prefix="/api")
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
    """Serve frontend index when available."""
    index_file = _get_frontend_file("index.html")
    if index_file:
        return FileResponse(index_file)

    return {
        "name": "Quark STRM",
        "version": "0.1.0",
        "status": "running"
    }


@app.get("/health")
async def health():
    """健康检查"""
    started_at = getattr(app.state, "started_at", None)
    uptime_seconds = None
    if started_at:
        uptime_seconds = int((datetime.utcnow() - started_at).total_seconds())
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "uptime_seconds": uptime_seconds,
        "version": "0.1.0"
    }


@app.get("/config")
async def get_config(_auth: None = Depends(require_api_key)):
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



@app.get("/{full_path:path}", include_in_schema=False)
async def spa_fallback(full_path: str):
    normalized = full_path.lstrip("/")
    if any(
        normalized == prefix or normalized.startswith(f"{prefix}/")
        for prefix in NON_SPA_PREFIXES
    ):
        raise HTTPException(status_code=404, detail="Not found")

    static_file = _get_frontend_file(normalized)
    if static_file:
        return FileResponse(static_file)

    index_file = _get_frontend_file("index.html")
    if index_file:
        return FileResponse(index_file)

    raise HTTPException(status_code=404, detail="Not found")

if __name__ == "__main__":
    import uvicorn
    workers = int(os.getenv("WEB_CONCURRENCY", "1"))
    uvicorn.run(app, host="0.0.0.0", port=8001, workers=workers)
