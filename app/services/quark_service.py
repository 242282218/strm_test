"""
夸克服务模块

参考: OpenList driver.go
"""

from app.models.quark import FileModel
from app.models.strm import LinkModel
from app.services.quark_api_client_v2 import QuarkAPIClient
from app.core.logging import get_logger
from html import unescape
from typing import List, Dict, Any, Optional
import asyncio

logger = get_logger(__name__)

# 视频文件扩展名
VIDEO_EXTENSIONS = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.ts', '.m2ts', '.strm'}


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

    @staticmethod
    def _looks_like_fid(segment: str) -> bool:
        s = (segment or "").strip().lower()
        if len(s) != 32:
            return False
        return all(ch in "0123456789abcdef" for ch in s)

    @staticmethod
    def _file_model_from_info(info: Dict[str, Any]) -> FileModel:
        is_dir = info.get("file_type") == 0
        return FileModel(
            fid=info.get("fid", ""),
            file_name=info.get("file_name", "Unknown"),
            file=not is_dir,
            category=info.get("category", 0),
            size=info.get("size", 0),
            l_created_at=info.get("l_created_at", 0),
            l_updated_at=info.get("l_updated_at", 0),
            created_at=info.get("created_at", 0),
            updated_at=info.get("updated_at", 0),
            mime_type=info.get("mime_type"),
            etag=info.get("etag"),
        )

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
                # If the first page fails, surface the error to the API layer so callers
                # can distinguish "empty directory" from "auth/network failure".
                if page == 1:
                    raise
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
        latest_cookie = self.client.cookie or self.cookie
        self.cookie = latest_cookie

        logger.debug(f"Got download link for {file_id}")

        return LinkModel(
            url=download_url,
            headers={
                "Cookie": latest_cookie,
                "Referer": self.referer,
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) quark-cloud-drive/2.5.20 Chrome/100.0.4896.160 Electron/18.3.5.4-b478491100 Safari/537.36 Channel/pckk_other_ch"
            },
            concurrency=3,
            part_size=10 * 1024 * 1024  # 10MB
        )
    async def get_file_by_path(self, path: str) -> FileModel:
        """
        根据路径获取文件信息。

        Args:
            path: 文件路径 (e.g. "Movies/Inception/Inception.mp4")

        Returns:
            FileModel: 文件信息，如果未找到返回 None
        """
        parts = [p for p in path.split("/") if p]
        current_fid = "0"
        current_file = None
        start_index = 0

        if not parts:
            # 根目录
            return FileModel(
                fid="0",
                file_name="/",
                file=False,
                size=0,
                category=0,
                l_created_at=0,
                l_updated_at=0,
                created_at=0,
                updated_at=0,
            )

        # 兼容 legacy 路径: 以 fid 作为首段（如 fid/目录/文件）
        first = parts[0]
        if self._looks_like_fid(first):
            try:
                info = await self.client.get_file_info(first)
                if info and info.get("fid"):
                    current_file = self._file_model_from_info(info)
                    current_fid = current_file.fid
                    start_index = 1
            except Exception:
                # 首段虽然像 fid，但也可能是普通目录名，回退为标准路径解析
                current_fid = "0"
                current_file = None
                start_index = 0

        for part in parts[start_index:]:
            found = False
            files = await self.get_files(parent=current_fid)

            for file in files:
                if file.file_name == part or unescape(file.file_name) == part:
                    current_fid = file.fid
                    current_file = file
                    found = True
                    break

            if not found:
                return None

        return current_file

    async def get_file_info(self, fid: str) -> Dict[str, Any]:
        """
        获取单个文件/目录信息。
        """
        return await self.client.get_file_info(fid)

    async def get_full_path_by_fid(self, fid: str) -> str:
        """
        通过 fid 反查完整路径（以文件名路径表示，不包含根 "0"）。

        示例:
            Movies/Inception/Inception.mkv
        """
        current_fid = (fid or "").strip()
        if not current_fid:
            return ""

        parts: List[str] = []
        visited = set()

        while current_fid and current_fid != "0":
            if current_fid in visited:
                logger.warning(f"Detected fid loop while resolving path: {current_fid}")
                break
            visited.add(current_fid)

            info = await self.client.get_file_info(current_fid)
            if not info:
                break

            name = unescape((info.get("file_name") or "").strip())
            if name:
                parts.append(name)

            parent = str(info.get("pdir_fid") or "0").strip()
            if not parent or parent == current_fid:
                break
            current_fid = parent

        parts.reverse()
        return "/".join(parts)

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

    async def list_files(
        self,
        pdir_fid: str = "0",
        page: int = 1,
        size: int = 100
    ) -> Dict[str, Any]:
        """
        获取文件列表（分页）
        
        用途: 获取指定目录下的文件和文件夹列表，支持分页
        输入:
            - pdir_fid (str): 父目录ID，默认为"0"（根目录）
            - page (int): 页码，从1开始
            - size (int): 每页数量
        输出:
            - Dict[str, Any]: 包含文件列表和元数据的字典
              {
                "list": [...],  # 文件列表
                "metadata": {"_total": ...}  # 元数据
              }
        副作用: 调用夸克 API，可能更新 Cookie
        """
        try:
            params = {
                "pdir_fid": pdir_fid,
                "_size": str(size),
                "_fetch_total": "1",
                "fetch_all_file": "1",
                "fetch_risk_file_name": "1",
                "_page": str(page)
            }

            result = await self.client.request("/file/sort", params=params)
            data = result.get("data", {})
            file_list = data.get("list", [])
            metadata = data.get("metadata", {})

            # HTML转义处理
            for file_data in file_list:
                file_data["file_name"] = unescape(file_data.get("file_name", ""))

            return {
                "list": file_list,
                "metadata": metadata
            }

        except Exception as e:
            logger.error(f"List files failed for pdir_fid={pdir_fid}: {str(e)}")
            raise

    async def rename_file(
        self,
        fid: str,
        new_name: str
    ) -> Dict[str, Any]:
        """
        重命名云盘文件
        
        用途: 重命名云盘中的文件或文件夹
        输入:
            - fid (str): 文件ID
            - new_name (str): 新文件名
        输出:
            - Dict[str, Any]: 重命名结果
              {
                "fid": "...",
                "file_name": "...",
                "status": "success"
              }
        副作用: 修改云盘中的文件名
        """
        try:
            target_name = (new_name or "").strip()
            if not target_name:
                raise ValueError("new_name cannot be empty")

            old_info = await self.client.get_file_info(fid)
            old_name = (old_info.get("file_name") or "").strip()
            if old_name and old_name == target_name:
                logger.info(f"Skip rename for fid={fid}: old_name equals target_name ({target_name})")
                return {
                    "fid": fid,
                    "old_name": old_name,
                    "file_name": old_name,
                    "status": "skipped",
                    "verified": True,
                    "changed": False,
                    "data": old_info,
                }

            # 添加请求间隔避免限流
            await asyncio.sleep(0.1)
            result = await self.client.rename_file(fid, target_name)

            # 改名后回查，避免“接口返回成功但文件名未变化”的假成功。
            verified = False
            actual_name = ""
            latest_info: Dict[str, Any] = {}
            for _attempt in range(5):
                await asyncio.sleep(0.25)
                latest_info = await self.client.get_file_info(fid)
                actual_name = (latest_info.get("file_name") or "").strip()
                if actual_name == target_name:
                    verified = True
                    break

            if not verified:
                raise Exception(
                    f"rename verification failed for fid={fid}, expected='{target_name}', actual='{actual_name or 'unknown'}'"
                )

            logger.info(f"Renamed file success fid={fid}, old_name='{old_name}', new_name='{target_name}'")
            return {
                "fid": fid,
                "old_name": old_name,
                "file_name": target_name,
                "status": "success",
                "verified": True,
                "changed": True,
                "data": result or latest_info,
            }

        except Exception as e:
            logger.error(f"Rename file failed for fid={fid}: {str(e)}")
            raise

    async def move_file(
        self,
        fid: str,
        to_pdir_fid: str,
        new_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        移动文件到指定目录
        
        用途: 移动文件到指定目录，可选择同时重命名
        输入:
            - fid (str): 文件ID
            - to_pdir_fid (str): 目标目录ID
            - new_name (Optional[str]): 新文件名（可选，不提供则保持原名）
        输出:
            - Dict[str, Any]: 移动结果
              {
                "fid": "...",
                "pdir_fid": "...",
                "status": "success"
              }
        副作用: 修改云盘中文件的位置
        """
        try:
            # 添加请求间隔避免限流
            await asyncio.sleep(0.1)

            # 修正：调用 client.move_files，它使用 fids 数组，这是夸克 API 的标准格式
            await self.client.move_files([fid], to_pdir_fid)
            
            logger.info(f"Moved file {fid} to {to_pdir_fid}")
            
            return {
                "fid": fid,
                "to_pdir_fid": to_pdir_fid,
                "status": "success"
            }

        except Exception as e:
            logger.error(f"Move file failed for fid={fid}: {str(e)}")
            raise

    async def delete_file(self, fid: str):
        """删除文件/文件夹"""
        await self.client.delete_files([fid])

    async def mkdir(self, parent_fid: str, name: str) -> Dict[str, Any]:
        """创建文件夹"""
        return await self.client.create_directory(parent_fid, name)

    def is_video_file(self, file_name: str) -> bool:
        """
        检查是否为视频文件
        
        用途: 根据文件扩展名判断是否为视频文件
        输入:
            - file_name (str): 文件名
        输出:
            - bool: 是否为视频文件
        副作用: 无
        """
        ext = file_name.lower().split('.')[-1] if '.' in file_name else ''
        return f".{ext}" in VIDEO_EXTENSIONS

    async def get_all_video_files(
        self,
        pdir_fid: str = "0",
        recursive: bool = True,
        max_files: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        递归获取所有视频文件
        
        用途: 获取指定目录下的所有视频文件，支持递归子目录
        输入:
            - pdir_fid (str): 父目录ID
            - recursive (bool): 是否递归子目录
            - max_files (int): 最大返回文件数
        输出:
            - List[Dict]: 视频文件列表
        副作用: 调用夸克 API
        """
        all_video_files = []
        
        async def scan_directory(dir_fid: str, depth: int = 0):
            """递归扫描目录"""
            if len(all_video_files) >= max_files:
                return
            
            if depth > 10:  # 防止过深递归
                logger.warning(f"递归深度超过10层，停止扫描: {dir_fid}")
                return
            
            try:
                # 获取当前目录的文件
                result = await self.list_files(pdir_fid=dir_fid, page=1, size=100)
                items = result.get("list", [])
                
                for item in items:
                    if len(all_video_files) >= max_files:
                        break
                    
                    file_type = item.get("file_type")
                    file_name = item.get("file_name", "")
                    
                    # 如果是视频文件，添加到列表
                    if file_type == 1 and self.is_video_file(file_name):
                        all_video_files.append(item)
                    
                    # 如果是文件夹且需要递归，扫描子目录
                    elif file_type == 0 and recursive:
                        sub_fid = item.get("fid")
                        if sub_fid:
                            await scan_directory(sub_fid, depth + 1)
                            await asyncio.sleep(0.1)  # 限流
                
            except Exception as e:
                logger.error(f"扫描目录失败 {dir_fid}: {str(e)}")
        
        # 开始扫描
        await scan_directory(pdir_fid)
        
        logger.info(f"递归扫描完成，找到 {len(all_video_files)} 个视频文件")
        return all_video_files[:max_files]

