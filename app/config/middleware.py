"""
中间件配置

负责注册和管理 FastAPI 应用的中间件。
"""

import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.core.auth_middleware import AuthMiddleware
from app.core.constants import REQUEST_ID_HEADER
from app.core.csrf_middleware import CSRFMiddleware
from app.core.logging import get_logger
from app.core.security_headers_middleware import SecurityHeadersMiddleware


logger = get_logger(__name__)

# 默认 CORS 配置
DEFAULT_CORS_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
DEFAULT_CORS_METHODS = ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"]
DEFAULT_CORS_HEADERS = ["Authorization", "Content-Type", "X-Requested-With", "Accept", "Origin", "X-CSRF-Token"]

LEGACY_API_PREFIXES = [
    "/api/quark",
    "/api/strm",
    "/api/proxy",
    "/api/emby",
    "/api/scrape",
    "/api/tasks",
    "/api/drives",
    "/api/monitor",
]


def load_config_for_cors(config_service) -> dict | None:
    """加载配置用于 CORS 设置"""
    if config_service is None:
        return None

    try:
        return config_service.get_config()
    except Exception as exc:
        logger.warning(f"Failed to load config for CORS: {exc}")
        return None


def resolve_cors_settings(app_config: dict | None, config_service) -> dict[str, object]:
    """
    解析 CORS 设置

    优先级：环境变量 > 配置文件 > 默认值
    """
    cors_origins_env = os.getenv("CORS_ALLOW_ORIGINS", "")
    cors_allow_credentials_env = os.getenv("CORS_ALLOW_CREDENTIALS", "")

    if cors_origins_env:
        allow_origins = [origin.strip() for origin in cors_origins_env.split(",") if origin.strip()]
    elif app_config and getattr(app_config, "cors", None) and app_config.cors.allow_origins:
        allow_origins = app_config.cors.allow_origins
        if allow_origins == ["*"]:
            logger.warning("CORS allow_origins is '*' - using default safe origins instead")
            allow_origins = DEFAULT_CORS_ORIGINS
    else:
        allow_origins = DEFAULT_CORS_ORIGINS
        logger.info(f"Using default CORS origins: {allow_origins}")

    if cors_allow_credentials_env:
        allow_credentials = cors_allow_credentials_env.lower() in {"1", "true", "yes"}
    elif app_config and getattr(app_config, "cors", None):
        allow_credentials = bool(app_config.cors.allow_credentials)
    else:
        allow_credentials = True

    if allow_origins == ["*"] and allow_credentials:
        logger.warning("CORS allow_origins is '*' - disabling credentials to avoid invalid CORS config")
        allow_credentials = False

    if app_config and getattr(app_config, "cors", None) and app_config.cors.allow_methods:
        allow_methods = app_config.cors.allow_methods
        if allow_methods == ["*"]:
            allow_methods = DEFAULT_CORS_METHODS
    else:
        allow_methods = DEFAULT_CORS_METHODS

    if app_config and getattr(app_config, "cors", None) and app_config.cors.allow_headers:
        allow_headers = app_config.cors.allow_headers
        if allow_headers == ["*"]:
            allow_headers = DEFAULT_CORS_HEADERS
    else:
        allow_headers = DEFAULT_CORS_HEADERS

    return {
        "allow_origins": allow_origins,
        "allow_credentials": allow_credentials,
        "allow_methods": allow_methods,
        "allow_headers": allow_headers,
    }


def register_cors_middleware(app: FastAPI, config_service):
    """注册 CORS 中间件"""
    app.add_middleware(CORSMiddleware, **resolve_cors_settings(load_config_for_cors(config_service), config_service))


def register_core_middleware(app: FastAPI, config_service):
    """注册核心中间件"""
    register_cors_middleware(app, config_service)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(CSRFMiddleware)
    app.add_middleware(AuthMiddleware)
    app.add_middleware(GZipMiddleware, minimum_size=1024)


async def request_id_middleware(request: Request, call_next):
    """
    请求 ID 中间件

    为每个请求生成或传递请求 ID，用于日志追踪。
    """
    import time
    import uuid

    request_id = request.headers.get(REQUEST_ID_HEADER)
    if not request_id or len(request_id) > 64:
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


async def prometheus_middleware(request: Request, call_next):
    """
    Prometheus 请求追踪中间件

    自动记录所有 HTTP 请求的指标到 Prometheus
    """
    import time

    # 跳过 /metrics 端点本身，避免递归
    if request.url.path == "/metrics":
        return await call_next(request)

    # 跳过健康检查端点
    if request.url.path in ["/health", "/health/live", "/health/ready", "/ready", "/metrics/health"]:
        return await call_next(request)

    start_time = time.perf_counter()

    # 规范化端点路径（将动态参数替换为占位符）
    endpoint = normalize_endpoint(request.url.path)

    # 记录请求开始
    from app.core.prometheus_metrics import REQUEST_IN_PROGRESS

    REQUEST_IN_PROGRESS.labels(method=request.method, endpoint=endpoint).inc()

    try:
        response = await call_next(request)
        duration = time.perf_counter() - start_time

        # 记录 Prometheus 指标
        from app.core.prometheus_metrics import track_request

        track_request(method=request.method, endpoint=endpoint, status=response.status_code, duration=duration)

        return response
    except Exception:
        duration = time.perf_counter() - start_time

        # 记录错误请求
        from app.core.prometheus_metrics import track_request

        track_request(method=request.method, endpoint=endpoint, status=500, duration=duration)
        raise
    finally:
        REQUEST_IN_PROGRESS.labels(method=request.method, endpoint=endpoint).dec()


def normalize_endpoint(path: str) -> str:
    """
    规范化端点路径

    将动态参数替换为占位符，避免指标基数爆炸
    """
    import re

    # 替换 UUID
    path = re.sub(
        r"/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", "/{uuid}", path, flags=re.IGNORECASE
    )

    # 替换纯数字 ID
    path = re.sub(r"/\d+(?=/|$)", "/{id}", path)

    # 替换文件名（包含扩展名）
    path = re.sub(r"/[^/]+\.(strm|mp4|mkv|avi|mov|wmv|flv|webm)", "/{filename}", path, flags=re.IGNORECASE)

    return path


async def deprecation_warning_middleware(request: Request, call_next):
    """
    弃用警告中间件

    为旧版 API 路由添加弃用警告响应头
    """
    response = await call_next(request)

    path = request.url.path

    # 检查是否为旧版 API 路由（非 /api/v1 开头）
    is_legacy = (
        path.startswith("/api/")
        and not path.startswith("/api/v1/")
        and any(path.startswith(prefix) for prefix in LEGACY_API_PREFIXES)
    )

    if is_legacy:
        # 添加弃用警告响应头
        response.headers["X-API-Deprecated"] = "true"
        response.headers["X-API-Deprecation-Message"] = "This endpoint is deprecated. Please migrate to /api/v1/*"
        response.headers["X-API-Sunset"] = "2025-12-31"  # 计划下线日期

        # 记录弃用警告日志
        logger.warning(f"Deprecated API endpoint accessed: {path}. Please migrate to /api/v1{path[4:]}")

    return response
