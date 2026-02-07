from wsgidav.wsgidav_app import WsgiDAVApp
from wsgidav.dc.simple_dc import SimpleDomainController
from app.services.config_service import get_config_service
from app.core.logging import get_logger
from .provider import QuarkDAVProvider

logger = get_logger(__name__)

def get_webdav_app():
    """创建一个 WsgiDAV 应用实例"""
    
    config_service = get_config_service()
    sys_config = config_service.get_config()
    webdav_config = sys_config.webdav
    
    if not webdav_config or not webdav_config.enabled:
        logger.info("WebDAV service is disabled in configuration.")
        return None

    logger.info(f"Initializing WebDAV service at {webdav_config.mount_path}")
    
    username = (webdav_config.username or "").strip()
    password = (webdav_config.password or "").strip()
    if not username or not password:
        logger.error("WebDAV credentials are required when WebDAV is enabled; service will not start")
        return None
    
    # 构造 WsgiDAV 配置
    config = {
        "mount_path": webdav_config.mount_path,
        "provider_mapping": {
            "/": QuarkDAVProvider()
        },
        "simple_dc": {
            "user_mapping": {
                "*": {
                    username: {"password": password}
                }
            }
        },
        "verbose": 1,
        "dir_browser": {
            "enable": True,          # 允许在浏览器中列出目录
            "response_trailer": True, # 显示页脚
        },
        "http_authenticator": {
            "accept_basic": True,
            "accept_digest": True,
            "default_to_digest": True,
        },
    }
    
    return WsgiDAVApp(config)
