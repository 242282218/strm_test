"""
依赖注入
"""

from fastapi import Depends, HTTPException, status
from app.core.config_manager import get_config
from app.core.logging import get_logger

logger = get_logger(__name__)
config = get_config()


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
