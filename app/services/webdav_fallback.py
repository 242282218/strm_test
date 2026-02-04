"""
WebDAV 兜底服务 (WebDAV Fallback)

当所有直链获取方式都失败时，生成 WebDAV URL 以供播放器尝试播放。
"""

from urllib.parse import quote
from app.core.config_manager import get_config
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
        mount_path = self.webdav_config.get('mount_path', '/').rstrip('/')
        username = self.webdav_config.get('username', '')
        password = self.webdav_config.get('password', '')
        
        # 拼接路径
        clean_path = path.lstrip('/')
        full_path_str = f"{mount_path}/{clean_path}" if mount_path else f"/{clean_path}"
        
        # URL 编码路径部分 (WebDAV 对特殊字符敏感)
        # 注意：quote 会转义 /，我们需要保留路径分隔符
        # 通常 WebDAV 客户端希望每个 path segment 被编码，但保留 /
        encoded_path = quote(full_path_str) 
        # 上面的 quote 默认 safe='/'，所以 / 不会被转义，符合预期
        # 但如果 path 中包含已编码字符，可能需要先解码? 假设传入的是原始路径
        
        # 构造 URL
        # 如果需要认证，可以在 URL 中嵌入 (不推荐但部分播放器支持) 
        # 或者仅仅返回 URL，播放器之后会弹窗? 
        # Emby 对 strm 中的 http auth 支持有限，但如果是 redirect 302 到 WebDAV Endpoint...
        
        # 最佳实践：
        # 如果是 302 重定向给 Emby，Emby 会作为客户端请求该 URL。
        # 如果 WebDAV 需要密码，Emby 可能无法自动提供（除非 URL 里带了）
        # 格式: http://user:pass@host/dav/...
        
        from urllib.parse import urlparse, urlunparse
        
        parsed = urlparse(base_url)
        netloc = parsed.netloc
        
        if username and password:
            # 插入 user:pass
            if '@' not in netloc:
                netloc = f"{quote(username)}:{quote(password)}@{netloc}"
        
        # 重新组装 base_url
        final_base = urlunparse((parsed.scheme, netloc, parsed.path, '', '', ''))
        final_base = final_base.rstrip('/')
        
        # 最终 URL
        fallback_url = f"{final_base}{encoded_path}"
        
        logger.debug(f"Generated WebDAV fallback URL: {fallback_url}")
        return fallback_url
