"""
PlaybackInfo Hook服务模块

参考: go-emby2openlist internal/service/emby/playbackinfo.go
"""

import os
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit

from app.core.logging import get_logger
from app.services.emby_api_client import EmbyAPIClient
from app.services.playback_decision_service import PlaybackDecisionService
from app.services.quark_service import QuarkService
from app.utils.strm_url import (
    build_proxy_url,
    extract_file_id_from_proxy_url,
    extract_file_id_from_strm_content,
    is_stable_media_url,
    read_strm_file_content,
)


logger = get_logger(__name__)
LOCAL_PLAYBACK_PROXY_QUERY_KEY = "smart_media_proxy"
LOCAL_PLAYBACK_PROXY_QUERY_VALUE = "1"


class PlaybackInfoHook:
    """
    PlaybackInfo Hook服务

    用于拦截和修改Emby的PlaybackInfo响应，强制DirectPlay/DirectStream
    """

    def __init__(self, emby_client: EmbyAPIClient, quark_service: QuarkService, proxy_base_url: str):
        """
        初始化PlaybackInfo Hook服务

        Args:
            emby_client: Emby API客户端
            quark_service: 夸克服务
            proxy_base_url: 代理服务基础URL
        """
        self.emby_client = emby_client
        self.quark_service = quark_service
        self.proxy_base_url = proxy_base_url.rstrip("/")
        self.playback_decision_service = PlaybackDecisionService()
        logger.info("PlaybackInfoHook initialized")

    async def hook_playback_info(
        self,
        item_id: str,
        user_id: str,
        media_source_id: str | None = None,
        is_web_client: bool = False,
        client_name: str | None = None,
        device_name: str | None = None,
        playback_request: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
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
            # 1. 获取原始PlaybackInfo，失败时对远程 STRM 条目退化为 Items 查询结果
            try:
                if playback_request is not None:
                    request_payload = dict(playback_request)
                    if not request_payload.get("DeviceProfile"):
                        request_payload.update(self.emby_client._get_default_device_profile())
                    if media_source_id and not request_payload.get("MediaSourceId") and not request_payload.get(
                        "media_source_id"
                    ):
                        request_payload["MediaSourceId"] = media_source_id
                    playback_info = await self.emby_client.post_playback_info(
                        item_id=item_id,
                        user_id=user_id,
                        device_profile=request_payload,
                    )
                else:
                    playback_info = await self.emby_client.get_playback_info(
                        item_id=item_id,
                        user_id=user_id,
                        media_source_id=media_source_id,
                    )
            except Exception as original_error:
                logger.warning(f"PlaybackInfo request failed for {item_id}, try item fallback: {original_error!s}")
                playback_info = await self._build_fallback_playback_info(
                    item_id=item_id,
                    user_id=user_id,
                    media_source_id=media_source_id,
                )
                if playback_info is None:
                    raise

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
                    user_id,
                    is_web_client=is_web_client,
                    client_name=client_name,
                    device_name=device_name,
                )
                if modified_source:
                    modified_sources.append(modified_source)

            # 4. 更新PlaybackInfo
            playback_info["MediaSources"] = modified_sources

            logger.debug(f"Hooked PlaybackInfo for item {item_id}")
            return playback_info

        except Exception as e:
            logger.error(f"Failed to hook playback info for {item_id}: {e!s}")
            raise

    async def _build_fallback_playback_info(
        self,
        item_id: str,
        user_id: str,
        media_source_id: str | None = None,
    ) -> dict[str, Any] | None:
        item_info = await self.emby_client.get_items(item_id=item_id, user_id=user_id)
        media_sources = item_info.get("MediaSources", [])
        if not media_sources:
            return None

        if media_source_id:
            media_sources = [source for source in media_sources if source.get("Id") == media_source_id]
            if not media_sources:
                return None

        fallback_sources = [source for source in media_sources if self._can_use_item_fallback(source)]
        if not fallback_sources:
            return None

        playback_info = {"MediaSources": fallback_sources}
        for key in ("Id", "MediaType", "RunTimeTicks"):
            if key in item_info:
                playback_info[key] = item_info[key]
        return playback_info

    def _can_use_item_fallback(self, source: dict[str, Any]) -> bool:
        path = source.get("Path", "")
        return source.get("IsRemote", False) or not self._is_local_media(path)

    async def _process_media_source(
        self,
        source: dict[str, Any],
        item_id: str,
        user_id: str,
        *,
        is_web_client: bool = False,
        client_name: str | None = None,
        device_name: str | None = None,
    ) -> dict[str, Any] | None:
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

            media_source_id = source.get("Id", "")
            transcoding_url = str(source.get("TranscodingUrl") or "").strip()
            if media_source_id and transcoding_url:
                source["TranscodingUrl"] = self._rewrite_transcoding_url(
                    item_id=item_id,
                    media_source_id=media_source_id,
                    original_url=transcoding_url,
                )

            stable_url = None
            file_id = None
            if path:
                if is_stable_media_url(path):
                    stable_url = path.strip()
                file_id = extract_file_id_from_proxy_url(path)
                if path.lower().endswith(".strm") and os.path.exists(path):
                    content = await read_strm_file_content(path)
                    if is_stable_media_url(content):
                        stable_url = content.strip()
                    file_id = file_id or extract_file_id_from_strm_content(content)

            decision = self.playback_decision_service.decide_hook_mode(
                is_web_client=is_web_client,
                client_name=client_name,
                device_name=device_name,
                user_agent=None,
                has_stable_url=bool(stable_url),
            )

            if decision.mode == "emby_stream":
                source["DirectStreamUrl"] = self._build_emby_stream_url(
                    item_id=item_id,
                    media_source_id=media_source_id,
                    source=source,
                )
                logger.debug(
                    "Proxy-managed media source %s rewrote to Emby-style stream URL (reason=%s, client=%s, device=%s)",
                    media_source_id,
                    decision.reason,
                    client_name,
                    device_name,
                )
                return source

            if decision.mode == "stable" and stable_url:
                separator = "&" if "?" in stable_url else "?"
                source["DirectStreamUrl"] = f"{stable_url}{separator}Static=true"
                logger.debug(
                    "Remote media source %s kept stable media entry (reason=%s, client=%s, device=%s)",
                    media_source_id,
                    decision.reason,
                    client_name,
                    device_name,
                )
                return source

            target_id = file_id or media_source_id
            new_url = f"{build_proxy_url(self.proxy_base_url, target_id, mode='redirect')}?Static=true"
            source["DirectStreamUrl"] = new_url

            logger.debug(
                "Proxy-managed media source %s rewritten to proxy redirect (reason=%s, client=%s, device=%s)",
                media_source_id,
                decision.reason,
                client_name,
                device_name,
            )
            return source

        except Exception as e:
            logger.error(f"Failed to process media source: {e!s}")
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
        if path.lower().endswith(".strm"):
            return False

        # 检查是否是http/https协议
        if path.startswith("http://") or path.startswith("https://"):
            return False

        # 其他情况认为是本地媒体
        return True

    def _build_emby_stream_url(self, *, item_id: str, media_source_id: str, source: dict[str, Any]) -> str:
        query_params: dict[str, str] = {
            "MediaSourceId": media_source_id,
            "Static": "true",
            LOCAL_PLAYBACK_PROXY_QUERY_KEY: LOCAL_PLAYBACK_PROXY_QUERY_VALUE,
        }
        container = source.get("Container")
        if container:
            query_params["container"] = str(container)
        return f"{self.proxy_base_url}/Videos/{item_id}/stream?{urlencode(query_params)}"

    def _rewrite_transcoding_url(self, *, item_id: str, media_source_id: str, original_url: str) -> str:
        query_pairs = [
            (key, value)
            for key, value in parse_qsl(urlsplit(original_url).query, keep_blank_values=True)
            if key not in {LOCAL_PLAYBACK_PROXY_QUERY_KEY, "MediaSourceId", "media_source_id"}
        ]
        query_pairs.extend(
            [
                ("MediaSourceId", media_source_id),
                (LOCAL_PLAYBACK_PROXY_QUERY_KEY, LOCAL_PLAYBACK_PROXY_QUERY_VALUE),
            ]
        )
        return f"/Videos/{item_id}/master.m3u8?{urlencode(query_pairs)}"

    async def close(self):
        """关闭服务"""
        logger.debug("PlaybackInfoHook closed")
