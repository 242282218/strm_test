"""
夸克服务模块

参考: OpenList driver.go
"""

from app.models.quark import FileModel
from app.models.strm import LinkModel
from app.services.quark_api_client_v2 import QuarkAPIClient
from app.core.logging import get_logger
from html import unescape
from typing import List

logger = get_logger(__name__)


class QuarkService:
    """夸克服务"""

    def __init__(self, cookie: str, referer: str = "https://pan.quark.cn/"):
        """
        初始化夸克服务

        Args:
            cookie: 夸克Cookie
            referer: Referer地址
        """
        self.client = QuarkAPIClient(cookie, referer)
        self.cookie = cookie
        self.referer = referer
        logger.info("QuarkService initialized")

    async def get_files(
        self,
        parent: str,
        page_size: int = 100,
        only_video: bool = False
    ) -> List[FileModel]:
        """
        获取文件列表

        参考: OpenList quark_uc/util.go:69-111

        Args:
            parent: 父目录ID
            page_size: 每页大小
            only_video: 是否只获取视频文件

        Returns:
            文件列表
        """
        files = []
        page = 1

        while True:
            params = {
                "pdir_fid": parent,
                "_size": str(page_size),
                "_fetch_total": "1",
                "fetch_all_file": "1",
                "fetch_risk_file_name": "1",
                "_page": str(page)
            }

            try:
                result = await self.client.request("/file/sort", params=params)
                data = result.get("data", {})
                file_list = data.get("list", [])
                metadata = data.get("metadata", {})

                for file_data in file_list:
                    # HTML转义处理
                    file_data["file_name"] = unescape(file_data["file_name"])

                    file_model = FileModel(**file_data)

                    # 过滤视频文件
                    if only_video:
                        if not file_model.is_dir and file_model.category == 1:
                            files.append(file_model)
                    else:
                        files.append(file_model)

                # 检查是否还有更多页
                total = metadata.get("total", 0)
                if page * page_size >= total:
                    break

                page += 1

            except Exception as e:
                logger.error(f"Failed to get files from {parent}: {str(e)}")
                break

        logger.debug(f"Got {len(files)} files from {parent}")
        return files

    async def get_download_link(self, file_id: str) -> LinkModel:
        """
        获取下载直链

        参考: OpenList quark_uc/util.go:113-137

        Args:
            file_id: 文件ID

        Returns:
            直链模型
        """
        result = await self.client.get_download_link(file_id)
        download_url = result.get("url", "")

        logger.debug(f"Got download link for {file_id}")

        return LinkModel(
            url=download_url,
            headers={
                "Cookie": self.cookie,
                "Referer": self.referer,
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) quark-cloud-drive/2.5.20 Chrome/100.0.4896.160 Electron/18.3.5.4-b478491100 Safari/537.36 Channel/pckk_other_ch"
            },
            concurrency=3,
            part_size=10 * 1024 * 1024  # 10MB
        )

    async def get_transcoding_link(self, file_id: str) -> LinkModel:
        """
        获取转码直链

        参考: OpenList quark_uc/util.go:139-168

        Args:
            file_id: 文件ID

        Returns:
            直链模型
        """
        result = await self.client.get_transcoding_link(file_id)
        transcoding_url = result.get("url", "")

        logger.debug(f"Got transcoding link for {file_id}")

        return LinkModel(
            url=transcoding_url,
            concurrency=3,
            part_size=10 * 1024 * 1024
        )

    async def close(self):
        """关闭客户端"""
        await self.client.close()
        logger.debug("QuarkService closed")
