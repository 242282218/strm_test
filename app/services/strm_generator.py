"""
STRM文件生成器

用于从夸克网盘生成STRM文件

支持三种URL模式：
- redirect: 使用302重定向代理URL（推荐，解决直链过期问题）
- stream: 使用流代理URL（服务器中转，占用带宽）
- direct: 使用夸克直链URL（不推荐，会过期）
"""

import os
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional, Literal
from app.services.quark_service import QuarkService
from app.models.quark import FileModel
from app.core.config_manager import get_config
from app.core.logging import get_logger

logger = get_logger(__name__)

# STRM URL模式类型
StrmUrlMode = Literal["redirect", "stream", "direct"]


class STRMGenerator:
    """STRM文件生成器"""

    def __init__(
        self,
        cookie: str,
        output_dir: str = "./strm",
        base_url: str = "http://localhost:8000",
        use_transcoding: bool = True,
        strm_url_mode: StrmUrlMode = "redirect"
    ):
        """
        初始化STRM生成器

        用途: 创建STRM生成器实例，配置输出目录和URL模式
        输入:
            - cookie (str): 夸克Cookie，用于API认证
            - output_dir (str): STRM文件输出目录，默认./strm
            - base_url (str): API基础URL，用于生成代理URL
            - use_transcoding (bool): 是否使用转码链接，默认True
            - strm_url_mode (StrmUrlMode): STRM URL模式
                - "redirect": 使用302重定向代理（推荐）
                - "stream": 使用流代理（服务器中转）
                - "direct": 使用直链（不推荐，会过期）
        输出: 无
        副作用: 
            - 创建输出目录（如不存在）
            - 初始化QuarkService
        """
        self.cookie = cookie
        self.output_dir = Path(output_dir)
        self.base_url = base_url.rstrip("/")
        self.use_transcoding = use_transcoding
        self.strm_url_mode = strm_url_mode
        self.service = QuarkService(cookie=cookie)

        # 确保输出目录存在
        self.output_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"STRMGenerator initialized, output dir: {self.output_dir}, url_mode: {strm_url_mode}")

    async def generate_strm_files(
        self,
        root_id: str = "0",
        remote_path: str = "",
        only_video: bool = True,
        max_files: int = 50
    ) -> Dict[str, Any]:
        """
        生成STRM文件

        Args:
            root_id: 根目录ID
            remote_path: 远程路径前缀
            only_video: 是否只处理视频文件
            max_files: 最大处理文件数量

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

            # 限制处理文件数量
            if max_files > 0 and len(all_files) > max_files:
                logger.info(f"Limiting processing to {max_files} files out of {len(all_files)} total")
                all_files = all_files[:max_files]

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

        用途: 为单个视频文件创建对应的STRM文件
        输入:
            - file_info (Dict): 文件信息，包含id, name, remote_path等
        输出:
            - bool: 是否成功生成（文件已存在返回False）
        副作用:
            - 在output_dir下创建.strm文件
            - 若strm_url_mode为direct，会调用夸克API获取直链
        """
        file_name = file_info["name"]
        file_id = file_info["id"]
        remote_path = file_info["remote_path"]

        # 构建STRM文件路径（保持夸克目录结构）
        strm_path = self.output_dir / f"{remote_path}.strm"

        # 检查文件是否已存在
        if strm_path.exists():
            logger.debug(f"STRM file already exists: {strm_path}")
            return False

        # 确保父目录存在
        strm_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            # 根据URL模式生成视频URL
            video_url = await self._generate_video_url(file_id, remote_path)

            # 写入STRM文件
            with open(strm_path, 'w', encoding='utf-8') as f:
                f.write(video_url)

            logger.info(f"Generated STRM file: {strm_path} -> {video_url[:80]}...")
            return True

        except Exception as e:
            logger.error(f"Failed to generate STRM for {file_name}: {str(e)}")
            raise

    async def _generate_video_url(self, file_id: str, remote_path: str = None) -> str:
        """
        根据URL模式生成视频URL

        用途: 根据strm_url_mode配置生成不同类型的视频URL
        输入:
            - file_id (str): 夸克文件ID
            - remote_path (str): 文件远程路径（可选，用于拼接兜底参数）
        输出:
            - str: 视频URL
                - redirect模式: http://base_url/api/proxy/redirect/{file_id}
                - stream模式: http://base_url/api/proxy/stream/{file_id}
                - direct模式: 夸克直链URL（会过期）
        副作用:
            - direct模式会调用夸克API
        """
        if self.strm_url_mode == "redirect":
            # 302重定向模式（推荐）
            # Emby请求此URL时，后端会302重定向到实时获取的夸克直链
            url = f"{self.base_url}/api/proxy/redirect/{file_id}"
            if remote_path:
                from urllib.parse import quote
                # 附加 path 参数，用于 WebDAV 兜底
                encoded_path = quote(remote_path)
                url += f"?path={encoded_path}"
            return url
        
        elif self.strm_url_mode == "stream":
            # 流代理模式
            # Emby请求此URL时，后端会代理视频流数据（占用服务器带宽）
            return f"{self.base_url}/api/proxy/stream/{file_id}"
        
        elif self.strm_url_mode == "direct":
            # 直链模式（不推荐，链接会过期）
            if self.use_transcoding:
                link = await self.service.get_transcoding_link(file_id)
            else:
                link = await self.service.get_download_link(file_id)
            logger.warning(f"Using direct link mode for {file_id}, link may expire!")
            return link.url
        
        else:
            raise ValueError(f"Unknown strm_url_mode: {self.strm_url_mode}")

    async def close(self):
        """关闭服务"""
        await self.service.close()
        logger.debug("STRMGenerator closed")


async def generate_strm_from_quark(
    cookie: str = None,
    output_dir: str = "./strm",
    root_id: str = None,
    only_video: bool = None,
    max_files: int = 50,
    base_url: str = "http://localhost:8000",
    strm_url_mode: StrmUrlMode = "redirect"
) -> Dict[str, Any]:
    """
    从夸克网盘生成STRM文件的便捷函数

    用途: 便捷地扫描夸克网盘并生成STRM文件
    输入:
        - cookie (str): 夸克Cookie（可选，默认从配置文件读取）
        - output_dir (str): STRM输出目录
        - root_id (str): 夸克根目录ID（可选，默认从配置文件读取）
        - only_video (bool): 是否只处理视频文件（可选，默认从配置文件读取）
        - max_files (int): 最大处理文件数量（可选，默认50）
        - base_url (str): API基础URL，用于生成代理URL
        - strm_url_mode (StrmUrlMode): URL模式，默认redirect
    输出:
        - Dict: 生成结果统计
    副作用:
        - 在output_dir下创建STRM文件
        - 调用夸克API获取文件列表
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
        output_dir=output_dir,
        base_url=base_url,
        strm_url_mode=strm_url_mode
    )

    try:
        result = await generator.generate_strm_files(
            root_id=root_id,
            only_video=only_video,
            max_files=max_files
        )
        return result
    finally:
        await generator.close()
