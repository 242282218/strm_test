import re
import asyncio
import json
from typing import Optional, Dict, Any
from functools import lru_cache

class MediaParser:
    """媒体文件名解析器"""
    
    # 媒体文件名解析正则表达式
    PATTERNS = [
        # === 电视剧 / 动漫模式 (优先识别季集) ===
        # 标准 S01E02 格式
        r'^(?P<title>.+?)[\.\s\-\(]*[Ss](?P<season>\d+)[Ee](?P<episode>\d+)',
        
        # 带有 "第x季" 的格式 (如: 咒术回战.第2季.01话.mp4)
        r'^(?P<title>.+?)[\.\s\-]第(?P<season>\d+)季[\.\s\-]?(?P<episode>\d+)[集话]',
        
        # 常见 EP01 / E01 格式
        r'^(?P<title>.+?)[\.\s\-\(]*[Ee][Pp]?(?P<episode>\d+)',
        
        # 中文 "第01集" / "第01话" 格式
        r'^(?P<title>.+?)[\.\s\-]?第(?P<episode>\d+)[集话]',
        
        # 动漫常用 " - 01" / " 01 " 格式
        r'^(?P<title>.+?)[\s\-_]+(?P<episode>\d{2,3})(?=\s|\[|\.|$)',
        
        # 多集格式 (如: 剧名.EP01.E02 或 剧名.S01E01E02)
        r'^(?P<title>.+?)[\.\s\-\(]*[Ss](?P<season>\d+)[Ee](?P<episode>\d+)[Ee]\d+',
        r'^(?P<title>.+?)[\.\s\-\(]*[Ee][Pp]?(?P<episode>\d+)[Ee][Pp]?\d+',
        
        # === 字幕组格式 ===
        # [字幕组] 标题 [属性]
        r'^\[(?P<group>[^\]]+)\]\s*(?P<title>[^\[\]]+?)(?:\s*\[|\s*\-|\s+\d{2,3}|\.|$)',
        
        # === 电影模式 ===
        # [标题][年份][分辨率]
        r'^\[(?P<title>[^\]]+)\]\s*\[?(?P<year>\d{4})\]?\s*\[?(?P<resolution>\d+[pP])\]?',
        
        # 标题.年份.分辨率 (使用更严谨的标题边界)
        r'^(?P<title>.+?)[\.\s\(\[](?P<year>\d{4})[\.\s\)\]]',
        
        # 标题 (年份)
        r'^(?P<title>.+?)\s*[\(\[](?P<year>\d{4})[\)\]]',
    ]

    @classmethod
    def _post_process_title(cls, title: str) -> str:
        """
        清理和标准化标题
        
        用途: 移除标题中的多余字符和常见后缀，生成干净的标题
        输入:
            - title (str): 原始标题
        输出:
            - str: 清理后的标题
        副作用: 无
        """
        if not title:
            return ""
            
        # 1. 如果标题以 [..] 开头且后面还有内容，移除开头的 [..] (通常是字幕组名)
        if title.startswith('[') and ']' in title:
            # 只有当 ] 后面还有非空白内容时才移除
            parts = title.split(']', 1)
            if len(parts) > 1 and parts[1].strip():
                title = parts[1]

        # 2. 替换分隔符为单个空格
        title = title.replace('.', ' ').replace('_', ' ').strip()
        
        # 3. 移除常见的视频属性后缀及其后的所有内容
        suffixes = [
            'BluRay', 'WEB-DL', 'HDTV', '1080p', '720p', '2160p', '4K', 
            'x264', 'x265', 'h264', 'h265', 'HEVC', 'AVC', 'AAC', 'DDP',
            'S\d+E\d+', 'EP?\d+', '第\d+[集话]',
            'REMUX', 'UHD', 'BD', 'DVD', 'CD1', 'CD2',
            'PROPER', 'REPACK', 'LIMITED', 'INTERNAL',
            'DTS', 'DTS-HD', 'TrueHD', 'Atmos',
            'Hi10P', '8bit', '10bit'
        ]
        for suffix in suffixes:
            title = re.sub(rf'\s+{suffix}.*$', '', title, flags=re.IGNORECASE)
            
        # 4. 移除年份 (4位数字，通常在末尾)
        title = re.sub(r'\s+(19|20)\d{2}.*$', '', title)
        
        # 5. 移除括号内容 (如果括号在末尾)
        title = re.sub(r'[\(\[].*?[\)\]]\s*$', '', title)
        
        # 6. 再次清理空白
        title = ' '.join(title.split())
        
        return title.strip()

    @classmethod
    def parse(cls, filename: str) -> Dict[str, Any]:
        """
        使用正则解析文件名 (支持缓存)
        """
        # 使用静态内部方法进行带缓存的解析
        # 返回副本以防止外部修改影响缓存结果
        return cls._parse_internal(filename).copy()

    @staticmethod
    @lru_cache(maxsize=2000)
    def _parse_internal(filename: str) -> Dict[str, Any]:
        """
        实际的解析逻辑，带 lru_cache 缓存
        """
        info = {
            "title": filename, 
            "original_title": filename,
            "year": None, 
            "season": None, 
            "episode": None,
            "resolution": None,
            "ai_parsed": False,
            "source": "regex"
        }
        
        # Remove extension
        if '.' in filename:
            name_without_ext = filename.rsplit('.', 1)[0]
        else:
            name_without_ext = filename
            
        # 遍历模式
        for pattern in MediaParser.PATTERNS:
            match = re.match(pattern, name_without_ext)
            if match:
                data = match.groupdict()
                
                # 提取并处理标题
                raw_title = data.get("title")
                if raw_title:
                    info["title"] = MediaParser._post_process_title(raw_title)
                    info["original_title"] = info["title"]
                    
                # 提取季/集/年
                if "year" in data and data["year"]:
                    info["year"] = int(data["year"])
                if "season" in data and data["season"]:
                    info["season"] = int(data["season"])
                if "episode" in data and data["episode"]:
                    info["episode"] = int(data["episode"])
                if "resolution" in data and data["resolution"]:
                    info["resolution"] = data["resolution"]
                    
                # 如果标题有变化，认为匹配成功
                if info["title"] != filename:
                    return info
                
        # Fallback: 如果没匹配到，尝试在全文搜年份
        year_match = re.search(r'(19|20)\d{2}', name_without_ext)
        if year_match:
            info["year"] = int(year_match.group(0))
            
        return info


    @classmethod
    async def parse_with_ai(cls, filename: str, force: bool = False) -> Dict[str, Any]:
        """
        带AI增强的解析 (异步，较慢但准确)
        :param force: 是否强制使用AI
        """
        # 1. 先进行正则解析
        info = cls.parse(filename)
        
        # 2. 判断是否需要 AI 介入
        # 如果强制开启，或者正则解析结果不理想 (无明确年份或集数)
        needs_ai = force or (not info.get("year") and info.get("episode") is None)
        
        if not needs_ai:
            return info
            
        # 3. 调用 AI 解析
        from app.services.ai_parser_service import get_ai_parser_service
        ai_service = get_ai_parser_service()

        if not ai_service.has_available_provider():
            return info
            
        ai_result = await ai_service.parse_filename(filename)
        
        if ai_result:
            # 合并结果 (优先使用 AI 结果)
            info["title"] = ai_result.title
            if ai_result.original_title:
                info["original_title"] = ai_result.original_title
            if ai_result.year:
                info["year"] = ai_result.year
            if ai_result.season is not None:
                info["season"] = ai_result.season
            if ai_result.episode is not None:
                info["episode"] = ai_result.episode
                
            info["ai_parsed"] = True
            info["source"] = "ai"
            info["confidence"] = ai_result.confidence
            
        return info

