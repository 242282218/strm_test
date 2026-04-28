"""
Confidence calculator - 置信度计算器

计算搜索结果的置信度得分
"""

import re
import unicodedata


class ConfidenceCalculator:
    """置信度计算器"""

    # 负面关键词列表
    VIDEO_NEG = [
        "解说文案",
        "文案",
        "讲解稿",
        "台词",
        "脚本",
        "宣传文案",
        "攻略",
        "补丁",
        "修改器",
        "安装",
        "破解版",
        "内购",
        "加速器",
        "网游",
        "手游",
        "客户端",
        ".apk",
        ".exe",
        ".torrent",
        "课程",
        "教程",
        "小说",
        "听书",
    ]

    # 正面关键词列表
    VIDEO_POS = [
        "电影",
        "影视",
        "剧集",
        "电视剧",
        "蓝光",
        "原盘",
        "remux",
        "bdmv",
        "webrip",
        "web-dl",
        "1080p",
        "2160p",
        "4k",
        "720p",
        "x264",
        "x265",
        "hevc",
        "hdr",
        "dv",
        "杜比",
        "中字",
        "字幕",
    ]

    def __init__(self):
        self.text_similarity = 0.0
        self.intent_score = 0.0
        self.plausibility_score = 0.0

    def calculate(self, query: str, title: str, tags: set[str]) -> float:
        """
        计算置信度

        Args:
            query: 搜索关键词
            title: 资源标题
            tags: 标签集合

        Returns:
            置信度得分 (0-1)
        """
        # 计算各维度得分
        c_text = self._text_similarity(query, title)
        c_intent = self._intent_score(title, tags)
        c_plaus = self._plausibility_score(title, tags)

        # 保存中间结果
        self.text_similarity = c_text
        self.intent_score = c_intent
        self.plausibility_score = c_plaus

        # 综合置信度公式
        conf = c_text * (0.7 + 0.3 * (0.5 * c_intent + 0.5 * c_plaus))
        conf = max(0.0, min(1.0, conf))

        # 低质量惩罚
        if c_text < 0.25 or c_intent == 0.0:
            conf *= 0.15

        return conf

    def _text_similarity(self, query: str, name: str) -> float:
        """计算文本相似度"""
        # 文本标准化
        qn = self._normalize_text(query)
        nn = self._normalize_text(name)

        # 完全包含检查
        if qn in nn:
            return 1.0

        # Bigram Jaccard相似度
        def bigrams(s):
            return {s[i : i + 2] for i in range(len(s) - 1)}

        qbg, nbg = bigrams(qn), bigrams(nn)
        if not qbg or not nbg:
            return 0.0

        jaccard = len(qbg & nbg) / len(qbg | nbg)

        # Token匹配率
        qtok = re.findall(r"[a-z0-9]+", query.lower())
        ntok = set(re.findall(r"[a-z0-9]+", name.lower()))
        if not qtok:
            token_hit = 0.0
        else:
            token_hit = sum(1 for t in qtok if t in ntok) / len(qtok)

        return max(jaccard, token_hit * 0.9)

    def _normalize_text(self, text: str) -> str:
        """文本标准化"""
        # NFKC标准化 + 小写 + 去空格
        text = unicodedata.normalize("NFKC", text)
        text = text.lower()
        text = re.sub(r"\s+", "", text)
        return text

    def _intent_score(self, name: str, tags: set[str]) -> float:
        """意图评分"""
        name_lower = name.lower()

        # 检查负面关键词
        for neg in self.VIDEO_NEG:
            if neg.lower() in name_lower:
                # ISO原盘例外
                if ".iso" in name_lower and ("bluray" in tags or "原盘" in name):
                    return 0.7
                return 0.0

        # 计算正面评分
        score = 0.0
        for pos in self.VIDEO_POS:
            if pos.lower() in name_lower:
                score += 0.7
                break

        if tags:
            score += 0.2

        return min(1.0, score)

    def _plausibility_score(self, name: str, tags: set[str]) -> float:
        """合理性评分"""
        # 大小与标签矛盾检查
        # 注意：pansou返回的结果没有大小信息，简化处理
        if {"4k", "bdmv", "remux", "bluray"} & tags:
            # 这些类型通常较大，给予较高合理性
            return 0.9

        return 0.7
