"""
智能重命名服务

集成多种重命名算法:
1. 标准本地算法 (基于正则解析 + TMDB 匹配)
2. AI Fallback 算法 (当本地算法置信度低时调用 AI)
3. Emby 规范命名 (确保输出符合 Emby 标准)

特性:
- 算法选择配置
- 命名规则自定义
- 批量处理
- 预览功能
- 回滚机制
"""

import os
import uuid
import shutil
import hashlib
import asyncio
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from sqlalchemy.orm import Session
from enum import Enum

from app.core.db import SessionLocal
from app.core.logging import get_logger
from app.core.validators import validate_path
from app.models.scrape import RenameHistory, RenameBatch
from app.services.tmdb_service import get_tmdb_service, TMDBService
from app.services.notification_service import get_notification_service, NotificationType
from app.services.ai_parser_service import get_ai_parser_service
from app.services.emby_naming_service import (
    get_emby_naming_service, 
    NamingConfig, 
    MediaType as NamingMediaType
)
from app.utils.media_parser import MediaParser

logger = get_logger(__name__)


class AlgorithmType(Enum):
    """重命名算法类型"""
    STANDARD = "standard"       # 标准本地算法 (正则 + TMDB)
    AI_ENHANCED = "ai_enhanced" # AI 增强算法 (本地 + AI fallback)
    AI_ONLY = "ai_only"         # 纯 AI 算法


class NamingStandard(Enum):
    """命名标准"""
    EMBY = "emby"               # Emby 标准
    PLEX = "plex"               # Plex 标准
    KODI = "kodi"               # Kodi 标准
    CUSTOM = "custom"           # 自定义


@dataclass
class SmartRenameOptions:
    """智能重命名选项"""
    # 算法选择
    algorithm: AlgorithmType = AlgorithmType.AI_ENHANCED
    
    # 命名标准
    naming_standard: NamingStandard = NamingStandard.EMBY
    
    # 命名配置
    naming_config: NamingConfig = field(default_factory=NamingConfig)
    
    # 处理选项
    recursive: bool = True
    create_folders: bool = True
    include_subtitles: bool = True
    move_related_files: bool = True
    
    # AI 选项
    ai_confidence_threshold: float = 0.7
    force_ai_parse: bool = False
    
    # 批量处理
    batch_size: int = 10
    concurrent_limit: int = 5
    
    # 确认选项
    auto_confirm_high_confidence: bool = True
    high_confidence_threshold: float = 0.9


@dataclass
class SmartRenameItem:
    """智能重命名项目"""
    original_path: str
    original_name: str
    new_path: Optional[str] = None
    new_name: Optional[str] = None
    
    # 解析结果
    parsed_info: Dict[str, Any] = field(default_factory=dict)
    
    # TMDB 匹配
    tmdb_id: Optional[int] = None
    tmdb_title: Optional[str] = None
    tmdb_year: Optional[int] = None
    
    # 媒体类型
    media_type: str = "unknown"  # movie/tv/anime
    season: Optional[int] = None
    episode: Optional[int] = None
    episode_title: Optional[str] = None
    
    # 置信度
    parse_confidence: float = 0.0
    match_confidence: float = 0.0
    overall_confidence: float = 0.0
    
    # 状态
    status: str = "pending"  # pending/parsed/matched/skipped/error
    error_message: Optional[str] = None
    needs_confirmation: bool = False
    confirmation_reason: Optional[str] = None
    
    # 算法信息
    used_algorithm: Optional[str] = None
    
    # 关联文件
    related_files: List[str] = field(default_factory=list)


@dataclass
class SmartRenamePreviewResult:
    """智能重命名预览结果"""
    batch_id: str
    target_path: str
    total_items: int
    parsed_items: int
    matched_items: int
    skipped_items: int
    needs_confirmation: int
    items: List[SmartRenameItem]
    algorithm_used: str
    naming_standard: str


class SmartRenameService:
    """
    智能重命名服务
    
    用途: 提供基于多种算法的智能媒体文件重命名功能
    输入: 目标路径和重命名选项
    输出: 预览结果或执行结果
    副作用: 执行阶段会修改文件系统 (重命名/移动文件)
    """
    
    _instance = None
    
    def __init__(self):
        self.tmdb_service: Optional[TMDBService] = None
        self.notification_service = get_notification_service()
        self.naming_service = get_emby_naming_service()
        
    @classmethod
    def get_instance(cls):
        if not cls._instance:
            cls._instance = SmartRenameService()
        return cls._instance
    
    def _get_tmdb_service(self) -> Optional[TMDBService]:
        """获取 TMDB 服务 (延迟加载)"""
        if self.tmdb_service:
            return self.tmdb_service
            
        from app.services.config_service import ConfigManager
        from app.services.cache_service import get_cache_service
        
        config = ConfigManager()
        api_key = config.get("api_keys.tmdb_api_key") or config.get("tmdb.api_key")
        if api_key:
            self.tmdb_service = get_tmdb_service(
                api_key=api_key, 
                cache_service=get_cache_service()
            )
        return self.tmdb_service
    
    def _generate_file_id(self, path: str) -> str:
        """生成文件唯一 ID"""
        return hashlib.md5(path.encode()).hexdigest()[:16]
    
    async def _scan_media_files(self, path: str, recursive: bool = True) -> List[str]:
        """
        扫描目录获取媒体文件
        
        用途: 异步扫描指定目录下的所有媒体文件
        输入:
            - path (str): 目标路径
            - recursive (bool): 是否递归扫描子目录
        输出:
            - List[str]: 媒体文件路径列表
        副作用: 无
        """
        video_extensions = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.ts', '.m2ts', '.strm'}
        
        files = []
        if not os.path.exists(path):
            return files
            
        if os.path.isfile(path):
            ext = os.path.splitext(path)[1].lower()
            if ext in video_extensions:
                return [path]
            return []
            
        for root, _, filenames in os.walk(path):
            for filename in filenames:
                ext = os.path.splitext(filename)[1].lower()
                if ext in video_extensions:
                    files.append(os.path.join(root, filename))
            if not recursive:
                break
                
        return files

    def _normalize_parsed_title(self, filename: str, parsed_info: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize parsed title to avoid duplicated extensions in generated names."""
        title = parsed_info.get("title")
        if not isinstance(title, str) or not title:
            return parsed_info

        ext = os.path.splitext(filename)[1]
        if not ext:
            return parsed_info

        if title.lower().endswith(ext.lower()):
            normalized = title[:-len(ext)].rstrip(" ._-")
            if normalized:
                normalized_info = dict(parsed_info)
                normalized_info["title"] = normalized
                return normalized_info

        return parsed_info
    
    async def _parse_with_algorithm(
        self,
        filename: str,
        algorithm: AlgorithmType,
        force_ai: bool = False,
        ai_timeout_seconds: Optional[int] = None
    ) -> Tuple[Dict[str, Any], str, float]:
        """
        使用指定算法解析文件名
        
        用途: 根据选择的算法解析文件名获取媒体信息
        输入:
            - filename (str): 文件名
            - algorithm (AlgorithmType): 算法类型
            - force_ai (bool): 是否强制使用 AI
        输出:
            - Tuple[Dict, str, float]: (解析结果, 使用的算法, 置信度)
        副作用: 无
        """
        if algorithm == AlgorithmType.AI_ONLY:
            # 纯 AI 算法
            ai_service = get_ai_parser_service()
            if ai_service.api_key:
                ai_result = await ai_service.parse_filename(filename, max_timeout_seconds=ai_timeout_seconds)
                if ai_result:
                    parsed_info = {
                        "title": ai_result.title,
                        "original_title": ai_result.original_title,
                        "year": ai_result.year,
                        "season": ai_result.season,
                        "episode": ai_result.episode,
                        "media_type": ai_result.media_type,
                        "ai_parsed": True
                    }
                    parsed_info = self._normalize_parsed_title(filename, parsed_info)
                    return parsed_info, "ai_only", ai_result.confidence
            # AI 不可用时回退到标准算法
            algorithm = AlgorithmType.STANDARD
        
        if algorithm == AlgorithmType.AI_ENHANCED or force_ai:
            # AI 增强算法
            parsed_info = await MediaParser.parse_with_ai(
                filename,
                force=force_ai,
                ai_timeout_seconds=ai_timeout_seconds
            )
            if parsed_info.get("ai_parsed"):
                parsed_info = self._normalize_parsed_title(filename, parsed_info)
                return parsed_info, "ai_enhanced", parsed_info.get("confidence", 0.8)
            # AI 解析失败时回退到正则
            algorithm = AlgorithmType.STANDARD
        
        # 标准本地算法 (正则)
        parsed_info = MediaParser.parse(filename)
        parsed_info = self._normalize_parsed_title(filename, parsed_info)
        
        # 计算置信度
        confidence = 0.5
        if parsed_info.get("year"):
            confidence += 0.2
        if parsed_info.get("season") or parsed_info.get("episode"):
            confidence += 0.2
        if parsed_info.get("title") != filename:
            confidence += 0.1
            
        return parsed_info, "standard", confidence
    
    async def _match_tmdb(
        self,
        parsed_info: Dict[str, Any],
        media_type_hint: Optional[str] = None
    ) -> Tuple[Optional[Dict[str, Any]], float]:
        """
        匹配 TMDB 信息
        
        用途: 使用解析结果搜索 TMDB 获取准确的媒体信息
        输入:
            - parsed_info (Dict): 解析的文件名信息
            - media_type_hint (str): 媒体类型提示
        输出:
            - Tuple[Optional[Dict], float]: (匹配结果, 置信度)
        副作用: 无
        """
        tmdb_service = self._get_tmdb_service()
        if not tmdb_service:
            return None, 0.0
        
        title = parsed_info.get("title", "")
        year = parsed_info.get("year")
        season = parsed_info.get("season")
        episode = parsed_info.get("episode")
        
        # 判断媒体类型
        if media_type_hint:
            media_type = media_type_hint
        elif season is not None or episode is not None:
            media_type = "tv"
        else:
            media_type = parsed_info.get("media_type", "movie")
        
        try:
            if media_type == "movie":
                result = await tmdb_service.search_movie(title, year=year)
                if result and result.results:
                    movie = result.results[0]
                    return {
                        "id": movie.id,
                        "title": movie.title,
                        "original_title": movie.original_title,
                        "year": self._extract_year(movie.release_date),
                        "media_type": "movie"
                    }, self._calculate_match_confidence(parsed_info, movie.title, movie.release_date)
            else:
                result = await tmdb_service.search_tv(title, year=year)
                if result and result.results:
                    tv_show = result.results[0]
                    return {
                        "id": tv_show.id,
                        "title": tv_show.name,
                        "original_title": tv_show.original_name,
                        "year": self._extract_year(tv_show.first_air_date),
                        "media_type": "tv"
                    }, self._calculate_match_confidence(parsed_info, tv_show.name, tv_show.first_air_date)
        except Exception as e:
            logger.error(f"TMDB search failed: {e}")
        
        return None, 0.0
    
    def _extract_year(self, date_str: Optional[str]) -> Optional[int]:
        """从日期字符串提取年份"""
        if not date_str:
            return None
        try:
            return int(date_str[:4])
        except (ValueError, IndexError):
            return None
    
    def _calculate_match_confidence(
        self,
        parsed_info: Dict[str, Any],
        match_title: str,
        match_date: Optional[str]
    ) -> float:
        """计算 TMDB 匹配置信度"""
        confidence = 0.0
        
        # 标题相似度
        parsed_title = parsed_info.get("title", "").lower()
        match_title_lower = match_title.lower()
        
        if parsed_title == match_title_lower:
            confidence += 0.5
        elif parsed_title in match_title_lower or match_title_lower in parsed_title:
            confidence += 0.35
        else:
            # 词重叠
            parsed_words = set(parsed_title.split())
            match_words = set(match_title_lower.split())
            if parsed_words and match_words:
                overlap = len(parsed_words & match_words) / len(parsed_words | match_words)
                confidence += overlap * 0.3
        
        # 年份匹配
        parsed_year = parsed_info.get("year")
        match_year = self._extract_year(match_date)
        if parsed_year and match_year:
            if parsed_year == match_year:
                confidence += 0.3
            elif abs(parsed_year - match_year) <= 1:
                confidence += 0.15
        else:
            confidence += 0.1
        
        return min(confidence, 1.0)
    
    def _generate_new_name(
        self,
        item: SmartRenameItem,
        options: SmartRenameOptions
    ) -> Tuple[str, str]:
        """
        生成新的文件名和路径
        
        用途: 根据媒体信息和命名标准生成新的文件名
        输入:
            - item (SmartRenameItem): 重命名项目
            - options (SmartRenameOptions): 重命名选项
        输出:
            - Tuple[str, str]: (新路径, 新文件名)
        副作用: 无
        """
        # 更新命名服务配置
        self.naming_service.config = options.naming_config
        
        media_type = item.media_type
        ext = os.path.splitext(item.original_name)[1]
        
        if media_type == "movie":
            folder_name, file_name = self.naming_service.generate_movie_name(
                title=item.tmdb_title or item.parsed_info.get("title", "Unknown"),
                year=item.tmdb_year or item.parsed_info.get("year"),
                extension=ext,
                tmdb_id=item.tmdb_id
            )
            
            if options.create_folders:
                new_path = os.path.join(os.path.dirname(item.original_path), folder_name, file_name)
            else:
                new_path = os.path.join(os.path.dirname(item.original_path), file_name)
                
        else:  # tv or anime
            show_folder, season_folder, file_name = self.naming_service.generate_tv_show_name(
                title=item.tmdb_title or item.parsed_info.get("title", "Unknown"),
                year=item.tmdb_year or item.parsed_info.get("year"),
                season=item.season,
                episode=item.episode,
                episode_title=item.episode_title,
                extension=ext,
                is_special=(media_type == "anime" and item.episode is None)
            )
            
            if options.create_folders and season_folder:
                new_path = os.path.join(
                    os.path.dirname(item.original_path),
                    show_folder,
                    season_folder,
                    file_name
                )
            elif options.create_folders:
                new_path = os.path.join(
                    os.path.dirname(item.original_path),
                    show_folder,
                    file_name
                )
            else:
                new_path = os.path.join(os.path.dirname(item.original_path), file_name)
        
        return new_path, file_name
    
    def _find_related_files(self, file_path: str) -> List[str]:
        """查找关联文件"""
        related_extensions = {'.nfo', '.jpg', '.png', '.srt', '.ass', '.sub', '.idx', '.sup'}
        related_files = []
        base_path = os.path.splitext(file_path)[0]
        
        for ext in related_extensions:
            related_path = base_path + ext
            if os.path.exists(related_path):
                related_files.append(related_path)
        
        return related_files
    
    async def preview(
        self,
        target_path: str,
        options: Optional[SmartRenameOptions] = None
    ) -> SmartRenamePreviewResult:
        """
        预览重命名结果
        
        用途: 分析目标路径下的媒体文件，生成重命名预览
        输入:
            - target_path (str): 目标路径
            - options (SmartRenameOptions): 重命名选项
        输出:
            - SmartRenamePreviewResult: 预览结果
        副作用: 写入数据库记录预览信息
        """
        target_path = validate_path(target_path, "target_path", allow_absolute=True)
        options = options or SmartRenameOptions()
        batch_id = str(uuid.uuid4())
        
        # 扫描文件
        files = await self._scan_media_files(target_path, recursive=options.recursive)
        
        items: List[SmartRenameItem] = []
        parsed_count = 0
        matched_count = 0
        skipped_count = 0
        needs_confirmation_count = 0
        
        # 处理单个文件
        async def process_file(file_path: str) -> SmartRenameItem:
            filename = os.path.basename(file_path)
            
            item = SmartRenameItem(
                original_path=file_path,
                original_name=filename,
                related_files=self._find_related_files(file_path)
            )
            
            # 使用选择的算法解析
            parsed_info, algorithm, parse_confidence = await self._parse_with_algorithm(
                filename,
                options.algorithm,
                force_ai=options.force_ai_parse
            )
            
            item.parsed_info = parsed_info
            item.parse_confidence = parse_confidence
            item.used_algorithm = algorithm
            
            if not parsed_info.get("title"):
                item.status = "skipped"
                item.error_message = "无法解析文件名"
                return item
            
            # 检测媒体类型
            media_type = self.naming_service.detect_media_type(filename)
            item.media_type = media_type.value
            item.season = parsed_info.get("season")
            item.episode = parsed_info.get("episode")
            
            # 匹配 TMDB
            tmdb_match, match_confidence = await self._match_tmdb(
                parsed_info,
                media_type_hint=item.media_type
            )
            
            item.match_confidence = match_confidence
            
            if tmdb_match:
                item.tmdb_id = tmdb_match.get("id")
                item.tmdb_title = tmdb_match.get("title")
                item.tmdb_year = tmdb_match.get("year")
                item.status = "matched"
            else:
                item.status = "parsed"
                item.tmdb_title = parsed_info.get("title")
                item.tmdb_year = parsed_info.get("year")
            
            # 计算总体置信度
            item.overall_confidence = (parse_confidence + match_confidence) / 2
            
            # 生成新文件名
            new_path, new_name = self._generate_new_name(item, options)
            item.new_path = new_path
            item.new_name = new_name
            
            # 判断是否需要确认
            if item.overall_confidence < options.ai_confidence_threshold:
                item.needs_confirmation = True
                item.confirmation_reason = f"置信度较低 ({item.overall_confidence:.0%})"
            elif not tmdb_match:
                item.needs_confirmation = True
                item.confirmation_reason = "未找到 TMDB 匹配"
            
            return item
        
        # 批量处理
        for i in range(0, len(files), options.batch_size):
            batch_files = files[i:i + options.batch_size]
            tasks = [process_file(f) for f in batch_files]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for res in batch_results:
                if isinstance(res, Exception):
                    logger.error(f"Error processing file: {res}")
                    continue
                
                items.append(res)
                
                if res.status == "parsed":
                    parsed_count += 1
                elif res.status == "matched":
                    matched_count += 1
                else:
                    skipped_count += 1
                
                if res.needs_confirmation:
                    needs_confirmation_count += 1
            
            # 避免 TMDB 限流
            await asyncio.sleep(0.1)
        
        # 保存到数据库
        db = SessionLocal()
        try:
            batch = RenameBatch(
                batch_id=batch_id,
                target_path=target_path,
                media_type="auto",
                total_items=len(items),
                status="previewing",
                options={
                    "algorithm": options.algorithm.value,
                    "naming_standard": options.naming_standard.value,
                    "recursive": options.recursive
                }
            )
            db.add(batch)
            
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
                    confidence=item.overall_confidence,
                    status=item.status if not item.needs_confirmation else "needs_confirmation",
                    error_message=item.error_message
                ))
            
            if history_objs:
                db.bulk_save_objects(history_objs)
            db.commit()
        finally:
            db.close()
        
        return SmartRenamePreviewResult(
            batch_id=batch_id,
            target_path=target_path,
            total_items=len(items),
            parsed_items=parsed_count,
            matched_items=matched_count,
            skipped_items=skipped_count,
            needs_confirmation=needs_confirmation_count,
            items=items,
            algorithm_used=options.algorithm.value,
            naming_standard=options.naming_standard.value
        )
    
    async def execute(
        self,
        batch_id: str,
        operations: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        执行重命名操作
        
        用途: 根据预览生成的 batch_id 执行实际的文件重命名
        输入:
            - batch_id (str): 批次 ID
        输出:
            - Dict: 执行结果统计
        副作用: 修改文件系统 (重命名/移动文件)
        """
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
            
            # 获取待处理的项目
            if operations:
                operation_map: Dict[str, str] = {}
                for op in operations:
                    original_path = (op.get("original_path", "") or "").strip()
                    new_name = (op.get("new_name", "") or "").strip()
                    if original_path and new_name:
                        operation_map[original_path] = new_name

                candidate_paths = list(operation_map.keys())
                items = []
                if candidate_paths:
                    items = db.query(RenameHistory).filter(
                        RenameHistory.batch_id == batch_id,
                        RenameHistory.original_path.in_(candidate_paths),
                        RenameHistory.status.in_(["matched", "parsed", "needs_confirmation"])
                    ).all()

                    for item in items:
                        override_name = operation_map.get(item.original_path)
                        if override_name:
                            target_dir = os.path.dirname(item.new_path) if item.new_path else os.path.dirname(item.original_path)
                            item.new_name = override_name
                            item.new_path = os.path.join(target_dir, override_name)
                            if item.status == "needs_confirmation":
                                item.status = "parsed"
                    db.commit()

                total_items_for_execution = len(candidate_paths)
            else:
                items = db.query(RenameHistory).filter(
                    RenameHistory.batch_id == batch_id,
                    RenameHistory.status.in_(["matched", "parsed"])
                ).all()
                total_items_for_execution = batch.total_items
            
            success = 0
            failed = 0
            
            for item in items:
                try:
                    if not item.new_path:
                        item.status = "failed"
                        item.error_message = "new_path is empty"
                        failed += 1
                        db.commit()
                        continue
                    
                    # 创建目标目录
                    target_dir = os.path.dirname(item.new_path)
                    if not os.path.exists(target_dir):
                        os.makedirs(target_dir, exist_ok=True)
                    
                    # 检查目标是否已存在
                    final_path = item.new_path
                    if os.path.exists(final_path):
                        base, ext = os.path.splitext(final_path)
                        counter = 1
                        while os.path.exists(f"{base}_{counter}{ext}"):
                            counter += 1
                        final_path = f"{base}_{counter}{ext}"
                    
                    # 执行移动/重命名
                    shutil.move(item.original_path, final_path)
                    
                    # 移动关联文件
                    original_base = os.path.splitext(item.original_path)[0]
                    new_base = os.path.splitext(final_path)[0]
                    
                    related_extensions = {'.nfo', '.jpg', '.png', '.srt', '.ass', '.sub'}
                    for ext in related_extensions:
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
            batch.skipped_items = max(total_items_for_execution - success - failed, 0)
            batch.status = "completed" if failed == 0 else "completed_with_errors"
            batch.completed_at = datetime.now()
            db.commit()
            
            # 发送通知
            await self.notification_service.send_notification(
                type=NotificationType.TASK_COMPLETED,
                title="智能重命名完成",
                content=f"成功: {success}, 失败: {failed}"
            )

            # 重命名完成后触发Emby刷新（不影响主流程）
            try:
                from app.services.emby_service import get_emby_service
                await get_emby_service().trigger_refresh_on_event("rename")
            except Exception as e:
                logger.warning(f"Trigger Emby refresh after rename failed (ignored): {e}")
            
            return {
                "batch_id": batch_id,
                "total_items": total_items_for_execution,
                "success_items": success,
                "failed_items": failed,
                "skipped_items": batch.skipped_items
            }
            
        finally:
            db.close()
    
    async def rollback(self, batch_id: str) -> Dict[str, Any]:
        """
        回滚重命名操作
        
        用途: 将指定批次的所有成功重命名操作回滚到原始状态
        输入:
            - batch_id (str): 批次 ID
        输出:
            - Dict: 回滚结果统计
        副作用: 修改文件系统 (恢复文件位置)
        """
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
                    if not item.new_path or not os.path.exists(item.new_path):
                        failed += 1
                        continue
                    
                    # 检查原位置
                    original_dir = os.path.dirname(item.original_path)
                    if not os.path.exists(original_dir):
                        os.makedirs(original_dir, exist_ok=True)
                    
                    if os.path.exists(item.original_path):
                        failed += 1
                        continue
                    
                    # 执行回滚
                    shutil.move(item.new_path, item.original_path)
                    
                    # 回滚关联文件
                    new_base = os.path.splitext(item.new_path)[0]
                    original_base = os.path.splitext(item.original_path)[0]
                    
                    related_extensions = {'.nfo', '.jpg', '.png', '.srt', '.ass', '.sub'}
                    for ext in related_extensions:
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
            
            return {
                "batch_id": batch_id,
                "total_items": len(items),
                "success_items": success,
                "failed_items": failed
            }
            
        finally:
            db.close()


def get_smart_rename_service() -> SmartRenameService:
    """
    获取 SmartRenameService 实例
    
    用途: 获取全局 SmartRenameService 实例
    输入: 无
    输出:
        - SmartRenameService: 智能重命名服务实例
    副作用: 无
    """
    return SmartRenameService.get_instance()
