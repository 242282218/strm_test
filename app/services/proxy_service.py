"""
代理服务模块

参考: MediaHelp proxy.py
"""

import asyncio
import aiohttp

from typing import Optional, Tuple
from app.services.quark_service import QuarkService
from app.services.link_cache import LinkCache, get_link_cache_service
from app.core.logging import get_logger

logger = get_logger(__name__)


class ProxyService:
    """代理服务"""

    def __init__(
        self,
        cookie: str,
        cache_ttl: int = 600,
        max_cache_size: int = 1000,
        link_cache: Optional[LinkCache] = None
    ):
        """
        初始化代理服务

        Args:
            cookie: 夸克Cookie
            cache_ttl: 缓存TTL（秒）
            max_cache_size: 最大缓存条目数
            concurrency_limit: 并发限制
        """
        self.cookie = cookie
        self.quark_service = QuarkService(cookie)
        self.link_cache = link_cache or get_link_cache_service(
            default_ttl=cache_ttl,
            max_size=max_cache_size
        )
        if not hasattr(ProxyService, "_global_semaphore"):
            ProxyService._global_semaphore = asyncio.Semaphore(50)
        self.semaphore = ProxyService._global_semaphore
        logger.info("ProxyService initialized")

    async def __aenter__(self):
        """
        异步上下文管理器进入方法
        """
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        异步上下文管理器退出方法
        """
        await self.close()

    async def get_download_url(self, file_id: str) -> str:
        """
        获取下载直链 (带缓存)

        Args:
            file_id: 文件ID

        Returns:
            下载地址
        """
        # 复用 redirect_302 的逻辑
        return await self.redirect_302(file_id)

    async def redirect_302(self, file_id: str) -> str:
        """
        302重定向

        Args:
            file_id: 文件ID

        Returns:
            重定向URL
        """
        try:
            # 检查缓存
            cached_entry = await self.link_cache.get(file_id)

            if cached_entry:
                logger.debug(f"Cache hit for redirect {file_id}")
                return cached_entry.value

            async with self.semaphore:
                link = await self.quark_service.get_download_link(file_id)

            # 缓存直链
            await self.link_cache.set(
                file_id=file_id,
                value=link.url,
                headers=link.headers
            )

            logger.debug(f"302 redirect for {file_id} to {link.url}")
            return link.url
        except Exception as e:
            logger.error(f"Failed to get redirect URL for {file_id}: {str(e)}")
            raise

    async def clear_cache(self):
        """清除缓存"""
        await self.link_cache.clear()
        logger.info("Cache cleared")

    async def get_cache_stats(self):
        """获取缓存统计"""
        return self.link_cache.get_stats()

    async def close(self):
        """关闭服务"""
        await self.quark_service.close()
        logger.debug("ProxyService closed")
