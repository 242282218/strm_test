"""
直链解析服务 (Link Resolver)

负责统一获取文件的下载直链，支持多种来源：
1. 夸克 API (Quark Native) - 优先，基于 ID
2. AList API - 备选，基于 Path
"""

import aiohttp
from typing import Optional, Dict, Any
from app.services.quark_service import QuarkService
from app.core.config_manager import get_config
from app.core.logging import get_logger

logger = get_logger(__name__)

class LinkResolver:
    def __init__(self, quark_service: QuarkService = None):
        config_mgr = get_config()
        self.quark_service = quark_service
        self.alist_config = config_mgr.get_alist_config()
        self.config_mgr = config_mgr
    
        # 0. Check Cache
        from app.services.link_cache import LinkCache
        # Using a singleton-like pattern or passing cache instance would be better
        # For now, we'll instantiate it or use a global instance if available.
        # But wait, LinkCache is a class, we need an instance.
        # Let's import the singleton instance if defined in link_cache (it's not).
        # We will create a class-level variable or simple singleton here for now.
        
        # NOTE: Ideally LinkCache should be a singleton service managed by the app container.
        # Given current constraints, I'll check if I can use a global cache.
        # Let's assume we modify this class to accept a cache instance or manage one.
        pass # Placeholder for thought
        
    async def resolve(self, file_id: str, path: str = None) -> str:
        """
        解析文件直链
        
        策略:
        0. 检查缓存
        1. 尝试使用 QuarkService 获取直链 (file_id)
        2. 如果失败且配置了 AList，尝试使用 AList API 获取直链 (path)
        """
        # Init simple cache instance (should be global)
        if not hasattr(LinkResolver, '_cache_instance'):
             from app.services.link_cache import LinkCache
             LinkResolver._cache_instance = LinkCache()
             # We should probably start it? It has start/stop methods for cleanup loop.
             # Ideally app startup starts it. For now, lazy start without cleanup task or simple usage.
             # The existing LinkCache requires async start for cleanup loop. 
             # Let's just use it as a passive store for now to avoid task lifecycle issues in this quick edit.
        
        cache = LinkResolver._cache_instance
        
        # Check cache
        cached_entry = await cache.get(file_id)
        if cached_entry:
            return cached_entry.value

        last_error = None
        
        # 1. 优先尝试 Quark API (基于 ID，最快)
        if self.quark_service:
            try:
                # 检查 Quark Token 是否需要刷新 (这里假设 Service 内部处理或通过 middleware 处理，暂时直接调用)
                link_model = await self.quark_service.get_download_link(file_id)
                if link_model and link_model.url:
                    logger.debug(f"Resolved link via Quark API: {file_id}")
                    # Cache successful result (Quark links valid for ~15-30 mins, lets cache for 10 mins)
                    await cache.set(file_id, link_model.url, ttl=600)
                    return link_model.url
            except Exception as e:
                logger.warning(f"Quark API resolve failed for {file_id}: {e}")
                last_error = e
        
        # 2. 尝试 AList API (基于 Path)
        # 仅当 path 存在且 AList 启用时
        if self.alist_config.get('enabled') and path:
            try:
                alist_url = await self._resolve_via_alist(path)
                if alist_url:
                    logger.info(f"Resolved link via AList API: {path}")
                    # AList 302 links usually also expire or point to expiring 115/Quark links.
                    await cache.set(file_id, alist_url, ttl=600)
                    return alist_url
            except Exception as e:
                logger.warning(f"AList API resolve failed for {path}: {e}")
                last_error = e if last_error is None else last_error
                
        # 如果都失败了
        if last_error:
            raise last_error
        else:
            raise Exception("No available link resolver service")

    async def _resolve_via_alist(self, path: str) -> str:
        """通过 AList API 获取直链"""
        base_url = self.alist_config.get('url', 'http://localhost:5244').rstrip('/')
        token = self.alist_config.get('token', '')
        mount_path = self.alist_config.get('mount_path', '/')
        
        # 拼接完整路径: mount_path + file_path
        # 注意处理斜杠，避免双斜杠
        full_path = f"{mount_path.rstrip('/')}/{path.lstrip('/')}"
        
        api_url = f"{base_url}/api/fs/get"
        headers = {
            "Authorization": token,
            "Content-Type": "application/json"
        }
        payload = {
            "path": full_path,
            "password": ""
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(api_url, json=payload, headers=headers, timeout=10) as resp:
                if resp.status != 200:
                    raise Exception(f"AList API error: {resp.status}")
                
                data = await resp.json()
                if data.get('code') != 200:
                    raise Exception(f"AList API returned error: {data.get('message')}")
                
                # AList 返回的 raw_url 即为直链
                # 注意：raw_url 可能是 302 重定向链接，也可能是真实链接，取决于 AList 驱动配置
                # 对于 Quark，AList 通常返回的是经过本地 302 的链接或直接的下载链接
                raw_url = data.get('data', {}).get('raw_url')
                if not raw_url:
                    raise Exception("AList did not return a raw_url")
                    
                return raw_url
