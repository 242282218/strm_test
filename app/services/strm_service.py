"""
STRM服务模块

参考: AlistAutoStrm mission.go
"""

from app.services.strm_generator import STRMGenerator as StrmGenerator
from app.services.quark_service import QuarkService
from app.core.database import Database
from app.core.logging import get_logger

logger = get_logger(__name__)


class StrmService:
    """STRM服务"""

    def __init__(
        self,
        cookie: str,
        database: Database,
        base_url: str = "http://localhost:5244",
        exts: list = None,
        alt_exts: list = None,
        create_sub_directory: bool = False,
        recursive: bool = True,
        force_refresh: bool = False
    ):
        """
        初始化STRM服务

        Args:
            cookie: 夸克Cookie
            database: 数据库实例
            base_url: 基础URL
            exts: 视频扩展名列表
            alt_exts: 字幕扩展名列表
            create_sub_directory: 是否创建子目录
            recursive: 是否递归扫描
            force_refresh: 是否强制刷新
        """
        if exts is None:
            exts = [".mp4", ".mkv", ".avi", ".mov"]
        if alt_exts is None:
            alt_exts = [".srt", ".ass"]

        self.quark_service = QuarkService(cookie)
        self.database = database
        self.base_url = base_url
        self.exts = exts
        self.alt_exts = alt_exts
        self.create_sub_directory = create_sub_directory
        self.recursive = recursive
        self.force_refresh = force_refresh
        logger.info("StrmService initialized")

    async def scan_directory(
        self,
        remote_path: str,
        local_path: str,
        concurrent_limit: int = 5
    ):
        """
        扫描目录并生成STRM

        参考: AlistAutoStrm mission.go:31-158

        Args:
            remote_path: 远程目录路径
            local_path: 本地目录路径
            concurrent_limit: 并发限制

        Returns:
            STRM模型列表
        """
        generator = StrmGenerator(
            quark_service=self.quark_service,
            database=self.database,
            base_url=self.base_url,
            exts=self.exts,
            alt_exts=self.alt_exts,
            create_sub_directory=self.create_sub_directory,
            recursive=self.recursive,
            force_refresh=self.force_refresh
        )

        strms = await generator.scan_directory(remote_path, local_path, concurrent_limit)

        # 保存扫描记录
        self.database.save_record(remote_path)

        return strms

    async def close(self):
        """关闭服务"""
        await self.quark_service.close()
        logger.debug("StrmService closed")
