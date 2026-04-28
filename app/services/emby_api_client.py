"""
Emby API客户端模块

参考: go-emby2openlist internal/service/emby/api.go
"""

from typing import Any

import aiohttp

from app.core.logging import get_logger
from app.core.retry import TransientError, retry_on_transient


logger = get_logger(__name__)


class EmbyAPIClient:
    """Emby API客户端"""

    def __init__(self, base_url: str, api_key: str, timeout: int = 30):
        """
        初始化Emby API客户端

        Args:
            base_url: Emby服务器地址
            api_key: Emby API密钥
            timeout: 请求超时时间
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.session: aiohttp.ClientSession | None = None
        logger.info(f"EmbyAPIClient initialized: {self.base_url}")

    async def __aenter__(self):
        """异步上下文管理器进入方法"""
        self.session = aiohttp.ClientSession(timeout=self.timeout)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器退出方法"""
        if self.session:
            await self.session.close()

    def _get_headers(self) -> dict[str, str]:
        """获取请求头"""
        return {"X-Emby-Token": self.api_key, "Accept": "application/json", "Content-Type": "application/json"}

    @retry_on_transient()
    async def _request_json(self, method: str, url: str, **kwargs) -> dict[str, Any]:
        if not self.session:
            raise RuntimeError("Emby client session not initialized")
        async with self.session.request(method, url, headers=self._get_headers(), **kwargs) as response:
            if response.status in {408, 429} or response.status >= 500:
                raise TransientError(f"Emby API transient error: {response.status}")
            if response.status != 200:
                raise Exception(f"Emby API error: {response.status}")
            return await response.json()

    async def get_views(self, user_id: str | None = None) -> list[dict[str, Any]]:
        """获取用户视图（媒体库）"""
        url = f"{self.base_url}/Users/{user_id}/Views" if user_id else f"{self.base_url}/Library/MediaFolders"

        try:
            data = await self._request_json("GET", url)
            return data.get("Items", [])
        except Exception as e:
            logger.error(f"Failed to get views: {e}")
            return []

    async def get_items_by_query(
        self,
        user_id: str | None = None,
        parent_id: str | None = None,
        recursive: bool = True,
        include_item_types: str | None = None,
        fields: str | None = "Path,MediaSources",
    ) -> list[dict[str, Any]]:
        """通用查询获取项目"""
        endpoint = f"/Users/{user_id}/Items" if user_id else "/Items"
        url = f"{self.base_url}{endpoint}"

        params = {
            "Recursive": str(recursive).lower(),
            "Fields": fields,
        }
        if parent_id:
            params["ParentId"] = parent_id
        if include_item_types:
            params["IncludeItemTypes"] = include_item_types

        try:
            data = await self._request_json("GET", url, params=params)
            return data.get("Items", [])
        except Exception as e:
            logger.error(f"Failed to query items: {e}")
            return []

    async def get_items(self, item_id: str, user_id: str | None = None) -> dict[str, Any]:
        """
        获取项目信息

        兼容部分 Emby 服务器不支持 /Items/{id} 的情况，统一走 /Items?Ids=...

        Args:
            item_id: 项目ID
            user_id: 用户ID

        Returns:
            项目信息字典
        """
        url = f"{self.base_url}/Users/{user_id}/Items" if user_id else f"{self.base_url}/Items"
        params: dict[str, Any] = {"Ids": item_id, "Fields": "Path,MediaSources"}
        if user_id:
            params["UserId"] = user_id

        try:
            data = await self._request_json("GET", url, params=params)
            items = data.get("Items", [])
            if not items:
                raise Exception(f"Emby item not found: {item_id}")
            return items[0]
        except Exception as e:
            logger.error(f"Failed to get item {item_id}: {e!s}")
            raise

    async def get_playback_info(
        self,
        item_id: str,
        user_id: str,
        media_source_id: str | None = None,
        max_static_bitrate: int = 140000000,
        max_streaming_bitrate: int = 140000000,
    ) -> dict[str, Any]:
        """
        获取播放信息

        参考: go-emby2openlist internal/service/emby/playbackinfo.go

        Args:
            item_id: 项目ID
            user_id: 用户ID
            media_source_id: 媒体源ID
            max_static_bitrate: 最大静态码率
            max_streaming_bitrate: 最大流媒体码率

        Returns:
            播放信息字典
        """
        url = f"{self.base_url}/Items/{item_id}/PlaybackInfo"
        params: dict[str, Any] = {
            "UserId": user_id,
            "MaxStaticBitrate": max_static_bitrate,
            "MaxStreamingBitrate": max_streaming_bitrate,
        }
        if media_source_id is not None:
            params["MediaSourceId"] = media_source_id

        try:
            return await self._request_json("GET", url, params=params)
        except Exception as e:
            logger.error(f"Failed to get playback info for {item_id}: {e!s}")
            raise

    async def post_playback_info(
        self,
        item_id: str,
        user_id: str,
        device_profile: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        POST请求获取播放信息

        参考: go-emby2openlist internal/service/emby/playbackinfo.go

        Args:
            item_id: 项目ID
            user_id: 用户ID
            device_profile: 设备配置文件

        Returns:
            播放信息字典
        """
        url = f"{self.base_url}/Items/{item_id}/PlaybackInfo?UserId={user_id}"
        if device_profile is None:
            device_profile = self._get_default_device_profile()

        try:
            return await self._request_json("POST", url, json=device_profile)
        except Exception as e:
            logger.error(f"Failed to post playback info for {item_id}: {e!s}")
            raise

    def _get_default_device_profile(self) -> dict[str, Any]:
        """
        获取默认设备配置文件

        参考: go-emby2openlist internal/service/emby/playbackinfo.go PlaybackCommonPayload

        Returns:
            设备配置文件字典
        """
        return {
            "DeviceProfile": {
                "MaxStaticBitrate": 140000000,
                "MaxStreamingBitrate": 140000000,
                "MusicStreamingTranscodingBitrate": 192000,
                "DirectPlayProfiles": [
                    {
                        "Container": "mp4,m4v",
                        "Type": "Video",
                        "VideoCodec": "h264,h265,hevc,av1,vp8,vp9",
                        "AudioCodec": "mp3,aac,opus,flac,vorbis",
                    },
                    {
                        "Container": "mkv",
                        "Type": "Video",
                        "VideoCodec": "h264,h265,hevc,av1,vp8,vp9",
                        "AudioCodec": "mp3,aac,opus,flac,vorbis",
                    },
                    {"Container": "flv", "Type": "Video", "VideoCodec": "h264", "AudioCodec": "aac,mp3"},
                    {"Container": "3gp", "Type": "Video", "VideoCodec": "", "AudioCodec": "mp3,aac,opus,flac,vorbis"},
                    {
                        "Container": "mov",
                        "Type": "Video",
                        "VideoCodec": "h264",
                        "AudioCodec": "mp3,aac,opus,flac,vorbis",
                    },
                    {"Container": "opus", "Type": "Audio"},
                    {"Container": "mp3", "Type": "Audio", "AudioCodec": "mp3"},
                    {"Container": "mp2,mp3", "Type": "Audio", "AudioCodec": "mp2"},
                    {"Container": "m4a", "AudioCodec": "aac", "Type": "Audio"},
                    {"Container": "mp4", "AudioCodec": "aac", "Type": "Audio"},
                    {"Container": "flac", "Type": "Audio"},
                    {"Container": "webma,webm", "Type": "Audio"},
                    {"Container": "wav", "Type": "Audio", "AudioCodec": "PCM_S16LE,PCM_S24LE"},
                    {"Container": "ogg", "Type": "Audio"},
                    {"Container": "webm", "Type": "Video", "AudioCodec": "vorbis,opus", "VideoCodec": "av1,VP8,VP9"},
                ],
                "TranscodingProfiles": [
                    {
                        "Container": "aac",
                        "Type": "Audio",
                        "AudioCodec": "aac",
                        "Context": "Streaming",
                        "Protocol": "hls",
                        "MaxAudioChannels": "2",
                        "MinSegments": "1",
                        "BreakOnNonKeyFrames": True,
                    },
                    {
                        "Container": "aac",
                        "Type": "Audio",
                        "AudioCodec": "aac",
                        "Context": "Streaming",
                        "Protocol": "http",
                        "MaxAudioChannels": "2",
                    },
                    {
                        "Container": "mp3",
                        "Type": "Audio",
                        "AudioCodec": "mp3",
                        "Context": "Streaming",
                        "Protocol": "http",
                        "MaxAudioChannels": "2",
                    },
                    {
                        "Container": "opus",
                        "Type": "Audio",
                        "AudioCodec": "opus",
                        "Context": "Streaming",
                        "Protocol": "http",
                        "MaxAudioChannels": "2",
                    },
                    {
                        "Container": "wav",
                        "Type": "Audio",
                        "AudioCodec": "wav",
                        "Context": "Streaming",
                        "Protocol": "http",
                        "MaxAudioChannels": "2",
                    },
                    {
                        "Container": "opus",
                        "Type": "Audio",
                        "AudioCodec": "opus",
                        "Context": "Static",
                        "Protocol": "http",
                        "MaxAudioChannels": "2",
                    },
                    {
                        "Container": "mp3",
                        "Type": "Audio",
                        "AudioCodec": "mp3",
                        "Context": "Static",
                        "Protocol": "http",
                        "MaxAudioChannels": "2",
                    },
                ],
            }
        }

    async def close(self):
        """关闭客户端"""
        if self.session:
            await self.session.close()
            logger.debug("EmbyAPIClient closed")
