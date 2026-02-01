"""
基于quark_sdk的夸克服务实现

提供与现有QuarkService兼容的接口，同时支持SDK新功能
"""

from typing import List, Dict, Any, Optional
from app.core.sdk_config import sdk_config
from app.core.logging import get_logger

logger = get_logger(__name__)


class QuarkSDKService:
    """基于SDK的夸克服务"""

    def __init__(self, cookie: Optional[str] = None):
        self.cookie = cookie
        self._client = None
        self._async_client = None

    def _check_sdk(self) -> bool:
        """检查SDK是否可用"""
        if not sdk_config.is_available():
            logger.error("quark_sdk不可用，请检查SDK路径配置")
            return False
        return True

    def _get_client(self):
        """获取同步客户端"""
        if self._client is None:
            self._client = sdk_config.create_quark_client(self.cookie)
        return self._client

    async def _get_async_client(self):
        """获取异步客户端"""
        if self._async_client is None:
            self._async_client = sdk_config.create_async_quark_client(self.cookie)
        return self._async_client

    async def get_files(
        self,
        parent: str = "0",
        page_size: int = 100,
        only_video: bool = False
    ) -> List[Dict[str, Any]]:
        """
        获取文件列表

        Args:
            parent: 父目录ID
            page_size: 每页大小
            only_video: 是否只获取视频文件

        Returns:
            文件列表
        """
        if not self._check_sdk():
            return []

        try:
            from packages.quark_sdk.models.file import FileListParams

            client = await self._get_async_client()
            if client is None:
                return []

            params = FileListParams(
                pdir_fid=parent,
                page_size=page_size
            )

            response = await client.file.list(params)

            files = []
            for file in response.files:
                # 获取文件属性
                is_dir = getattr(file, 'is_dir', False) or getattr(file, 'dir', False)
                category = getattr(file, 'category', 0)

                file_dict = {
                    "fid": getattr(file, 'fid', getattr(file, 'file_id', '')),
                    "file_name": getattr(file, 'file_name', getattr(file, 'name', '')),
                    "category": category.value if hasattr(category, 'value') else category,
                    "file": not is_dir,
                    "dir": is_dir,
                    "size": getattr(file, 'size', 0),
                    "created_at": getattr(file, 'created_at', None),
                    "updated_at": getattr(file, 'updated_at', None),
                    "mime_type": getattr(file, 'mime_type', ''),
                }

                # 视频文件过滤
                if only_video:
                    if is_dir:
                        files.append(file_dict)
                    elif file_dict.get("category") == 1:  # 1表示视频
                        files.append(file_dict)
                else:
                    files.append(file_dict)

            logger.debug(f"从SDK获取到 {len(files)} 个文件")
            return files

        except Exception as e:
            logger.error(f"SDK获取文件列表失败: {e}")
            return []

    async def get_download_link(self, file_id: str) -> Optional[Dict[str, Any]]:
        """
        获取下载直链

        Args:
            file_id: 文件ID

        Returns:
            下载链接信息
        """
        if not self._check_sdk():
            return None

        try:
            client = await self._get_async_client()
            if client is None:
                return None

            result = await client.file.get_download_link(file_id)

            return {
                "url": getattr(result, 'url', ''),
                "headers": getattr(result, 'headers', {}),
                "concurrency": 3,
                "part_size": 10 * 1024 * 1024  # 10MB
            }

        except Exception as e:
            logger.error(f"SDK获取下载链接失败: {e}")
            return None

    async def get_transcoding_link(self, file_id: str) -> Optional[Dict[str, Any]]:
        """
        获取转码直链

        Args:
            file_id: 文件ID

        Returns:
            转码链接信息
        """
        if not self._check_sdk():
            return None

        try:
            client = await self._get_async_client()
            if client is None:
                return None

            result = await client.file.get_transcoding_link(file_id)

            return {
                "url": getattr(result, 'url', ''),
                "content_length": getattr(result, 'content_length', 0),
                "headers": getattr(result, 'headers', {}),
                "concurrency": 3,
                "part_size": 10 * 1024 * 1024  # 10MB
            }

        except Exception as e:
            logger.error(f"SDK获取转码链接失败: {e}")
            return None

    async def create_share(
        self,
        file_ids: List[str],
        title: Optional[str] = None,
        password: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        创建分享（新功能）

        Args:
            file_ids: 文件ID列表
            title: 分享标题
            password: 分享密码

        Returns:
            分享信息
        """
        if not self._check_sdk():
            return None

        try:
            from packages.quark_sdk.models.share import ShareCreateParams

            client = await self._get_async_client()
            if client is None:
                return None

            params = ShareCreateParams(
                fid_list=file_ids,
                title=title,
                password=password
            )

            result = await client.share.create(params)

            return {
                "share_id": getattr(result, 'share_id', ''),
                "share_key": getattr(result, 'share_key', ''),
                "url": getattr(result, 'url', ''),
                "password": getattr(result, 'password', ''),
                "title": getattr(result, 'title', ''),
                "expires_at": getattr(result, 'expires_at', None)
            }

        except Exception as e:
            logger.error(f"SDK创建分享失败: {e}")
            return None

    async def save_share(
        self,
        share_key: str,
        file_ids: List[str],
        target_folder: str = "0",
        password: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        转存分享文件（新功能）

        Args:
            share_key: 分享key
            file_ids: 要转存的文件ID列表
            target_folder: 目标文件夹ID
            password: 分享密码

        Returns:
            转存结果
        """
        if not self._check_sdk():
            return None

        try:
            from packages.quark_sdk.models.transfer import TransferSaveParams

            client = await self._get_async_client()
            if client is None:
                return None

            params = TransferSaveParams(
                share_key=share_key,
                fid_list=file_ids,
                target_pdir_fid=target_folder,
                password=password
            )

            result = await client.transfer.save(params)

            return {
                "task_id": getattr(result, 'task_id', ''),
                "status": getattr(result, 'status', ''),
                "message": getattr(result, 'message', '')
            }

        except Exception as e:
            logger.error(f"SDK转存分享失败: {e}")
            return None

    async def search_files(
        self,
        keyword: str,
        parent: str = "0",
        page_size: int = 50
    ) -> List[Dict[str, Any]]:
        """
        搜索文件（新功能）

        Args:
            keyword: 搜索关键词
            parent: 父目录ID
            page_size: 每页大小

        Returns:
            文件列表
        """
        if not self._check_sdk():
            return []

        try:
            from packages.quark_sdk.models.file import FileSearchParams

            client = await self._get_async_client()
            if client is None:
                return []

            params = FileSearchParams(
                keyword=keyword,
                pdir_fid=parent,
                page_size=page_size
            )

            response = await client.file.search(params)

            files = []
            for file in response.files:
                files.append({
                    "fid": getattr(file, 'fid', getattr(file, 'file_id', '')),
                    "file_name": getattr(file, 'file_name', getattr(file, 'name', '')),
                    "category": getattr(file, 'category', 0),
                    "file": not getattr(file, 'is_dir', False),
                    "size": getattr(file, 'size', 0),
                    "path": getattr(file, 'path', ''),
                })

            return files

        except Exception as e:
            logger.error(f"SDK搜索文件失败: {e}")
            return []

    async def close(self):
        """关闭客户端"""
        if self._async_client:
            try:
                await self._async_client.close()
            except Exception as e:
                logger.warning(f"关闭异步客户端失败: {e}")
            self._async_client = None

        if self._client:
            try:
                self._client.close()
            except Exception as e:
                logger.warning(f"关闭同步客户端失败: {e}")
            self._client = None
