"""
Emby反代服务模块

参考: go-emby2openlist internal/service/emby/redirect.go
支持302重定向和PlaybackInfo Hook
"""

import os
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

import aiohttp

from app.core.logging import get_logger
from app.services.emby_api_client import EmbyAPIClient
from app.services.media_mapping_service import MediaMappingService
from app.services.playbackinfo_hook import PlaybackInfoHook
from app.services.quark_service import QuarkService
from app.utils.strm_url import (
    extract_file_id_from_proxy_url,
    extract_file_id_from_strm_content,
    extract_media_id_from_strm_content,
    extract_media_id_from_url,
    extract_path_from_media_reference,
    read_strm_file_content,
)


logger = get_logger(__name__)


class EmbyProxyService:
    """
    Emby反代服务

    功能:
    1. 拦截Emby请求
    2. 修改PlaybackInfo响应，强制DirectPlay
    3. 302重定向视频流到夸克直链
    """

    def __init__(self, emby_base_url: str, api_key: str, cookie: str, proxy_base_url: str = "http://localhost:8000"):
        """
        初始化Emby反代服务

        Args:
            emby_base_url: Emby服务器地址
            api_key: Emby API密钥
            cookie: 夸克Cookie
            proxy_base_url: 代理服务基础URL
        """
        self.emby_base_url = emby_base_url.rstrip("/")
        self.api_key = api_key
        self.cookie = cookie
        self.proxy_base_url = proxy_base_url.rstrip("/")
        self.media_mapping_service = MediaMappingService()

        # 创建客户端
        self.emby_client: EmbyAPIClient | None = None
        self.quark_service: QuarkService | None = None
        self.playback_hook: PlaybackInfoHook | None = None
        self._url_check_session: aiohttp.ClientSession | None = None

        logger.info(f"EmbyProxyService initialized: {self.emby_base_url}")

    async def __aenter__(self):
        """异步上下文管理器进入方法"""
        self.emby_client = EmbyAPIClient(base_url=self.emby_base_url, api_key=self.api_key)
        await self.emby_client.__aenter__()

        self.quark_service = QuarkService(cookie=self.cookie)

        self.playback_hook = PlaybackInfoHook(
            emby_client=self.emby_client, quark_service=self.quark_service, proxy_base_url=self.proxy_base_url
        )

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器退出方法"""
        await self.close()

    async def proxy_playback_info(
        self,
        item_id: str,
        user_id: str,
        media_source_id: str | None = None,
        is_web_client: bool = False,
        client_name: str | None = None,
        device_name: str | None = None,
    ) -> dict[str, Any]:
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
                media_source_id=media_source_id,
                is_web_client=is_web_client,
                client_name=client_name,
                device_name=device_name,
            )

            logger.info(f"PlaybackInfo hooked for item {item_id}")
            return playback_info

        except Exception as e:
            logger.error(f"Failed to proxy playback info: {e!s}")
            raise

    async def proxy_stream_request(self, media_source_id: str, file_path: str | None = None) -> str:
        """
        代理视频流请求

        参考: go-emby2openlist internal/service/emby/redirect.go Redirect2OpenlistLink

        1. 检查是否是STRM文件
        2. 如果是STRM，解析文件ID
        3. 获取夸克直链
        4. 验证直链有效性
        5. 返回302重定向URL或降级到本地代理

        Args:
            media_source_id: 媒体源ID
            file_path: 文件路径（可选）

        Returns:
            直链URL（用于302重定向）
        """
        try:
            # 如果提供了文件路径，直接使用
            if file_path and file_path.lower().endswith(".strm"):
                # 从STRM文件解析文件ID
                file_id = await self._extract_file_id_from_strm(file_path)
                if file_id:
                    return await self._get_stream_url_with_fallback(file_id)

            # 如果没有文件路径或无法解析，尝试通过Emby API获取
            if self.emby_client:
                # 获取媒体源信息
                # 这里可以实现更复杂的逻辑
                pass

            raise Exception("Unable to get stream URL")

        except Exception as e:
            logger.error(f"Failed to proxy stream request: {e!s}")
            raise

    def _build_proxy_stream_url(self, file_id: str) -> str:
        return f"{self.proxy_base_url}/api/proxy/stream/{file_id}"

    async def _get_stream_url_with_fallback(self, file_id: str) -> str:
        """
        获取流URL，带Failover机制

        1. 尝试获取直链
        2. 验证直链有效性
        3. 如果直链无效，降级到本地代理

        Args:
            file_id: 文件ID

        Returns:
            流URL
        """
        fallback_url = self._build_proxy_stream_url(file_id)
        try:
            # 1. 尝试获取直链
            link = await self.quark_service.get_download_link(file_id)
            direct_url = link.url

            # 2. 验证直链有效性 (HEAD请求)
            if await self._check_url_alive(direct_url):
                logger.info(f"Direct link is valid: {direct_url[:100]}...")
                return direct_url
            logger.warning("Direct link is invalid, falling back to local proxy")
            return fallback_url

        except Exception as e:
            logger.warning(f"Failed to get direct link, falling back to local proxy: {e}")
            return fallback_url

    async def _check_url_alive(self, url: str, timeout: int = 5) -> bool:
        """
        检查URL是否有效

        Args:
            url: 要检查的URL
            timeout: 超时时间（秒）

        Returns:
            bool: URL是否有效
        """
        try:
            session = self._url_check_session
            if session is None or session.closed:
                session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout))
                self._url_check_session = session
            async with session.head(url, allow_redirects=True) as resp:
                # 检查状态码是否为2xx或3xx
                return 200 <= resp.status < 400
        except Exception as e:
            logger.debug(f"URL check failed for {url[:50]}...: {e}")
            return False

    async def _extract_file_id_from_strm(self, file_path: str) -> str | None:
        """
        从STRM文件路径提取文件ID

        Args:
            file_path: STRM文件路径

        Returns:
            文件ID或None
        """
        try:
            content = await read_strm_file_content(file_path)
            file_id = extract_file_id_from_strm_content(content)
            if file_id:
                return file_id
            file_id = extract_file_id_from_proxy_url(content)
            if file_id:
                return file_id
            filename = os.path.basename(file_path)
            name_without_ext = os.path.splitext(filename)[0]
            parts = name_without_ext.rsplit("_", 1)
            if len(parts) == 2:
                return parts[1]
            return None
        except Exception as e:
            logger.error(f"Failed to extract file ID from STRM: {e!s}")
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
            content = await read_strm_file_content(file_path)

            # 如果内容是夸克文件ID，获取直链
            file_id = extract_file_id_from_strm_content(content)
            if file_id:
                link = await self.quark_service.get_download_link(file_id)
                return link.url

            # 否则直接返回内容（假设已经是URL）
            return content

        except Exception as e:
            logger.error(f"Failed to read STRM file: {e!s}")
            raise

    async def proxy_items_request(self, item_id: str, user_id: str | None = None) -> dict[str, Any]:
        """
        代理Items请求

        Args:
            item_id: 项目ID
            user_id: 用户ID

        Returns:
            项目信息
        """
        try:
            item_info = await self.emby_client.get_items(item_id=item_id, user_id=user_id)
            return item_info
        except Exception as e:
            logger.error(f"Failed to proxy items request: {e!s}")
            raise

    def _extract_query_path(self, path: str) -> str | None:
        parsed = urlparse(path)
        query_path = parse_qs(parsed.query).get("path", [])
        if not query_path:
            return None
        return unquote(query_path[0]).strip() or None

    def _extract_local_strm_path(self, path: str) -> str | None:
        candidate = self._extract_query_path(path)
        if candidate and candidate.lower().endswith(".strm") and os.path.exists(candidate):
            return candidate

        normalized_path = path.strip()
        if normalized_path.lower().endswith(".strm") and os.path.exists(normalized_path):
            return normalized_path
        return None

    async def _resolve_file_id_from_reference(self, reference: str) -> str | None:
        text = (reference or "").strip()
        if not text:
            return None

        media_id = extract_media_id_from_url(text) or extract_media_id_from_strm_content(text)
        if media_id:
            mapping = self.media_mapping_service.get_by_media_id(media_id)
            if mapping:
                if mapping.provider_file_id:
                    return mapping.provider_file_id
                if mapping.source_path and self.quark_service:
                    try:
                        file_info = await self.quark_service.get_file_by_path(mapping.source_path)
                        if file_info and getattr(file_info, "fid", ""):
                            self.media_mapping_service.update_provider_file_id(media_id, file_info.fid)
                            return file_info.fid
                    except Exception as exc:
                        logger.warning(
                            "Failed to resolve provider file by mapped path %s: %s", mapping.source_path, exc
                        )

        if text.startswith("quark://"):
            return extract_file_id_from_strm_content(text)

        remote_path = self._extract_query_path(text) or extract_path_from_media_reference(text)
        if remote_path and self.quark_service:
            try:
                file_info = await self.quark_service.get_file_by_path(remote_path)
                if file_info and getattr(file_info, "fid", ""):
                    return file_info.fid
            except Exception as exc:
                logger.warning("Failed to resolve quark file by remote path %s: %s", remote_path, exc)

        return extract_file_id_from_strm_content(text) or extract_file_id_from_proxy_url(text)

    async def resolve_media_source_file_id(self, item_id: str, media_source_id: str) -> str:
        """根据 item_id + media_source_id 解析真实 Quark file_id。"""
        if not self.emby_client:
            raise ValueError("Emby client is not initialized")

        item_info = await self.emby_client.get_items(item_id=item_id)
        media_sources = item_info.get("MediaSources", [])
        target_source = next((source for source in media_sources if source.get("Id") == media_source_id), None)
        if not target_source:
            raise ValueError(f"MediaSource not found: {media_source_id}")

        path = target_source.get("Path", "")
        strm_candidates: list[str] = []
        item_path = (item_info.get("Path") or "").strip()
        if item_path.lower().endswith(".strm") and os.path.exists(item_path):
            strm_candidates.append(item_path)

        strm_path = self._extract_local_strm_path(path)
        if strm_path and strm_path not in strm_candidates:
            strm_candidates.append(strm_path)

        for candidate in strm_candidates:
            content = await read_strm_file_content(candidate)
            file_id = await self._resolve_file_id_from_reference(content)
            if file_id:
                return file_id

        file_id = await self._resolve_file_id_from_reference(path)
        if file_id:
            return file_id

        raise ValueError(f"Unable to resolve file_id for media source: {media_source_id}")

    async def close(self):
        """关闭服务"""
        if self.emby_client:
            await self.emby_client.__aexit__(None, None, None)
            self.emby_client = None
        if self.quark_service:
            await self.quark_service.close()
            self.quark_service = None
        if self._url_check_session and not self._url_check_session.closed:
            await self._url_check_session.close()
        self._url_check_session = None
        logger.debug("EmbyProxyService closed")
