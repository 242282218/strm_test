"""
Emby 命名规范服务

提供符合 Emby 媒体服务器命名标准的重命名功能:
- 电影命名: Movie Name (Year).ext
- 剧集命名: Show Name (Year) - S##E##.ext
- Specials/OVA: Season 0/S00E##
- 多版本支持: Movie Name (Year) - Version.ext
- 字幕命名: Movie Name (Year).lang.srt

参考文档:
- emby命名研究1.txt
- emby命名研究2.txt
- https://emby.media/support/articles/Movie-Naming.html
- https://emby.media/support/articles/TV-Naming.html
"""

import re
import os
from typing import Optional, Dict, Any, Tuple, List
from dataclasses import dataclass
from enum import Enum
from app.core.logging import get_logger

logger = get_logger(__name__)


class MediaType(Enum):
    """媒体类型"""
    MOVIE = "movie"
    TV_SHOW = "tv"
    ANIME = "anime"
    UNKNOWN = "unknown"


class NamingPattern(Enum):
    """命名模式"""
    STANDARD = "standard"           # 标准模式
    WITH_QUALITY = "with_quality"   # 包含质量信息
    WITH_SOURCE = "with_source"     # 包含来源信息
    WITH_CODEC = "with_codec"       # 包含编码信息
    MINIMAL = "minimal"             # 最小模式


@dataclass
class NamingConfig:
    """命名配置"""
    # 电影模板
    movie_template: str = "{title} ({year})"
    movie_folder_template: str = "{title} ({year})"
    
    # 剧集模板
    tv_show_folder_template: str = "{title} ({year})"
    tv_season_folder_template: str = "Season {season:02d}"
    tv_episode_template: str = "{title} - S{season:02d}E{episode:02d}"
    tv_episode_with_title_template: str = "{title} - S{season:02d}E{episode:02d} - {episode_title}"
    
    # Specials/OVA 模板
    specials_folder: str = "Season 00"  # 或 "Specials"
    specials_episode_template: str = "{title} - S00E{episode:02d}"
    
    # 多版本分隔符
    version_separator: str = " - "
    
    # 质量信息 (可选)
    include_quality: bool = False
    include_source: bool = False
    include_codec: bool = False
    include_release_group: bool = False
    
    # 字符清理
    sanitize_filenames: bool = True
    
    # TMDB ID 嵌入
    include_tmdb_id: bool = False
    tmdb_id_format: str = "[tmdbid={id}]"  # 或 {tmdb=xxxx}


class EmbyNamingService:
    """
    Emby 命名规范服务
    
    用途: 生成符合 Emby 媒体服务器命名标准的文件名和文件夹结构
    输入: 媒体信息字典 (包含 title, year, season, episode 等)
    输出: 标准化的文件名和文件夹路径
    副作用: 无 (纯计算服务，不操作文件系统)
    """
    
    # Windows 非法字符
    ILLEGAL_CHARS = r'[<>:"/\\|?*]'
    
    # 视频扩展名
    VIDEO_EXTENSIONS = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.ts', '.m2ts'}
    
    # 字幕扩展名
    SUBTITLE_EXTENSIONS = {'.srt', '.ass', '.sub', '.idx', '.sup', '.vtt'}
    
    # 质量标识映射
    QUALITY_PATTERNS = {
        '2160p': '4K',
        '1080p': '1080p',
        '720p': '720p',
        '480p': '480p',
        '4K': '4K',
        'UHD': '4K',
        'HD': '1080p'
    }
    
    # 来源标识
    SOURCE_PATTERNS = {
        'blu-ray': 'BluRay',
        'bluray': 'BluRay',
        'web-dl': 'WEB-DL',
        'webdl': 'WEB-DL',
        'webrip': 'WEBRip',
        'hdtv': 'HDTV',
        'dvd': 'DVD',
        'remux': 'Remux'
    }
    
    def __init__(self, config: Optional[NamingConfig] = None):
        """
        初始化命名服务
        
        用途: 创建 EmbyNamingService 实例
        输入:
            - config (NamingConfig): 命名配置，使用默认配置如果为 None
        输出: 无
        副作用: 无
        """
        self.config = config or NamingConfig()
    
    def generate_movie_name(
        self,
        title: str,
        year: Optional[int] = None,
        extension: str = ".mp4",
        tmdb_id: Optional[int] = None,
        quality: Optional[str] = None,
        source: Optional[str] = None,
        codec: Optional[str] = None,
        edition: Optional[str] = None
    ) -> Tuple[str, str]:
        """
        生成电影文件名和文件夹名
        
        用途: 根据电影信息生成符合 Emby 规范的文件名和文件夹名
        输入:
            - title (str): 电影标题
            - year (int): 年份
            - extension (str): 文件扩展名
            - tmdb_id (int): TMDB ID (可选)
            - quality (str): 质量 (如 1080p, 4K)
            - source (str): 来源 (如 BluRay, WEB-DL)
            - codec (str): 编码 (如 x264, x265)
            - edition (str): 版本 (如 Director's Cut, Extended)
        输出:
            - Tuple[str, str]: (文件夹名, 文件名)
        副作用: 无
        """
        # 清理标题
        safe_title = self._sanitize_filename(title)
        
        # 构建基础文件名
        if year:
            base_name = f"{safe_title} ({year})"
        else:
            base_name = safe_title
        
        # 添加 TMDB ID (如果启用)
        if self.config.include_tmdb_id and tmdb_id:
            tmdb_tag = self.config.tmdb_id_format.format(id=tmdb_id)
            folder_name = f"{base_name} {tmdb_tag}"
        else:
            folder_name = base_name
        
        # 构建文件名
        file_parts = [base_name]
        
        # 添加版本信息 (如 Director's Cut)
        if edition:
            file_parts.append(edition)
        
        # 添加质量信息
        if self.config.include_quality and quality:
            file_parts.append(quality)
        
        # 添加来源信息
        if self.config.include_source and source:
            file_parts.append(source)
        
        # 添加编码信息
        if self.config.include_codec and codec:
            file_parts.append(codec)
        
        # 组合文件名
        if len(file_parts) > 1:
            file_name = self.config.version_separator.join(file_parts) + extension
        else:
            file_name = base_name + extension
        
        return folder_name, file_name
    
    def generate_tv_show_name(
        self,
        title: str,
        year: Optional[int] = None,
        season: Optional[int] = None,
        episode: Optional[int] = None,
        episode_title: Optional[str] = None,
        extension: str = ".mp4",
        is_special: bool = False
    ) -> Tuple[str, Optional[str], str]:
        """
        生成剧集文件名和文件夹结构
        
        用途: 根据剧集信息生成符合 Emby 规范的文件夹结构和文件名
        输入:
            - title (str): 剧集标题
            - year (int): 年份
            - season (int): 季数
            - episode (int): 集数
            - episode_title (str): 集标题
            - extension (str): 文件扩展名
            - is_special (bool): 是否为特别篇/OVA
        输出:
            - Tuple[str, Optional[str], str]: (剧集文件夹名, 季文件夹名, 文件名)
        副作用: 无
        """
        # 清理标题
        safe_title = self._sanitize_filename(title)
        
        # 剧集文件夹名
        if year:
            show_folder = f"{safe_title} ({year})"
        else:
            show_folder = safe_title
        
        # 季文件夹和文件名
        if is_special:
            # Specials/OVA 使用 Season 00
            season_folder = self.config.specials_folder
            if episode:
                file_name = self.config.specials_episode_template.format(
                    title=safe_title,
                    episode=episode
                ) + extension
            else:
                file_name = f"{safe_title} - Special" + extension
        else:
            if season is not None:
                season_folder = self.config.tv_season_folder_template.format(season=season)
                
                if episode is not None:
                    if episode_title and self.config.tv_episode_with_title_template:
                        file_name = self.config.tv_episode_with_title_template.format(
                            title=safe_title,
                            season=season,
                            episode=episode,
                            episode_title=self._sanitize_filename(episode_title)
                        ) + extension
                    else:
                        file_name = self.config.tv_episode_template.format(
                            title=safe_title,
                            season=season,
                            episode=episode
                        ) + extension
                else:
                    file_name = f"{safe_title} - S{season:02d}" + extension
            else:
                season_folder = None
                file_name = f"{safe_title}{extension}"
        
        return show_folder, season_folder, file_name
    
    def generate_subtitle_name(
        self,
        video_name: str,
        language: str,
        is_forced: bool = False,
        is_default: bool = False,
        is_sdh: bool = False
    ) -> str:
        """
        生成字幕文件名
        
        用途: 根据视频文件名生成符合 Emby 规范的字幕文件名
        输入:
            - video_name (str): 视频文件名 (不含扩展名)
            - language (str): 语言代码 (如 zh, en, ja)
            - is_forced (bool): 是否为强制字幕
            - is_default (bool): 是否为默认字幕
            - is_sdh (bool): 是否为听障辅助字幕
        输出:
            - str: 字幕文件名
        副作用: 无
        """
        parts = [video_name, language]
        
        if is_forced:
            parts.append("forced")
        elif is_sdh:
            parts.append("sdh")
        
        if is_default:
            parts.append("default")
        
        return ".".join(parts) + ".srt"
    
    def parse_quality(self, filename: str) -> Optional[str]:
        """
        从文件名解析质量信息
        
        用途: 从文件名中提取分辨率/质量信息
        输入:
            - filename (str): 文件名
        输出:
            - Optional[str]: 质量标识 (如 1080p, 4K) 或 None
        副作用: 无
        """
        filename_lower = filename.lower()
        
        for pattern, quality in self.QUALITY_PATTERNS.items():
            if pattern.lower() in filename_lower:
                return quality
        
        return None
    
    def parse_source(self, filename: str) -> Optional[str]:
        """
        从文件名解析来源信息
        
        用途: 从文件名中提取媒体来源信息
        输入:
            - filename (str): 文件名
        输出:
            - Optional[str]: 来源标识 (如 BluRay, WEB-DL) 或 None
        副作用: 无
        """
        filename_lower = filename.lower()
        
        for pattern, source in self.SOURCE_PATTERNS.items():
            if pattern.lower() in filename_lower:
                return source
        
        return None
    
    def parse_release_group(self, filename: str) -> Optional[str]:
        """
        从文件名解析发布组信息
        
        用途: 从文件名中提取发布组信息
        输入:
            - filename (str): 文件名
        输出:
            - Optional[str]: 发布组名称 或 None
        副作用: 无
        """
        # 匹配 -[GROUP] 或 [GROUP] 格式
        patterns = [
            r'\-([^\-\[\]]+)$',  # 结尾的 -GROUP
            r'\[([^\]]+)\]',     # [GROUP]
        ]
        
        for pattern in patterns:
            match = re.search(pattern, filename)
            if match:
                group = match.group(1).strip()
                # 过滤掉常见的非发布组标识
                if group.lower() not in {'mp4', 'mkv', 'avi', 'x264', 'x265', 'h264', 'h265'}:
                    return group
        
        return None
    
    def _sanitize_filename(self, filename: str) -> str:
        """
        清理文件名中的非法字符
        
        用途: 移除或替换文件名中的非法字符，确保跨平台兼容
        输入:
            - filename (str): 原始文件名
        输出:
            - str: 清理后的文件名
        副作用: 无
        """
        if not self.config.sanitize_filenames:
            return filename
        
        # 替换非法字符为下划线
        sanitized = re.sub(self.ILLEGAL_CHARS, '_', filename)
        
        # 移除首尾空格和点
        sanitized = sanitized.strip(' .')
        
        # 限制长度 (Windows 最大 255 字符)
        if len(sanitized) > 200:
            sanitized = sanitized[:200].strip(' .')
        
        return sanitized or "Unknown"
    
    def detect_media_type(self, filename: str) -> MediaType:
        """
        检测媒体类型
        
        用途: 根据文件名特征判断是电影还是剧集
        输入:
            - filename (str): 文件名
        输出:
            - MediaType: 媒体类型枚举
        副作用: 无
        """
        filename_lower = filename.lower()
        
        # 检测剧集模式
        tv_patterns = [
            r'[Ss]\d{1,2}[Ee]\d{1,2}',           # S01E01
            r'\d{1,2}[Xx]\d{1,2}',                # 1x01
            r'[第]\d{1,2}[季]',                   # 第1季
            r'[第]\d{1,3}[集]',                   # 第1集
            r'[Ss]eason[\s.]?\d{1,2}',            # Season 1
            r'[Ee]pisode[\s.]?\d{1,3}',           # Episode 1
        ]
        
        for pattern in tv_patterns:
            if re.search(pattern, filename_lower):
                # 检测是否为动漫
                anime_keywords = ['anime', 'ova', 'sp', 'special', 'animation']
                if any(kw in filename_lower for kw in anime_keywords):
                    return MediaType.ANIME
                return MediaType.TV_SHOW
        
        # 检测动漫关键词
        anime_keywords = ['ova', 'special', 'sp']
        if any(kw in filename_lower for kw in anime_keywords):
            return MediaType.ANIME
        
        return MediaType.MOVIE
    
    def validate_emby_naming(self, filename: str) -> Dict[str, Any]:
        """
        验证文件名是否符合 Emby 命名规范
        
        用途: 检查文件名是否符合 Emby 标准命名规范
        输入:
            - filename (str): 文件名
        输出:
            - Dict[str, Any]: 验证结果，包含 is_valid 和 suggestions
        副作用: 无
        """
        result = {
            "is_valid": True,
            "suggestions": [],
            "warnings": []
        }
        
        # 检查年份格式
        year_match = re.search(r'\((\d{4})\)', filename)
        if not year_match:
            result["warnings"].append("建议包含年份信息，格式: Movie Name (2023).ext")
        
        # 检查剧集格式
        if re.search(r'[Ss]\d{1,2}[Ee]\d{1,2}', filename):
            # 是剧集格式
            if not re.search(r'\s-\sS\d{2}E\d{2}', filename):
                result["suggestions"].append("建议使用标准剧集格式: Show Name - S01E01.ext")
        
        # 检查非法字符
        if re.search(self.ILLEGAL_CHARS, filename):
            result["is_valid"] = False
            result["suggestions"].append("文件名包含非法字符，建议清理")
        
        # 检查扩展名
        ext = os.path.splitext(filename)[1].lower()
        if ext not in self.VIDEO_EXTENSIONS and ext not in self.SUBTITLE_EXTENSIONS:
            result["warnings"].append(f"不常见的文件扩展名: {ext}")
        
        return result


# 全局服务实例
_naming_service: Optional[EmbyNamingService] = None


def get_emby_naming_service(config: Optional[NamingConfig] = None) -> EmbyNamingService:
    """
    获取 EmbyNamingService 实例 (单例模式)
    
    用途: 获取全局 EmbyNamingService 实例
    输入:
        - config (NamingConfig): 可选的配置，仅在首次创建时使用
    输出:
        - EmbyNamingService: 命名服务实例
    副作用: 无
    """
    global _naming_service
    if _naming_service is None:
        _naming_service = EmbyNamingService(config)
    return _naming_service
