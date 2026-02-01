"""
代理服务模块

参考: MediaHelp proxy.py
"""

import aiohttp
from typing import Optional, Tuple
from app.services.quark_service import QuarkService
from app.services.link_cache import LinkCache
from app.core.logging import get_logger

logger = get_logger(__name__)


class ProxyService:
    """代理服务"""

    def __init__(
        self,
        cookie: str,
        cache_ttl: int = 600,
        max_cache_size: int = 1000
    ):
        """
        初始化代理服务

        Args:
            cookie: 夸克Cookie
            cache_ttl: 缓存TTL（秒）
            max_cache_size: 最大缓存条目数
        """
        self.cookie = cookie
        self.quark_service = QuarkService(cookie)
        self.link_cache = LinkCache(
            default_ttl=cache_ttl,
            max_size=max_cache_size
        )
        logger.info("ProxyService initialized")

    async def __aenter__(self):
        """
        异步上下文管理器进入方法
        """
        await self.link_cache.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        异步上下文管理器退出方法
        """
        await self.link_cache.stop()
        await self.close()

    async def proxy_stream(
        self,
        file_id: str,
        range_header: Optional[str] = None
    ) -> Tuple[aiohttp.ClientResponse, Optional[dict]]:
        """
        代理视频流

        参考: MediaHelp proxy.py

        Args:
            file_id: 文件ID
            range_header: Range请求头

        Returns:
            (响应对象, 响应头字典)
        """
        try:
            # 检查缓存（忽略Range）
            cached_entry = await self.link_cache.get(file_id, range_header=None)

            if cached_entry:
                logger.debug(f"Cache hit for {file_id}")
                return cached_entry.value, cached_entry.headers

            # 获取直链
            link = await self.quark_service.get_download_link(file_id)

            # 创建aiohttp客户端
            async with aiohttp.ClientSession() as session:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Referer": "https://pan.quark.cn/",
                    "Accept": "*/*",
                }

                # 处理Range请求
                if range_header:
                    headers["Range"] = range_header

                async with session.get(
                    link.url,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status != 200 and response.status != 206:
                        error_msg = f"Failed to proxy stream: status {response.status}"
                        logger.error(error_msg)
                        raise Exception(error_msg)

                    # 构建响应头
                    response_headers = {
                        "Content-Type": response.headers.get("Content-Type", "video/mp4"),
                        "Accept-Ranges": response.headers.get("Accept-Ranges", "bytes"),
                        "Content-Length": response.headers.get("Content-Length"),
                        "Content-Range": response.headers.get("Content-Range"),
                        "Cache-Control": f"public, max-age={self.link_cache.default_ttl}",
                        "Access-Control-Allow-Origin": "*",
                    }

                    # 缓存响应（忽略Range）
                    await self.link_cache.set(
                        file_id=file_id,
                        value=response,
                        headers=response_headers,
                        range_header=None
                    )

                    logger.debug(f"Proxied stream for {file_id}, status: {response.status}")
                    return response, response_headers

        except Exception as e:
            logger.error(f"Failed to proxy stream {file_id}: {str(e)}")
            raise

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
