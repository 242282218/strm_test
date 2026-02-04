"""
PlaybackInfo Hook服务模块

参考: go-emby2openlist internal/service/emby/playbackinfo.go
"""

import asyncio
import os
from typing import Dict, Any, Optional
from app.services.emby_api_client import EmbyAPIClient
from app.services.quark_service import QuarkService
from app.core.logging import get_logger
from app.utils.strm_url import (
    build_proxy_url,
    extract_file_id_from_proxy_url,
    extract_file_id_from_strm_content,
    read_strm_file_content,
)

logger = get_logger(__name__)


class PlaybackInfoHook:
    """
    PlaybackInfo Hook服务

    用于拦截和修改Emby的PlaybackInfo响应，强制DirectPlay/DirectStream
    """

    def __init__(
        self,
        emby_client: EmbyAPIClient,
        quark_service: QuarkService,
        proxy_base_url: str
    ):
        """
        初始化PlaybackInfo Hook服务

        Args:
            emby_client: Emby API客户端
            quark_service: 夸克服务
            proxy_base_url: 代理服务基础URL
        """
        self.emby_client = emby_client
        self.quark_service = quark_service
        self.proxy_base_url = proxy_base_url.rstrip('/')
        logger.info("PlaybackInfoHook initialized")

    async def hook_playback_info(
        self,
        item_id: str,
        user_id: str,
        media_source_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Hook PlaybackInfo接口

        参考: go-emby2openlist internal/service/emby/playbackinfo.go TransferPlaybackInfo

        Args:
            item_id: 项目ID
            user_id: 用户ID
            media_source_id: 媒体源ID

        Returns:
            修改后的PlaybackInfo响应
        """
        try:
            # 1. 获取原始PlaybackInfo
            playback_info = await self.emby_client.get_playback_info(
                item_id=item_id,
                user_id=user_id,
                media_source_id=media_source_id
            )

            # 2. 检查是否有MediaSources
            media_sources = playback_info.get("MediaSources", [])
            if not media_sources:
                logger.debug(f"No MediaSources found for item {item_id}")
                return playback_info

            # 3. 处理每个MediaSource
            modified_sources = []
            for source in media_sources:
                modified_source = await self._process_media_source(
                    source,
                    item_id,
                    user_id
                )
                if modified_source:
                    modified_sources.append(modified_source)

            # 4. 更新PlaybackInfo
            playback_info["MediaSources"] = modified_sources

            logger.debug(f"Hooked PlaybackInfo for item {item_id}")
            return playback_info

        except Exception as e:
            logger.error(f"Failed to hook playback info for {item_id}: {str(e)}")
            raise

    async def _process_media_source(
        self,
        source: Dict[str, Any],
        item_id: str,
        user_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        处理单个MediaSource

        参考: go-emby2openlist internal/service/emby/playbackinfo.go

        Args:
            source: MediaSource字典
            item_id: 项目ID
            user_id: 用户ID

        Returns:
            处理后的MediaSource字典
        """
        try:
            # 检查是否是无限流（电视直播）
            is_infinite_stream = source.get("IsInfiniteStream", False)
            if is_infinite_stream:
                logger.debug("Skipping infinite stream")
                return None

            # 检查是否是本地媒体
            path = source.get("Path", "")
            if self._is_local_media(path):
                logger.debug(f"Local media: {path}, skip processing")
                return source

            # 检查是否是远程资源
            is_remote = source.get("IsRemote", False)

            # 强制DirectPlay/DirectStream
            source["SupportsDirectPlay"] = True
            source["SupportsDirectStream"] = True

            # 设置DirectStreamUrl
            media_source_id = source.get("Id", "")
            file_id = None
            if path:
                file_id = extract_file_id_from_proxy_url(path)
                if not file_id and path.lower().endswith(".strm") and os.path.exists(path):
                    content = await read_strm_file_content(path)
                    file_id = extract_file_id_from_strm_content(content)
            target_id = file_id or media_source_id
            new_url = f"{build_proxy_url(self.proxy_base_url, target_id, mode='stream')}?Static=true"
            source["DirectStreamUrl"] = new_url

            # 禁用转码
            source["SupportsTranscoding"] = False
            source.pop("TranscodingUrl", None)
            source.pop("TranscodingSubProtocol", None)
            source.pop("TranscodingContainer", None)

            # 如果是远程资源，不获取转码地址
            if is_remote:
                logger.debug(f"Remote media source: {media_source_id}, skip transcoding")
                return source

            # TODO: 添加转码MediaSource获取逻辑
            # 参考: go-emby2openlist findVideoPreviewInfos

            logger.debug(f"Processed media source: {media_source_id}")
            return source

        except Exception as e:
            logger.error(f"Failed to process media source: {str(e)}")
            return source

    def _is_local_media(self, path: str) -> bool:
        """
        检查是否是本地媒体

        参考: go-emby2openlist internal/service/emby/playbackinfo.go

        Args:
            path: 媒体路径

        Returns:
            是否是本地媒体
        """
        # 检查是否是STRM文件
        if path.lower().endswith('.strm'):
            return False

        # 检查是否是http/https协议
        if path.startswith('http://') or path.startswith('https://'):
            return False

        # 其他情况认为是本地媒体
        return True

    async def close(self):
        """关闭服务"""
        logger.debug("PlaybackInfoHook closed")
