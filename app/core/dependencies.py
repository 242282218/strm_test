"""
依赖注入
"""

import os
import secrets
from fastapi import Depends, HTTPException, status, Header
from app.core.config_manager import get_config
from app.services.config_service import get_config_service
from app.core.logging import get_logger

logger = get_logger(__name__)
config = get_config()
config_service = get_config_service()

def _extract_bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip()
    return None

def _get_security_config():
    try:
        cfg = config_service.get_config()
        security = getattr(cfg, "security", None)
        if security:
            return security.api_key or None, bool(security.require_api_key)
    except Exception as exc:
        logger.warning(f"Failed to read security config: {exc}")
    return None, False


async def require_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> None:
    expected = os.getenv("SMART_MEDIA_API_KEY") or os.getenv("API_KEY")
    config_key, require_flag = _get_security_config()
    if not expected and config_key:
        expected = config_key

    if not expected and not require_flag:
        return
    if not expected and require_flag:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API key required but not configured",
        )

    provided = x_api_key or _extract_bearer(authorization)
    if not provided:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key is required",
        )
    if not secrets.compare_digest(provided, expected):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key",
        )

async def get_quark_cookie(cookie: str = None) -> str:
    """
    获取夸克Cookie依赖

    Args:
        cookie: 可选的Cookie参数

    Returns:
        Cookie字符串

    Raises:
        HTTPException: 当Cookie未配置时
    """
    cookie = cookie or config.get_quark_cookie()

    if not cookie:
        logger.warning("Cookie not configured")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cookie is required. Please provide cookie parameter or set it in config.yaml"
        )

    return cookie

async def get_only_video_flag(only_video: bool = None) -> bool:
    """
    获取only_video标志依赖

    Args:
        only_video: 可选的only_video参数

    Returns:
        only_video布尔值
    """
    if only_video is None:
        only_video = config.get_quark_only_video()

    return only_video

async def get_root_id(root_id: str = None) -> str:
    """
    获取根目录ID依赖

    Args:
        root_id: 可选的root_id参数

    Returns:
        根目录ID
    """
    root_id = root_id or config.get_quark_root_id()
    return root_id
