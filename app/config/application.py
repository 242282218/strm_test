"""
应用配置

负责 FastAPI 应用实例的创建和基础配置。
"""

from fastapi import FastAPI, HTTPException

from app.config.lifecycle import create_lifespan_context
from app.core.logging import get_logger


logger = get_logger(__name__)


def create_fastapi_app(title: str, description: str, version: str, lifespan_context) -> FastAPI:
    """
    创建 FastAPI 应用实例

    Args:
        title: 应用标题
        description: 应用描述
        version: 应用版本
        lifespan_context: 生命周期上下文管理器

    Returns:
        FastAPI 应用实例
    """
    return FastAPI(
        title=title,
        description=description,
        version=version,
        lifespan=lifespan_context,
    )


def register_routers(_app: FastAPI):
    """
    注册所有路由

    Args:
        _app: FastAPI 应用实例
    """
    from app.api import auth as auth_router
    from app.api import (
        cloud_drive,
        dashboard,
        emby,
        emby_gateway,
        file_manager,
        monitoring,
        prometheus,
        proxy,
        quark,
        quark_sdk,
        rename,
        scrape,
        search,
        security,
        smart_rename,
        stable_stream,
        strm,
        strm_validator,
        tasks,
        tmdb,
    )
    from app.api import notification as notification_router
    from app.api.v1 import v1_router

    # 导入模型以确保创建表
    import app.models.cloud_drive
    import app.models.emby
    import app.models.media_mapping
    import app.models.notification
    import app.models.scrape
    import app.models.security_event
    import app.models.task
    import app.models.user

    # 注册传统路由
    register_legacy_routers(_app)

    # 注册 V1 和支持路由
    register_v1_and_support_routers(_app)


def register_legacy_routers(_app: FastAPI):
    """
    注册传统 API 路由（即将废弃）

    Args:
        _app: FastAPI 应用实例
    """
    import warnings
    from app.api import auth as auth_router
    from app.api import (
        cloud_drive,
        dashboard,
        emby,
        file_manager,
        proxy,
        quark,
        quark_sdk,
        rename,
        scrape,
        search,
        smart_rename,
        stable_stream,
        strm,
        strm_validator,
        tasks,
        tmdb,
    )
    from app.api import notification as notification_router
    from app.api import transfer
    from app.api import system_config

    warnings.filterwarnings("default", message=".*deprecated.*", category=DeprecationWarning)

    _app.include_router(quark.router)
    _app.include_router(strm.router)
    _app.include_router(proxy.router)
    _app.include_router(emby.router)
    _app.include_router(scrape.router, prefix="/api")
    _app.include_router(tasks.router, prefix="/api/tasks", tags=["Tasks"])
    _app.include_router(cloud_drive.router, prefix="/api/drives", tags=["Cloud Drives"])
    _app.include_router(strm_validator.router)
    _app.include_router(quark_sdk.router)
    _app.include_router(search.router)
    _app.include_router(rename.router)
    _app.include_router(smart_rename.router)
    _app.include_router(stable_stream.router)
    _app.include_router(dashboard.router)
    _app.include_router(file_manager.router, prefix="/api", tags=["FileManager"])
    _app.include_router(transfer.router)
    _app.include_router(tmdb.router)
    _app.include_router(notification_router.router)
    _app.include_router(system_config.router)


def register_v1_and_support_routers(_app: FastAPI):
    """
    注册 V1 API 和支持路由

    Args:
        _app: FastAPI 应用实例
    """
    from app.api import auth as auth_router
    from app.api import (
        emby_gateway,
        monitoring,
        prometheus,
        security,
    )
    from app.api.v1 import v1_router

    _app.include_router(v1_router, prefix="/api/v1", tags=["API V1"])
    _app.include_router(monitoring.router, prefix="/api", tags=["monitoring"])
    _app.include_router(prometheus.router)
    _app.include_router(auth_router.router)
    _app.include_router(security.router)
    _app.include_router(emby_gateway.router)

    # 注册批量操作 API
    try:
        from app.api import batch_ops
        _app.include_router(batch_ops.router)
    except ImportError as e:
        logger.warning(f"Batch ops router not available: {e}")


def register_exception_handlers(_app: FastAPI):
    """
    注册异常处理器

    Args:
        _app: FastAPI 应用实例
    """
    from fastapi.exceptions import RequestValidationError

    from app.core.exception_handler import (
        app_exception_handler,
        exception_handler,
        http_exception_handler,
        input_validation_exception_handler,
        validation_exception_handler,
    )
    from app.core.exceptions import AppException
    from app.core.validators import InputValidationError

    _app.add_exception_handler(Exception, exception_handler)
    _app.add_exception_handler(AppException, app_exception_handler)
    _app.add_exception_handler(HTTPException, http_exception_handler)
    _app.add_exception_handler(RequestValidationError, validation_exception_handler)
    _app.add_exception_handler(InputValidationError, input_validation_exception_handler)
