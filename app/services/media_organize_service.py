import os
import asyncio
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from urllib.parse import quote

from app.services.quark_service import QuarkService
from app.services.cloud_drive_service import CloudDriveService
from app.services.rename_service import get_rename_service, RenameService
from app.models.task import Task
from app.core.logging import get_logger
from app.core.config_manager import ConfigManager
from app.models.quark import FileModel

logger = get_logger(__name__)

@dataclass
class ScannedFile:
    fid: str
    file_name: str
    full_path: str
    size: int

class MediaOrganizeService:
    def __init__(self, db_session):
        self.db = db_session
        self.cloud_drive_service = CloudDriveService(db_session)
        self.rename_service = get_rename_service()
        self.config = ConfigManager()
        
    async def process_strm_generation(self, task: Task, update_progress):
        """
        执行 STRM 生成任务
        :param task: 任务对象
        :param update_progress: 回调函数 async (progress, step_name, logs)
        """
        params = task.params or {}
        drive_id = params.get('drive_id')
        source_dir = params.get('source_dir', '/')
        target_dir = params.get('target_dir', 'data/media')
        media_type = params.get('media_type', 'auto')
        
        # 兼容旧逻辑，如果没有 drive_id 但有 cookie
        if not drive_id and not params.get('cookie'):
            # 尝试获取默认驱动器
            drive = self.cloud_drive_service.get_default_drive() # 需要我在 CloudDriveService 加这个方法？
            # 暂时报错
            if not drive:
                 # 使用 Config 中的 Cookie? 
                 cookie = self.config.get("quark.cookie")
                 if not cookie:
                     raise ValueError("No drive_id provided and no default cookie found")
                 quark_service = QuarkService(cookie)
            else:
                 quark_service = QuarkService(drive.cookie)
        elif drive_id:
            drive = self.cloud_drive_service.get_drive(drive_id)
            if not drive:
                raise ValueError(f"Drive {drive_id} not found")
            quark_service = QuarkService(drive.cookie)
        else:
             # params['cookie'] exists
             quark_service = QuarkService(params['cookie'])
        
        processed_files = 0
        generated_files = 0
        skipped_files = 0
        errors = 0
        
        try:
            # 1. 扫描文件
            await update_progress(5, f"Scanning {source_dir}...", [])
            
            scanned_files = await self._scan_recursive(quark_service, source_dir)
            total_files = len(scanned_files)
            
            await update_progress(10, f"Found {total_files} video files. Starting processing...", [])
            
            if total_files == 0:
                await update_progress(100, "No video files found.", [])
                return

            # 获取 WebDAV 配置用于构造 URL
            webdav_user = self.config.get("webdav.username", "")
            webdav_pass = self.config.get("webdav.password", "")
            
            # 2. 处理文件
            for i, file in enumerate(scanned_files):
                try:
                    current_progress = 10 + int((i / total_files) * 80)
                    await update_progress(current_progress, f"Processing {file.file_name}", [])
                    
                    # 匹配 TMDB
                    match_info, confidence = await self.rename_service._match_media(
                        file.file_name, 
                        media_type=media_type
                    )
                    
                    if match_info and confidence >= self.rename_service.confidence_threshold:
                        # 生成目标路径
                        ext = os.path.splitext(file.file_name)[1]
                        folder_name, new_name = self.rename_service._generate_new_name(match_info, ext)
                        
                        # STRM 路径: target_dir / folder_name / new_name.strm
                        strm_name = os.path.splitext(new_name)[0] + ".strm"
                        
                        relative_path = os.path.join(folder_name, strm_name)
                        abs_target_path = os.path.join(target_dir, relative_path)
                        
                        webdav_url = self._build_webdav_url(file.full_path, webdav_user, webdav_pass)
                        
                        # 写入 STRM
                        self._write_strm(abs_target_path, webdav_url)
                        generated_files += 1
                        
                        await update_progress(current_progress, f"Generated: {strm_name}", [])
                    else:
                        skipped_files += 1
                        # 记录未匹配日志
                        await update_progress(current_progress, f"Skipped (No Match): {file.file_name}", [])
                        
                except Exception as e:
                    errors += 1
                    logger.error(f"Error processing {file.file_name}: {e}")
                    
                processed_files += 1
            
            # 3. 完成
            summary = f"Completed. Processed: {processed_files}, Generated: {generated_files}, Skipped: {skipped_files}, Errors: {errors}"
            await update_progress(100, summary, [])
            
        finally:
            await quark_service.close()
            
    async def _scan_recursive(self, service: QuarkService, root_path: str) -> List[ScannedFile]:
        """递归扫描视频文件"""
        results = []
        
        root_file = await service.get_file_by_path(root_path)
        if not root_file:
            logger.warning(f"Path not found: {root_path}")
            return []
            
        async def _walk(fid, current_path):
            files = await service.get_files(fid, page_size=1000)
            for f in files:
                child_path = os.path.join(current_path, f.file_name).replace("\\", "/")
                if f.is_dir:
                    await _walk(f.fid, child_path)
                else:
                    if self._is_video(f.file_name):
                        results.append(ScannedFile(
                            fid=f.fid,
                            file_name=f.file_name,
                            full_path=child_path,
                            size=f.size
                        ))
        
        if root_file.is_dir:
            await _walk(root_file.fid, root_path)
        elif self._is_video(root_file.file_name):
             results.append(ScannedFile(
                fid=root_file.fid,
                file_name=root_file.file_name,
                full_path=root_path,
                size=root_file.size
            ))
            
        return results

    def _is_video(self, filename: str) -> bool:
        ext = os.path.splitext(filename)[1].lower()
        return ext in ['.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.ts', '.m2ts']

    def _build_webdav_url(self, path: str, user: str, passw: str) -> str:
        if not path.startswith('/'):
            path = '/' + path
        
        # 路径编码，保留 /
        safe_path = quote(path).replace("%2F", "/")
        
        port = self.config.get("app.port", 8000)
        host = self.config.get("app.host", "localhost")
        if host == "0.0.0.0": host = "127.0.0.1" 
        
        # user:pass
        auth = f"{user}:{passw}@" if user and passw else ""
        
        return f"http://{auth}{host}:{port}/dav{safe_path}"

    def _write_strm(self, path: str, content: str):
        if hasattr(os, 'makedirs'):
            os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)

    def get_default_drive(self):
        # 简单的占位符，实际应该调用 CloudDriveService
        pass
