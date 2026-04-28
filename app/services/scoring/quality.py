"""
Quality calculator - 质量分计算器

计算视频资源的技术质量得分
"""


class QualityCalculator:
    """质量分计算器"""

    def calculate(self, title: str, tags: set[str]) -> float:
        """
        计算质量分

        Args:
            title: 资源标题
            tags: 标签集合

        Returns:
            质量分 (0-1)
        """
        pts = 0

        # 1. 分辨率评分 (最高25分)
        if "4k" in tags:
            pts += 25
        elif "1080p" in tags:
            pts += 15
        elif "720p" in tags:
            pts += 6

        # 2. 视频格式评分 (最高35分)
        if "bdmv" in tags:
            pts += 35
        elif "remux" in tags:
            pts += 30
        elif "bluray" in tags:
            pts += 24
        elif "webdl" in tags or "webrip" in tags:
            pts += 18

        # 3. HDR/DV评分 (最高20分)
        if "dv" in tags:
            pts += 20
        if "hdr" in tags:
            pts += 10

        # 4. 音频评分 (最高10分)
        if "atmos" in tags:
            pts += 10
        if "dtsx" in tags:
            pts += 8
        if "truehd" in tags:
            pts += 6
        if "dtshd" in tags:
            pts += 5
        if "ddp" in tags:
            pts += 3

        # 5. 编码评分 (最高4分)
        if "x265" in tags:
            pts += 4
        if "x264" in tags:
            pts += 2

        # 6. 字幕评分 (最高6分)
        if "fx_sub" in tags:
            pts += 6
        elif "cn_sub" in tags:
            pts += 3
        if "multi_audio" in tags:
            pts += 4

        # 7. 其他加分 (最高2分)
        if "imax" in tags:
            pts += 2
        if "hfr" in tags:
            pts += 2
        if "collection" in tags:
            pts += 2

        # 检查标题中的高码率
        if "高码率" in title:
            pts += 4

        # 8. 冲突惩罚
        if "4k" in tags and "1080p" in tags:
            pts -= 12

        return max(0.0, min(1.0, pts / 110))
