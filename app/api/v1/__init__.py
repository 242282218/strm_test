"""
V1 API 路由聚合器

统一管理所有 API 路由，提供版本化的 API 端点。
所有路由在 /api/v1 前缀下可用。

路由结构:
- /api/v1/quark/* - 夸克网盘服务
- /api/v1/strm/* - STRM 文件服务
- /api/v1/proxy/* - 代理服务
- /api/v1/emby/* - Emby 集成服务
- /api/v1/scrape/* - 刮削服务
- /api/v1/tasks/* - 任务管理
- /api/v1/monitor/* - 监控服务
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.routing import APIRoute, APIWebSocketRoute

# 导入所有 API 路由模块
from app.api import emby, monitoring, proxy, quark, scrape, strm, tasks


# 创建 V1 路由聚合器
v1_router = APIRouter()


def _trim_api_prefix(path: str) -> str:
    if path == "/api":
        return "/"
    if path.startswith("/api/"):
        return path[4:]
    return path


def _join_path(prefix: str, path: str) -> str:
    normalized_prefix = (prefix or "").rstrip("/")
    normalized_path = path if path.startswith("/") else f"/{path}"
    if not normalized_prefix:
        return normalized_path
    if normalized_path == "/":
        return normalized_prefix
    return f"{normalized_prefix}{normalized_path}"


def _register_canonical_routes(source_router: APIRouter, tags: list[str], extra_prefix: str = "") -> None:
    for route in source_router.routes:
        canonical_path = _join_path(extra_prefix, _trim_api_prefix(route.path))

        if isinstance(route, APIRoute):
            v1_router.add_api_route(
                canonical_path,
                route.endpoint,
                response_model=route.response_model,
                status_code=route.status_code,
                tags=tags,
                dependencies=route.dependencies,
                summary=route.summary,
                description=route.description,
                response_description=route.response_description,
                responses=route.responses,
                deprecated=route.deprecated,
                methods=route.methods,
                operation_id=route.operation_id,
                response_model_include=route.response_model_include,
                response_model_exclude=route.response_model_exclude,
                response_model_by_alias=route.response_model_by_alias,
                response_model_exclude_unset=route.response_model_exclude_unset,
                response_model_exclude_defaults=route.response_model_exclude_defaults,
                response_model_exclude_none=route.response_model_exclude_none,
                include_in_schema=route.include_in_schema,
                response_class=route.response_class,
                name=route.name,
                callbacks=route.callbacks,
                openapi_extra=route.openapi_extra,
            )
            continue

        if isinstance(route, APIWebSocketRoute):
            v1_router.add_api_websocket_route(
                canonical_path,
                route.endpoint,
                dependencies=route.dependencies,
                name=route.name,
            )


# Keep legacy /api-prefixed V1 aliases for backward compatibility.
v1_router.include_router(quark.router, tags=["Quark"], include_in_schema=False)
v1_router.include_router(strm.router, tags=["STRM"], include_in_schema=False)
v1_router.include_router(proxy.router, tags=["Proxy"], include_in_schema=False)
v1_router.include_router(emby.router, tags=["Emby"], include_in_schema=False)

# Canonical V1 routes.
_register_canonical_routes(quark.router, ["Quark"])
_register_canonical_routes(strm.router, ["STRM"])
_register_canonical_routes(proxy.router, ["Proxy"])
_register_canonical_routes(emby.router, ["Emby"])
_register_canonical_routes(tasks.router, ["Tasks"], extra_prefix="/tasks")

# Routes that already use canonical prefixes.
v1_router.include_router(scrape.router, tags=["Scrape"])
v1_router.include_router(monitoring.router, tags=["Monitor"])
