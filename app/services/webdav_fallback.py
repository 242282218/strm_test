"""
WebDAV 兜底服务 (WebDAV Fallback)

当所有直链获取方式都失败时，生成 WebDAV URL 以供播放器尝试播放。
"""

from urllib.parse import quote
from app.services.config_service import get_config
from app.core.logging import get_logger

logger = get_logger(__name__)

class WebDAVFallback:
    def __init__(self):
        self.config_mgr = get_config()
        self.webdav_config = self.config_mgr.get_webdav_config()

    def get_fallback_url(self, path: str) -> str:
        """
        生成 WebDAV 播放链接
        
        Args:
            path: 文件相对路径 (e.g. "Movies/Avatar.mp4")
            
        Returns:
            str: WebDAV URL
        """
        if not self.webdav_config.get('enabled') or not self.webdav_config.get('fallback_enabled'):
            return None
            
        base_url = self.webdav_config.get('url', 'http://localhost:5244/dav').rstrip('/')
        mount_path = self.webdav_config.get('mount_path', '/')
        username = self.webdav_config.get('username', '')
        password = self.webdav_config.get('password', '')

        def _norm_prefix(p: str) -> str:
            v = (p or "").strip()
            if not v or v == "/":
                return ""
            if not v.startswith("/"):
                v = "/" + v
            return v.rstrip("/")

        # clean and join path parts:
        # - base_url may already contain '/dav'
        # - mount_path may also be configured as '/dav'
        # avoid producing '/dav/dav/...'
        clean_path = (path or "").lstrip("/")

        from urllib.parse import urlparse, urlunparse

        parsed = urlparse(base_url)
        base_path = _norm_prefix(parsed.path)
        mount_prefix = _norm_prefix(mount_path)

        if not mount_prefix:
            prefix = base_path
        elif not base_path:
            prefix = mount_prefix
        elif base_path == mount_prefix:
            prefix = base_path
        elif mount_prefix.startswith(base_path + "/"):
            prefix = mount_prefix
        elif base_path.startswith(mount_prefix + "/"):
            prefix = base_path
        else:
            prefix = base_path + mount_prefix

        file_path = "/" + clean_path if clean_path else ""
        final_path = f"{prefix}{file_path}" if prefix else (file_path or "/")
        encoded_path = quote(final_path, safe="/")

        netloc = parsed.netloc
        if username and password and '@' not in netloc:
            netloc = f"{quote(username)}:{quote(password)}@{netloc}"

        fallback_url = urlunparse((parsed.scheme, netloc, encoded_path, '', '', ''))
        
        logger.debug(f"Generated WebDAV fallback URL: {fallback_url}")
        return fallback_url
