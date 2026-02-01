"""
Emby API客户端模块

参考: go-emby2openlist internal/service/emby/api.go
"""

import aiohttp
from typing import Optional, Dict, Any
from app.core.logging import get_logger

logger = get_logger(__name__)


class EmbyAPIClient:
    """Emby API客户端"""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout: int = 30
    ):
        """
        初始化Emby API客户端

        Args:
            base_url: Emby服务器地址
            api_key: Emby API密钥
            timeout: 请求超时时间
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.session: Optional[aiohttp.ClientSession] = None
        logger.info(f"EmbyAPIClient initialized: {self.base_url}")

    async def __aenter__(self):
        """异步上下文管理器进入方法"""
        self.session = aiohttp.ClientSession(timeout=self.timeout)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器退出方法"""
        if self.session:
            await self.session.close()

    def _get_headers(self) -> Dict[str, str]:
        """获取请求头"""
        return {
            "X-Emby-Token": self.api_key,
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

    async def get_items(
        self,
        item_id: str,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        获取项目信息

        参考: go-emby2openlist internal/service/emby/items.go

        Args:
            item_id: 项目ID
            user_id: 用户ID

        Returns:
            项目信息字典
        """
        url = f"{self.base_url}/Users/{user_id}/Items/{item_id}" if user_id else f"{self.base_url}/Items/{item_id}"
        params = {}
        if user_id:
            params["UserId"] = user_id

        try:
            async with self.session.get(url, headers=self._get_headers(), params=params) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(f"Failed to get item {item_id}: status {response.status}")
                    raise Exception(f"Failed to get item: {response.status}")
        except Exception as e:
            logger.error(f"Failed to get item {item_id}: {str(e)}")
            raise

    async def get_playback_info(
        self,
        item_id: str,
        user_id: str,
        media_source_id: Optional[str] = None,
        max_static_bitrate: int = 140000000,
        max_streaming_bitrate: int = 140000000
    ) -> Dict[str, Any]:
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
        params = {
            "UserId": user_id,
            "MaxStaticBitrate": max_static_bitrate,
            "MaxStreamingBitrate": max_streaming_bitrate,
            "MediaSourceId": media_source_id
        }

        try:
            async with self.session.get(url, headers=self._get_headers(), params=params) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(f"Failed to get playback info for {item_id}: status {response.status}")
                    raise Exception(f"Failed to get playback info: {response.status}")
        except Exception as e:
            logger.error(f"Failed to get playback info for {item_id}: {str(e)}")
            raise

    async def post_playback_info(
        self,
        item_id: str,
        user_id: str,
        device_profile: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
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
            async with self.session.post(url, headers=self._get_headers(), json=device_profile) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(f"Failed to post playback info for {item_id}: status {response.status}")
                    raise Exception(f"Failed to post playback info: {response.status}")
        except Exception as e:
            logger.error(f"Failed to post playback info for {item_id}: {str(e)}")
            raise

    def _get_default_device_profile(self) -> Dict[str, Any]:
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
                        "AudioCodec": "mp3,aac,opus,flac,vorbis"
                    },
                    {
                        "Container": "mkv",
                        "Type": "Video",
                        "VideoCodec": "h264,h265,hevc,av1,vp8,vp9",
                        "AudioCodec": "mp3,aac,opus,flac,vorbis"
                    },
                    {
                        "Container": "flv",
                        "Type": "Video",
                        "VideoCodec": "h264",
                        "AudioCodec": "aac,mp3"
                    },
                    {
                        "Container": "3gp",
                        "Type": "Video",
                        "VideoCodec": "",
                        "AudioCodec": "mp3,aac,opus,flac,vorbis"
                    },
                    {
                        "Container": "mov",
                        "Type": "Video",
                        "VideoCodec": "h264",
                        "AudioCodec": "mp3,aac,opus,flac,vorbis"
                    },
                    {
                        "Container": "opus",
                        "Type": "Audio"
                    },
                    {
                        "Container": "mp3",
                        "Type": "Audio",
                        "AudioCodec": "mp3"
                    },
                    {
                        "Container": "mp2,mp3",
                        "Type": "Audio",
                        "AudioCodec": "mp2"
                    },
                    {
                        "Container": "m4a",
                        "AudioCodec": "aac",
                        "Type": "Audio"
                    },
                    {
                        "Container": "mp4",
                        "AudioCodec": "aac",
                        "Type": "Audio"
                    },
                    {
                        "Container": "flac",
                        "Type": "Audio"
                    },
                    {
                        "Container": "webma,webm",
                        "Type": "Audio"
                    },
                    {
                        "Container": "wav",
                        "Type": "Audio",
                        "AudioCodec": "PCM_S16LE,PCM_S24LE"
                    },
                    {
                        "Container": "ogg",
                        "Type": "Audio"
                    },
                    {
                        "Container": "webm",
                        "Type": "Video",
                        "AudioCodec": "vorbis,opus",
                        "VideoCodec": "av1,VP8,VP9"
                    }
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
                        "BreakOnNonKeyFrames": True
                    },
                    {
                        "Container": "aac",
                        "Type": "Audio",
                        "AudioCodec": "aac",
                        "Context": "Streaming",
                        "Protocol": "http",
                        "MaxAudioChannels": "2"
                    },
                    {
                        "Container": "mp3",
                        "Type": "Audio",
                        "AudioCodec": "mp3",
                        "Context": "Streaming",
                        "Protocol": "http",
                        "MaxAudioChannels": "2"
                    },
                    {
                        "Container": "opus",
                        "Type": "Audio",
                        "AudioCodec": "opus",
                        "Context": "Streaming",
                        "Protocol": "http",
                        "MaxAudioChannels": "2"
                    },
                    {
                        "Container": "wav",
                        "Type": "Audio",
                        "AudioCodec": "wav",
                        "Context": "Streaming",
                        "Protocol": "http",
                        "MaxAudioChannels": "2"
                    },
                    {
                        "Container": "opus",
                        "Type": "Audio",
                        "AudioCodec": "opus",
                        "Context": "Static",
                        "Protocol": "http",
                        "MaxAudioChannels": "2"
                    },
                    {
                        "Container": "mp3",
                        "Type": "Audio",
                        "AudioCodec": "mp3",
                        "Context": "Static",
                        "Protocol": "http",
                        "MaxAudioChannels": "2"
                    }
                ]
            }
        }

    async def close(self):
        """关闭客户端"""
        if self.session:
            await self.session.close()
            logger.debug("EmbyAPIClient closed")
