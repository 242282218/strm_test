"""
Tags extractor - 标签提取器

从资源名称中提取视频质量标签
"""

import re


class TagExtractor:
    """标签提取器"""

    # 标签匹配规则
    TAG_PATTERNS = {
        # 分辨率
        "4k": r"2160p|4k|uhd|ultra\s*hd",
        "1080p": r"1080p|1920x1080",
        "720p": r"720p|1280x720",
        # 视频格式
        "bdmv": r"bdmv|blu-ray\s*iso|bd\s*iso",
        "remux": r"remux|remuxed",
        "bluray": r"bluray|blu-ray|蓝光|原盘",
        "webdl": r"web-dl|webdl",
        "webrip": r"webrip|web-rip",
        # 动态范围
        "dv": r"dolby\s*vision|杜比视界|dv",
        "hdr": r"hdr|hdr10|hdr10\+",
        # 编码
        "x265": r"x265|h\.?265|hevc",
        "x264": r"x264|h\.?264|avc",
        # 音频
        "atmos": r"atmos|杜比全景声|dolby\s*atmos",
        "dtsx": r"dts-?x|dtsx",
        "truehd": r"true-?hd|truehd",
        "dtshd": r"dts-?hd|dtshd|dts-hd",
        "ddp": r"ddp|eac3|e-ac-?3|dolby\s*digital\s*plus",
        # 字幕
        "fx_sub": r"特效字幕|特效|fx",
        "cn_sub": r"中字|中文字幕|简体|繁体",
        "multi_audio": r"国英|双语|双音|多音轨|multi",
        # 其他
        "imax": r"imax",
        "hfr": r"60fps|120fps|高帧率|hfr",
        "collection": r"合集|系列|全集",
    }

    def extract(self, name: str) -> set[str]:
        """
        从资源名称中提取标签

        Args:
            name: 资源名称

        Returns:
            标签集合
        """
        tags = set()
        name_lower = name.lower()

        for tag, pattern in self.TAG_PATTERNS.items():
            if re.search(pattern, name_lower, re.IGNORECASE):
                tags.add(tag)

        return tags
