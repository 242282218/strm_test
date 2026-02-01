"""
STRM文件生成器

用于从夸克网盘生成STRM文件
"""

import os
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional
from app.services.quark_service import QuarkService
from app.models.quark import FileModel
from app.core.config_manager import get_config
from app.core.logging import get_logger

logger = get_logger(__name__)


class STRMGenerator:
    """STRM文件生成器"""

    def __init__(
        self,
        cookie: str,
        output_dir: str = "./strm",
        base_url: str = "http://localhost:8000",
        use_transcoding: bool = True
    ):
        """
        初始化STRM生成器

        Args:
            cookie: 夸克Cookie
            output_dir: STRM文件输出目录
            base_url: API基础URL
            use_transcoding: 是否使用转码链接
        """
        self.cookie = cookie
        self.output_dir = Path(output_dir)
        self.base_url = base_url.rstrip("/")
        self.use_transcoding = use_transcoding
        self.service = QuarkService(cookie=cookie)

        # 确保输出目录存在
        self.output_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"STRMGenerator initialized, output dir: {self.output_dir}")

    async def generate_strm_files(
        self,
        root_id: str = "0",
        remote_path: str = "",
        only_video: bool = True
    ) -> Dict[str, Any]:
        """
        生成STRM文件

        Args:
            root_id: 根目录ID
            remote_path: 远程路径前缀
            only_video: 是否只处理视频文件

        Returns:
            生成结果统计
        """
        stats = {
            "total_files": 0,
            "generated_files": 0,
            "skipped_files": 0,
            "failed_files": 0,
            "errors": []
        }

        try:
            # 递归获取所有文件
            all_files = await self._get_all_files(root_id, remote_path, only_video)
            stats["total_files"] = len(all_files)

            logger.info(f"Found {len(all_files)} files to process")

            # 生成STRM文件
            for file_info in all_files:
                try:
                    result = await self._generate_single_strm(file_info)
                    if result:
                        stats["generated_files"] += 1
                    else:
                        stats["skipped_files"] += 1
                except Exception as e:
                    stats["failed_files"] += 1
                    error_msg = f"Failed to generate STRM for {file_info.get('name', 'unknown')}: {str(e)}"
                    stats["errors"].append(error_msg)
                    logger.error(error_msg)

        except Exception as e:
            logger.error(f"Failed to generate STRM files: {str(e)}")
            stats["errors"].append(str(e))

        return stats

    async def _get_all_files(
        self,
        parent_id: str,
        remote_path: str,
        only_video: bool
    ) -> List[Dict[str, Any]]:
        """
        递归获取所有文件

        Args:
            parent_id: 父目录ID
            remote_path: 远程路径
            only_video: 是否只获取视频文件

        Returns:
            文件列表
        """
        files = []

        try:
            # 获取当前目录的文件列表
            file_models = await self.service.get_files(
                parent=parent_id,
                only_video=False  # 获取所有文件以便递归
            )

            for file_model in file_models:
                file_name = file_model.file_name
                file_id = file_model.fid
                is_dir = file_model.is_dir

                # 构建远程路径
                current_remote_path = f"{remote_path}/{file_name}" if remote_path else file_name

                if is_dir:
                    # 递归处理子目录
                    sub_files = await self._get_all_files(
                        file_id,
                        current_remote_path,
                        only_video
                    )
                    files.extend(sub_files)
                else:
                    # 检查是否为视频文件
                    if only_video and file_model.category != 1:
                        continue

                    files.append({
                        "id": file_id,
                        "name": file_name,
                        "remote_path": current_remote_path,
                        "size": file_model.size,
                        "category": file_model.category
                    })

        except Exception as e:
            logger.error(f"Failed to get files from {parent_id}: {str(e)}")

        return files

    async def _generate_single_strm(self, file_info: Dict[str, Any]) -> bool:
        """
        生成单个STRM文件

        Args:
            file_info: 文件信息

        Returns:
            是否成功生成
        """
        file_name = file_info["name"]
        file_id = file_info["id"]
        remote_path = file_info["remote_path"]

        # 构建STRM文件路径
        strm_path = self.output_dir / f"{remote_path}.strm"

        # 检查文件是否已存在
        if strm_path.exists():
            logger.debug(f"STRM file already exists: {strm_path}")
            return False

        # 确保父目录存在
        strm_path.parent.mkdir(parents=True, exist_ok=True)

        # 获取直链URL
        try:
            if self.use_transcoding:
                link = await self.service.get_transcoding_link(file_id)
            else:
                link = await self.service.get_download_link(file_id)

            video_url = link.url

            # 写入STRM文件
            with open(strm_path, 'w', encoding='utf-8') as f:
                f.write(video_url)

            logger.info(f"Generated STRM file: {strm_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to get link for {file_name}: {str(e)}")
            raise

    async def close(self):
        """关闭服务"""
        await self.service.close()
        logger.debug("STRMGenerator closed")


async def generate_strm_from_quark(
    cookie: str = None,
    output_dir: str = "./strm",
    root_id: str = None,
    only_video: bool = None
) -> Dict[str, Any]:
    """
    从夸克网盘生成STRM文件的便捷函数

    Args:
        cookie: 夸克Cookie（可选，默认从配置文件读取）
        output_dir: 输出目录
        root_id: 根目录ID（可选，默认从配置文件读取）
        only_video: 是否只处理视频文件（可选，默认从配置文件读取）

    Returns:
        生成结果
    """
    config = get_config()

    # 使用传入的参数或配置文件中的值
    cookie = cookie or config.get_quark_cookie()
    root_id = root_id or config.get_quark_root_id()
    if only_video is None:
        only_video = config.get_quark_only_video()

    if not cookie:
        raise ValueError("Cookie is required. Please provide cookie parameter or set it in config.yaml")

    generator = STRMGenerator(
        cookie=cookie,
        output_dir=output_dir
    )

    try:
        result = await generator.generate_strm_files(
            root_id=root_id,
            only_video=only_video
        )
        return result
    finally:
        await generator.close()
