"""
Emby反代服务模块

参考: go-emby2openlist internal/service/emby/redirect.go
支持302重定向和PlaybackInfo Hook
"""

import aiohttp
from typing import Optional, Dict, Any
from app.services.emby_api_client import EmbyAPIClient
from app.services.playbackinfo_hook import PlaybackInfoHook
from app.services.quark_service import QuarkService
from app.core.config_manager import get_config
from app.core.logging import get_logger

logger = get_logger(__name__)

# 获取配置管理器
config = get_config()


class EmbyProxyService:
    """
    Emby反代服务

    功能:
    1. 拦截Emby请求
    2. 修改PlaybackInfo响应，强制DirectPlay
    3. 302重定向视频流到夸克直链
    """

    def __init__(
        self,
        emby_base_url: str,
        api_key: str,
        cookie: str,
        proxy_base_url: str = "http://localhost:8000"
    ):
        """
        初始化Emby反代服务

        Args:
            emby_base_url: Emby服务器地址
            api_key: Emby API密钥
            cookie: 夸克Cookie
            proxy_base_url: 代理服务基础URL
        """
        self.emby_base_url = emby_base_url.rstrip('/')
        self.api_key = api_key
        self.cookie = cookie
        self.proxy_base_url = proxy_base_url.rstrip('/')

        # 创建客户端
        self.emby_client: Optional[EmbyAPIClient] = None
        self.quark_service: Optional[QuarkService] = None
        self.playback_hook: Optional[PlaybackInfoHook] = None

        logger.info(f"EmbyProxyService initialized: {self.emby_base_url}")

    async def __aenter__(self):
        """异步上下文管理器进入方法"""
        self.emby_client = EmbyAPIClient(
            base_url=self.emby_base_url,
            api_key=self.api_key
        )
        await self.emby_client.__aenter__()

        self.quark_service = QuarkService(cookie=self.cookie)

        self.playback_hook = PlaybackInfoHook(
            emby_client=self.emby_client,
            quark_service=self.quark_service,
            proxy_base_url=self.proxy_base_url
        )

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器退出方法"""
        if self.emby_client:
            await self.emby_client.__aexit__(exc_type, exc_val, exc_tb)
        if self.quark_service:
            await self.quark_service.close()

    async def proxy_playback_info(
        self,
        item_id: str,
        user_id: str,
        media_source_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        代理PlaybackInfo请求

        参考: go-emby2openlist internal/service/emby/playbackinfo.go

        1. 获取原始PlaybackInfo
        2. Hook响应，强制DirectPlay
        3. 修改DirectStreamUrl为代理地址

        Args:
            item_id: 项目ID
            user_id: 用户ID
            media_source_id: 媒体源ID

        Returns:
            修改后的PlaybackInfo响应
        """
        try:
            # 使用PlaybackInfo Hook修改响应
            playback_info = await self.playback_hook.hook_playback_info(
                item_id=item_id,
                user_id=user_id,
                media_source_id=media_source_id
            )

            logger.info(f"PlaybackInfo hooked for item {item_id}")
            return playback_info

        except Exception as e:
            logger.error(f"Failed to proxy playback info: {str(e)}")
            raise

    async def proxy_stream_request(
        self,
        media_source_id: str,
        file_path: Optional[str] = None
    ) -> str:
        """
        代理视频流请求

        参考: go-emby2openlist internal/service/emby/redirect.go Redirect2OpenlistLink

        1. 检查是否是STRM文件
        2. 如果是STRM，解析文件ID
        3. 获取夸克直链
        4. 返回302重定向URL

        Args:
            media_source_id: 媒体源ID
            file_path: 文件路径（可选）

        Returns:
            302重定向URL
        """
        try:
            # 如果提供了文件路径，直接使用
            if file_path and file_path.lower().endswith('.strm'):
                # 从STRM文件解析文件ID
                file_id = self._extract_file_id_from_strm(file_path)
                if file_id:
                    link = await self.quark_service.get_download_link(file_id)
                    logger.info(f"Stream redirected to quark link: {link.url[:100]}...")
                    return link.url

            # 如果没有文件路径或无法解析，尝试通过Emby API获取
            if self.emby_client:
                # 获取媒体源信息
                # 这里可以实现更复杂的逻辑
                pass

            raise Exception("Unable to get stream URL")

        except Exception as e:
            logger.error(f"Failed to proxy stream request: {str(e)}")
            raise

    def _extract_file_id_from_strm(self, file_path: str) -> Optional[str]:
        """
        从STRM文件路径提取文件ID

        Args:
            file_path: STRM文件路径

        Returns:
            文件ID或None
        """
        try:
            # 假设STRM文件名格式为: {name}_{file_id}.strm
            # 例如: movie_123456789.strm
            import os
            filename = os.path.basename(file_path)
            name_without_ext = os.path.splitext(filename)[0]

            # 尝试从文件名提取ID
            # 这里需要根据实际情况调整
            parts = name_without_ext.rsplit('_', 1)
            if len(parts) == 2:
                return parts[1]

            return None
        except Exception as e:
            logger.error(f"Failed to extract file ID from STRM: {str(e)}")
            return None

    async def get_strm_content(self, file_path: str) -> str:
        """
        读取STRM文件内容

        Args:
            file_path: STRM文件路径

        Returns:
            STRM文件内容（直链URL）
        """
        try:
            # 读取STRM文件
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()

            # 如果内容是夸克文件ID，获取直链
            if content.startswith('quark://'):
                file_id = content.replace('quark://', '')
                link = await self.quark_service.get_download_link(file_id)
                return link.url

            # 否则直接返回内容（假设已经是URL）
            return content

        except Exception as e:
            logger.error(f"Failed to read STRM file: {str(e)}")
            raise

    async def proxy_items_request(
        self,
        item_id: str,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        代理Items请求

        Args:
            item_id: 项目ID
            user_id: 用户ID

        Returns:
            项目信息
        """
        try:
            item_info = await self.emby_client.get_items(
                item_id=item_id,
                user_id=user_id
            )
            return item_info
        except Exception as e:
            logger.error(f"Failed to proxy items request: {str(e)}")
            raise

    async def close(self):
        """关闭服务"""
        if self.emby_client:
            await self.emby_client.__aexit__(None, None, None)
        if self.quark_service:
            await self.quark_service.close()
        logger.debug("EmbyProxyService closed")
