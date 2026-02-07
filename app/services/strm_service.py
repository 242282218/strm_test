"""
STRM 服务模块

核心职责：
1) 根据远端路径扫描夸克网盘文件
2) 生成可播放的 .strm 文件（302 / WebDAV 等模式）
"""

from __future__ import annotations

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
        overwrite_existing: bool = False,
    ):
        self.cookie = cookie
        self.database = database
        self.recursive = recursive
        self.base_url = base_url
        self.strm_url_mode = strm_url_mode
        self.max_files = max_files
        self.only_video = only_video
        self.overwrite_existing = overwrite_existing
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

    async def scan_directory(self, remote_path: str, local_path: str, concurrent_limit: int = 5) -> dict:
        remote_path = self._normalize_remote_path(remote_path)
        remote_prefix = remote_path.strip("/")  # used for WebDAV path & proxy fallback
        resolved_remote_prefix = remote_prefix

        self._generator = STRMGenerator(
            cookie=self.cookie,
            output_dir=local_path,
            base_url=self.base_url,
            strm_url_mode=self.strm_url_mode,
            overwrite_existing=self.overwrite_existing,
        )
        result = {
            "strms": [],
            "generated_count": 0,
            "skipped_count": 0,
            "failed_count": 0,
            "total_files": 0,
        }

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
                result["strms"] = stats.get("files", [])
                result["generated_count"] = stats.get("generated_files", 0)
                result["skipped_count"] = stats.get("skipped_files", 0)
                result["failed_count"] = stats.get("failed_files", 0)
                result["total_files"] = stats.get("total_files", 0)
            else:
                # 先尝试通过路径获取文件
                node = await self._generator.service.get_file_by_path(remote_path)
                
                # 如果路径查找失败，尝试通过文件ID获取（支持从前端文件浏览器直接传入ID）
                if not node:
                    try:
                        fid = remote_path.lstrip("/")
                        file_info = await self._generator.service.get_file_info(fid)
                        if file_info and file_info.get('fid'):
                            from app.models.quark import FileModel
                            info = file_info
                            # file_type: 0=目录, 1=文件
                            is_dir = info.get('file_type') == 0
                            node = FileModel(
                                fid=info['fid'],
                                file_name=info.get('file_name', 'Unknown'),
                                file=not is_dir,  # file=True 表示是文件，False表示是目录
                                category=info.get('category', 0),
                                size=info.get('size', 0),
                                created_at=info.get('created_at', 0),
                                updated_at=info.get('updated_at', 0),
                                l_created_at=info.get('l_created_at', 0),
                                l_updated_at=info.get('l_updated_at', 0)
                            )
                            logger.info(f"Got file by ID: {node.file_name}, is_dir={node.is_dir}, file={node.file}")
                            full_path = await self._generator.service.get_full_path_by_fid(node.fid)
                            if full_path:
                                resolved_remote_prefix = full_path
                                logger.info(f"Resolved full path by fid: {node.fid} -> {resolved_remote_prefix}")
                    except Exception as e:
                        logger.warning(f"Failed to get file by ID: {e}")
                
                if not node:
                    raise ValueError(f"Remote path not found: {remote_path}")

                if node.is_dir:
                    stats = await self._generator.generate_strm_files(
                        root_id=node.fid,
                        remote_path=resolved_remote_prefix,
                        only_video=self.only_video,
                        max_files=self.max_files,
                        recursive=self.recursive,
                        concurrent_limit=concurrent_limit,
                    )
                    result["strms"] = stats.get("files", [])
                    result["generated_count"] = stats.get("generated_files", 0)
                    result["skipped_count"] = stats.get("skipped_files", 0)
                    result["failed_count"] = stats.get("failed_files", 0)
                    result["total_files"] = stats.get("total_files", 0)
                else:
                    file_remote_path = resolved_remote_prefix or node.file_name
                    rel_path = await self._generator.generate_single_file_strm(
                        file_id=node.fid,
                        remote_path=file_remote_path,
                    )
                    result["total_files"] = 1
                    if rel_path:
                        result["strms"] = [rel_path]
                        result["generated_count"] = 1
                    else:
                        result["skipped_count"] = 1

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

            return result
        finally:
            await self.close()

    async def close(self):
        if self._generator:
            await self._generator.close()
            self._generator = None
        logger.debug("StrmService closed")
