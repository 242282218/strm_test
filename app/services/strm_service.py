"""
STRM 服务模块

核心职责：
1) 根据远端路径扫描夸克网盘文件
2) 生成可播放的 .strm 文件（302 / WebDAV 等模式）
"""

from __future__ import annotations

from typing import List

from app.core.database import Database
from app.core.logging import get_logger
from app.services.strm_generator import STRMGenerator

logger = get_logger(__name__)


class StrmService:
    """STRM 服务"""

    def __init__(
        self,
        cookie: str,
        database: Database,
        recursive: bool = True,
        base_url: str = "http://localhost:8000",
        strm_url_mode: str = "redirect",
        max_files: int = 0,
        only_video: bool = True,
    ):
        self.cookie = cookie
        self.database = database
        self.recursive = recursive
        self.base_url = base_url
        self.strm_url_mode = strm_url_mode
        self.max_files = max_files
        self.only_video = only_video
        self._generator: STRMGenerator | None = None
        logger.info(f"StrmService initialized, mode={strm_url_mode}, recursive={recursive}")

    @staticmethod
    def _normalize_remote_path(path: str) -> str:
        p = (path or "").strip()
        if not p:
            return "/"
        if not p.startswith("/"):
            p = "/" + p
        if p != "/":
            p = p.rstrip("/")
        return p

    async def scan_directory(self, remote_path: str, local_path: str, concurrent_limit: int = 5) -> List[str]:
        remote_path = self._normalize_remote_path(remote_path)
        remote_prefix = remote_path.strip("/")  # used for WebDAV path & proxy fallback

        self._generator = STRMGenerator(
            cookie=self.cookie,
            output_dir=local_path,
            base_url=self.base_url,
            strm_url_mode=self.strm_url_mode,
        )

        try:
            if remote_path == "/":
                stats = await self._generator.generate_strm_files(
                    root_id="0",
                    remote_path=remote_prefix,
                    only_video=self.only_video,
                    max_files=self.max_files,
                    recursive=self.recursive,
                    concurrent_limit=concurrent_limit,
                )
                generated = stats.get("files", [])
            else:
                node = await self._generator.service.get_file_by_path(remote_path)
                if not node:
                    raise ValueError(f"Remote path not found: {remote_path}")

                if node.is_dir:
                    stats = await self._generator.generate_strm_files(
                        root_id=node.fid,
                        remote_path=remote_prefix,
                        only_video=self.only_video,
                        max_files=self.max_files,
                        recursive=self.recursive,
                        concurrent_limit=concurrent_limit,
                    )
                    generated = stats.get("files", [])
                else:
                    file_remote_path = remote_prefix or node.file_name
                    rel_path = await self._generator.generate_single_file_strm(
                        file_id=node.fid,
                        remote_path=file_remote_path,
                    )
                    generated = [rel_path] if rel_path else []

            # 保存扫描记录（用于 UI 展示/历史），失败不影响主流程
            try:
                self.database.save_record(remote_path)
            except Exception as e:
                logger.warning(f"Save scan record failed (ignored): {e}")

            # STRM 生成后触发 Emby 刷新（不影响主流程）
            try:
                from app.services.emby_service import get_emby_service

                await get_emby_service().trigger_refresh_on_event("strm_generate")
            except Exception as e:
                logger.warning(f"Trigger Emby refresh failed (ignored): {e}")

            return generated
        finally:
            await self.close()

    async def close(self):
        if self._generator:
            await self._generator.close()
            self._generator = None
        logger.debug("StrmService closed")

