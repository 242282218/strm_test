"""
媒体整理服务 (Rename Service)

提供媒体文件重命名功能:
- 智能识别文件名
- TMDB匹配获取标准标题
- 规范化命名
- 批量处理
- 回滚机制
"""

import os
import uuid
import shutil
import hashlib
import asyncio
import re
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from sqlalchemy.orm import Session
from app.core.db import SessionLocal
from app.core.logging import get_logger
from app.models.scrape import RenameHistory, RenameBatch
from app.services.tmdb_service import get_tmdb_service, TMDBService, _global_tmdb_service
from app.services.notification_service import get_notification_service, NotificationType
from app.utils.media_parser import MediaParser
from app.core.validators import validate_path

logger = get_logger(__name__)

# 关联文件扩展名
RELATED_EXTENSIONS = {'.nfo', '.jpg', '.png', '.srt', '.ass', '.sub', '.idx', '.sup'}

# 视频扩展名
VIDEO_EXTENSIONS = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.ts', '.m2ts', '.strm'}


@dataclass
class RenameItem:
    """单个重命名项目"""
    original_path: str
    original_name: str
    new_path: Optional[str] = None
    new_name: Optional[str] = None
    tmdb_id: Optional[int] = None
    title: Optional[str] = None
    year: Optional[int] = None
    season: Optional[int] = None
    episode: Optional[int] = None
    confidence: float = 0.0
    status: str = "pending"  # pending/matched/skipped/error
    error_message: Optional[str] = None
    related_files: List[str] = field(default_factory=list)


@dataclass
class RenamePreviewResult:
    """预览结果"""
    batch_id: str
    target_path: str
    total_items: int
    matched_items: int
    skipped_items: int
    items: List[RenameItem]


@dataclass 
class RenameExecuteResult:
    """执行结果"""
    batch_id: str
    total_items: int
    success_items: int
    failed_items: int
    skipped_items: int


class RenameService:
    """媒体重命名服务"""
    
    _instance = None
    
    # 默认命名模板
    TEMPLATES = {
        "movie": "{title} ({year})",
        "movie_folder": "{title} ({year})",
        "tv_show_folder": "{title} ({year})",
        "tv_season_folder": "Season {season:02d}",
        "tv_episode": "{title} - S{season:02d}E{episode:02d}",
        "tv_episode_with_title": "{title} - S{season:02d}E{episode:02d} - {episode_title}"
    }
    
    def __init__(self):
        self.tmdb_service = _global_tmdb_service
        self.notification_service = get_notification_service()
        self.confidence_threshold = 0.7
        
    @classmethod
    def get_instance(cls):
        if not cls._instance:
            cls._instance = RenameService()
        return cls._instance
    
    def _get_tmdb_service(self) -> Optional[TMDBService]:
        """获取TMDB服务（Lazy Loading）"""
        if self.tmdb_service:
            return self.tmdb_service
            
        from app.services.config_service import ConfigManager
        from app.services.cache_service import get_cache_service
        
        config = ConfigManager()
        api_key = config.get("api_keys.tmdb_api_key") or config.get("tmdb.api_key")
        if api_key:
            self.tmdb_service = get_tmdb_service(api_key=api_key, cache_service=get_cache_service())
        return self.tmdb_service

    def _generate_file_id(self, path: str) -> str:
        """生成文件唯一ID"""
        return hashlib.md5(path.encode()).hexdigest()[:16]

    async def _scan_media_files_async(self, path: str, recursive: bool = True) -> List[str]:
        """异步扫描目录获取媒体文件"""
        loop = asyncio.get_event_loop()
        
        def _scan():
            files = []
            if not os.path.exists(path):
                return files
                
            if os.path.isfile(path):
                ext = os.path.splitext(path)[1].lower()
                if ext in VIDEO_EXTENSIONS:
                    return [path]
                return []
                
            for root, _, filenames in os.walk(path):
                for filename in filenames:
                    ext = os.path.splitext(filename)[1].lower()
                    if ext in VIDEO_EXTENSIONS:
                        files.append(os.path.join(root, filename))
                if not recursive:
                    break
            return files
            
        return await loop.run_in_executor(None, _scan) # None uses default ThreadPoolExecutor

    async def preview_rename(self, path: str, **kwargs) -> Dict[str, Any]:
        """
        预览重命名 (SDK兼容接口)

        Args:
            path: 目标路径
            **kwargs: 其他参数

        Returns:
            预览结果字典
        """
        try:
            result = await self.preview(
                target_path=path,
                media_type=kwargs.get("media_type", "auto"),
                options=kwargs
            )
            return {
                "batch_id": result.batch_id,
                "tasks": [
                    {
                        "original_path": item.original_path,
                        "original_name": item.original_name,
                        "new_path": item.new_path,
                        "new_name": item.new_name,
                        "status": item.status,
                        "confidence": item.confidence
                    }
                    for item in result.items
                ]
            }
        except Exception as e:
            return {"error": str(e), "tasks": []}

    async def preview(
        self,
        target_path: str,
        media_type: str = "auto",
        options: Dict[str, Any] = None
    ) -> RenamePreviewResult:
        """预览重命名结果（不实际修改文件）"""
        target_path = validate_path(target_path, "target_path", allow_absolute=True)
        options = options or {}
        batch_id = str(uuid.uuid4())
        
        # 异步扫描文件
        files = await self._scan_media_files_async(target_path, recursive=options.get("recursive", True))
        
        items = []
        matched_count = 0
        skipped_count = 0
        use_ai = options.get("use_ai", False)
        batch_size = options.get("batch_size", 10) # 默认并发 10
        
        # 处理单个文件的函数
        async def process_file(file_path):
            filename = os.path.basename(file_path)
            ext = os.path.splitext(filename)[1]
            
            item = RenameItem(
                original_path=file_path,
                original_name=filename,
                related_files=self._find_related_files(file_path)
            )
            
            # 匹配TMDB
            match, confidence = await self._match_media(filename, media_type, use_ai=use_ai)
            
            if match and confidence >= self.confidence_threshold:
                folder_name, new_name = self._generate_new_name(match, ext, options)
                base_dir = os.path.dirname(target_path) if os.path.isfile(target_path) else target_path
                
                if options.get("create_folders", True):
                    new_path = os.path.join(base_dir, folder_name, new_name)
                else:
                    new_path = os.path.join(os.path.dirname(file_path), new_name)
                
                item.new_path = new_path
                item.new_name = new_name
                item.tmdb_id = match.get("id")
                item.title = match.get("title")
                item.year = match.get("year")
                item.season = match.get("season")
                item.episode = match.get("episode")
                item.confidence = confidence
                item.status = "matched"
            else:
                item.status = "skipped"
                item.error_message = f"Confidence too low: {confidence:.2f}" if match else "No TMDB match"
                
            return item

        # 批量处理循环
        for i in range(0, len(files), batch_size):
            batch_files = files[i:i + batch_size]
            tasks = [process_file(f) for f in batch_files]
            
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for res in batch_results:
                if isinstance(res, Exception):
                    logger.error(f"Error processing file in preview: {res}")
                    continue
                
                items.append(res)
                if res.status == "matched":
                    matched_count += 1
                else:
                    skipped_count += 1
            
            # 稍微延时避免 TMDB 限流
            await asyncio.sleep(0.1)
        
        # 保存预览到数据库 (批量写入优化)
        db = SessionLocal()
        try:
            batch = RenameBatch(
                batch_id=batch_id,
                target_path=target_path,
                media_type=media_type,
                total_items=len(items),
                status="previewing",
                options=options
            )
            db.add(batch)
            
            # 批量转换对象
            history_objs = []
            for item in items:
                history_objs.append(RenameHistory(
                    batch_id=batch_id,
                    file_id=self._generate_file_id(item.original_path),
                    original_path=item.original_path,
                    original_name=item.original_name,
                    new_path=item.new_path,
                    new_name=item.new_name,
                    tmdb_id=item.tmdb_id,
                    confidence=item.confidence,
                    status=item.status,
                    error_message=item.error_message
                ))
            
            # 使用 bulk_save_objects 提升写入性能
            db.bulk_save_objects(history_objs)
            db.commit()
        finally:
            db.close()

        # 返回预览结果
        return RenamePreviewResult(
            batch_id=batch_id,
            target_path=target_path,
            total_items=len(items),
            matched_items=matched_count,
            skipped_items=skipped_count,
            items=items
        )

    async def execute(self, batch_id: str) -> RenameExecuteResult:
        """执行重命名操作"""
        db = SessionLocal()
        
        try:
            batch = db.query(RenameBatch).filter(RenameBatch.batch_id == batch_id).first()
            if not batch:
                raise ValueError(f"Batch {batch_id} not found")
                
            if batch.status not in ["previewing", "pending"]:
                raise ValueError(f"Batch {batch_id} cannot be executed (status: {batch.status})")
            
            batch.status = "executing"
            batch.executed_at = datetime.now()
            db.commit()
            
            items = db.query(RenameHistory).filter(
                RenameHistory.batch_id == batch_id,
                RenameHistory.status == "matched"
            ).all()
            
            success = 0
            failed = 0
            
            for item in items:
                try:
                    # 创建目标目录
                    target_dir = os.path.dirname(item.new_path)
                    if not os.path.exists(target_dir):
                        os.makedirs(target_dir, exist_ok=True)
                    
                    # 检查目标是否已存在
                    if os.path.exists(item.new_path):
                        # 添加后缀避免覆盖
                        base, ext = os.path.splitext(item.new_path)
                        counter = 1
                        while os.path.exists(f"{base}_{counter}{ext}"):
                            counter += 1
                        item.new_path = f"{base}_{counter}{ext}"
                    
                    # 执行移动/重命名
                    shutil.move(item.original_path, item.new_path)
                    
                    # 移动关联文件
                    # (简化：此处只移动同名的 .nfo 文件)
                    original_base = os.path.splitext(item.original_path)[0]
                    new_base = os.path.splitext(item.new_path)[0]
                    
                    for ext in RELATED_EXTENSIONS:
                        related_src = original_base + ext
                        if os.path.exists(related_src):
                            related_dst = new_base + ext
                            shutil.move(related_src, related_dst)
                    
                    item.status = "success"
                    item.executed_at = datetime.now()
                    success += 1
                    
                except Exception as e:
                    logger.error(f"Failed to rename {item.original_path}: {e}")
                    item.status = "failed"
                    item.error_message = str(e)
                    failed += 1
                    
                db.commit()
            
            batch.success_items = success
            batch.failed_items = failed
            batch.skipped_items = batch.total_items - success - failed
            batch.status = "completed" if failed == 0 else "completed_with_errors"
            batch.completed_at = datetime.now()
            db.commit()
            
            # 发送通知
            await self.notification_service.send_notification(
                type=NotificationType.TASK_COMPLETED,
                title="媒体整理完成",
                content=f"成功: {success}, 失败: {failed}"
            )
            
            return RenameExecuteResult(
                batch_id=batch_id,
                total_items=batch.total_items,
                success_items=success,
                failed_items=failed,
                skipped_items=batch.skipped_items
            )
            
        finally:
            db.close()

    async def rollback(self, batch_id: str) -> RenameExecuteResult:
        """回滚指定批次的所有操作"""
        db = SessionLocal()
        
        try:
            batch = db.query(RenameBatch).filter(RenameBatch.batch_id == batch_id).first()
            if not batch:
                raise ValueError(f"Batch {batch_id} not found")
            
            if batch.status == "rolled_back":
                raise ValueError(f"Batch {batch_id} already rolled back")
            
            items = db.query(RenameHistory).filter(
                RenameHistory.batch_id == batch_id,
                RenameHistory.status == "success"
            ).order_by(RenameHistory.executed_at.desc()).all()
            
            success = 0
            failed = 0
            
            for item in items:
                try:
                    # 检查新位置文件是否存在
                    if not os.path.exists(item.new_path):
                        item.error_message = "File not found at new location"
                        failed += 1
                        continue
                    
                    # 检查原位置是否可用
                    original_dir = os.path.dirname(item.original_path)
                    if not os.path.exists(original_dir):
                        os.makedirs(original_dir, exist_ok=True)
                    
                    if os.path.exists(item.original_path):
                        item.error_message = "Original path occupied"
                        failed += 1
                        continue
                    
                    # 执行回滚
                    shutil.move(item.new_path, item.original_path)
                    
                    # 回滚关联文件
                    new_base = os.path.splitext(item.new_path)[0]
                    original_base = os.path.splitext(item.original_path)[0]
                    
                    for ext in RELATED_EXTENSIONS:
                        related_new = new_base + ext
                        if os.path.exists(related_new):
                            related_original = original_base + ext
                            shutil.move(related_new, related_original)
                    
                    item.status = "rolled_back"
                    item.rolled_back_at = datetime.now()
                    success += 1
                    
                except Exception as e:
                    logger.error(f"Failed to rollback {item.new_path}: {e}")
                    item.error_message = str(e)
                    failed += 1
                    
                db.commit()
            
            batch.status = "rolled_back"
            db.commit()
            
            await self.notification_service.send_notification(
                type=NotificationType.TASK_COMPLETED,
                title="回滚完成",
                content=f"成功回滚: {success}, 失败: {failed}"
            )
            
            return RenameExecuteResult(
                batch_id=batch_id,
                total_items=len(items),
                success_items=success,
                failed_items=failed,
                skipped_items=0
            )
            
        finally:
            db.close()

    def get_batch(self, batch_id: str) -> Optional[RenameBatch]:
        """获取批次详情"""
        db = SessionLocal()
        try:
            return db.query(RenameBatch).filter(RenameBatch.batch_id == batch_id).first()
        finally:
            db.close()

    def list_batches(self, skip: int = 0, limit: int = 20) -> List[RenameBatch]:
        """获取批次列表"""
        db = SessionLocal()
        try:
            return db.query(RenameBatch).order_by(
                RenameBatch.created_at.desc()
            ).offset(skip).limit(limit).all()
        finally:
            db.close()

    def _find_related_files(self, file_path: str) -> List[str]:
        """
        查找与媒体文件关联的辅助文件
        
        Args:
            file_path: 媒体文件路径
            
        Returns:
            关联文件路径列表
        """
        related_files = []
        base_path = os.path.splitext(file_path)[0]
        
        for ext in RELATED_EXTENSIONS:
            related_path = base_path + ext
            if os.path.exists(related_path):
                related_files.append(related_path)
        
        return related_files

    async def _match_media(
        self,
        filename: str,
        media_type: str = "auto",
        use_ai: bool = False
    ) -> Tuple[Optional[Dict[str, Any]], float]:
        """
        匹配TMDB媒体信息
        
        Args:
            filename: 文件名
            media_type: 媒体类型 (auto/movie/tv)
            use_ai: 是否使用AI解析
            
        Returns:
            (匹配结果字典, 置信度)
        """
        tmdb_service = self._get_tmdb_service()
        if not tmdb_service:
            return None, 0.0
        
        # 解析文件名
        parsed_info = MediaParser.parse(filename)
        
        if not parsed_info or not parsed_info.get("title"):
            return None, 0.0
        
        title = parsed_info.get("title", "")
        year = parsed_info.get("year")
        season = parsed_info.get("season")
        episode = parsed_info.get("episode")
        
        # 判断媒体类型
        if media_type == "auto":
            if season is not None or episode is not None:
                media_type = "tv"
            else:
                media_type = "movie"
        
        try:
            if media_type == "movie":
                result = await tmdb_service.search_movie(title, year=year)
                if result and result.results:
                    movie = result.results[0]
                    match_info = {
                        "id": movie.id,
                        "title": movie.title,
                        "original_title": movie.original_title,
                        "year": self._extract_year(movie.release_date),
                        "media_type": "movie"
                    }
                    confidence = self._calculate_confidence(parsed_info, match_info)
                    return match_info, confidence
            else:
                result = await tmdb_service.search_tv(title, year=year)
                if result and result.results:
                    tv_show = result.results[0]
                    match_info = {
                        "id": tv_show.id,
                        "title": tv_show.name,
                        "original_title": tv_show.original_name,
                        "year": self._extract_year(tv_show.first_air_date),
                        "media_type": "tv",
                        "season": season,
                        "episode": episode
                    }
                    confidence = self._calculate_confidence(parsed_info, match_info)
                    return match_info, confidence
        except Exception as e:
            logger.error(f"TMDB search failed for {filename}: {e}")
        
        return None, 0.0

    def _extract_year(self, date_str: Optional[str]) -> Optional[int]:
        """从日期字符串提取年份"""
        if not date_str:
            return None
        try:
            return int(date_str[:4])
        except (ValueError, IndexError):
            return None

    def _calculate_confidence(
        self,
        parsed_info: Dict[str, Any],
        match_info: Dict[str, Any]
    ) -> float:
        """
        计算匹配置信度
        
        Args:
            parsed_info: 解析的文件名信息
            match_info: TMDB匹配结果
            
        Returns:
            置信度 (0.0 - 1.0)
        """
        confidence = 0.0
        
        # 标题相似度 (基础分)
        parsed_title = parsed_info.get("title", "").lower()
        match_title = match_info.get("title", "").lower()
        original_title = match_info.get("original_title", "").lower()
        
        if parsed_title == match_title or parsed_title == original_title:
            confidence += 0.5
        elif parsed_title in match_title or match_title in parsed_title:
            confidence += 0.35
        elif parsed_title in original_title or original_title in parsed_title:
            confidence += 0.3
        else:
            # 计算词重叠
            parsed_words = set(parsed_title.split())
            match_words = set(match_title.split())
            if parsed_words and match_words:
                overlap = len(parsed_words & match_words) / len(parsed_words | match_words)
                confidence += overlap * 0.3
        
        # 年份匹配
        parsed_year = parsed_info.get("year")
        match_year = match_info.get("year")
        if parsed_year and match_year:
            if parsed_year == match_year:
                confidence += 0.3
            elif abs(parsed_year - match_year) <= 1:
                confidence += 0.15
        else:
            # 没有年份信息时，给予部分分数
            confidence += 0.1
        
        # 媒体类型匹配
        parsed_media_type = "tv" if parsed_info.get("season") or parsed_info.get("episode") else "movie"
        match_media_type = match_info.get("media_type", "movie")
        if parsed_media_type == match_media_type:
            confidence += 0.2
        
        return min(confidence, 1.0)

    def _generate_new_name(
        self,
        match_info: Dict[str, Any],
        ext: str,
        options: Optional[Dict[str, Any]] = None
    ) -> Tuple[str, str]:
        """
        生成新的文件名

        Args:
            match_info: TMDB匹配信息
            ext: 文件扩展名
            options: 配置选项

        Returns:
            (文件夹名称, 文件名称)
        """
        options = options or {}
        title = match_info.get("title", "Unknown")
        year = match_info.get("year")
        media_type = match_info.get("media_type", "movie")
        season = match_info.get("season")
        episode = match_info.get("episode")
        episode_title = match_info.get("episode_title", "")

        # 清理标题中的非法字符
        safe_title = self._sanitize_filename(title)

        if media_type == "movie":
            # 电影命名
            if year:
                folder_name = self.TEMPLATES["movie_folder"].format(
                    title=safe_title,
                    year=year
                )
                file_name = f"{safe_title} ({year}){ext}"
            else:
                folder_name = safe_title
                file_name = f"{safe_title}{ext}"
        else:
            # 电视剧命名 - 文件夹包含Season信息
            if year:
                show_folder = self.TEMPLATES["tv_show_folder"].format(
                    title=safe_title,
                    year=year
                )
            else:
                show_folder = safe_title

            # 如果有季信息，添加Season子文件夹
            if season is not None:
                season_folder = self.TEMPLATES["tv_season_folder"].format(season=season)
                folder_name = os.path.join(show_folder, season_folder)
            else:
                folder_name = show_folder

            if season is not None and episode is not None:
                if episode_title:
                    file_name = self.TEMPLATES["tv_episode_with_title"].format(
                        title=safe_title,
                        season=season,
                        episode=episode,
                        episode_title=episode_title
                    ) + ext
                else:
                    file_name = self.TEMPLATES["tv_episode"].format(
                        title=safe_title,
                        season=season,
                        episode=episode
                    ) + ext
            else:
                file_name = f"{safe_title}{ext}"

        return folder_name, file_name

    def _sanitize_filename(self, filename: str) -> str:
        """
        清理文件名中的非法字符
        
        Args:
            filename: 原始文件名
            
        Returns:
            清理后的文件名
        """
        # Windows非法字符: < > : " / \ | ? *
        illegal_chars = r'[<>:"/\\|?*]'
        sanitized = re.sub(illegal_chars, '_', filename)
        # 去除首尾空格和点
        sanitized = sanitized.strip(' .')
        return sanitized or "Unknown"


def get_rename_service():
    return RenameService.get_instance()


# 兼容SDK的类名别名
MediaRenameService = RenameService
