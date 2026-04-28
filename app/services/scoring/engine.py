"""
Scoring engine - 评分引擎

协调各维度评分计算，生成综合评分
"""

from typing import Any

from .confidence import ConfidenceCalculator
from .freshness import FreshnessCalculator
from .popularity import PopularityCalculator
from .quality import QualityCalculator
from .tags import TagExtractor
from .weights import ScoringWeights


class ScoringEngine:
    """评分引擎"""

    def __init__(self, weights: ScoringWeights | None = None):
        """
        初始化评分引擎

        Args:
            weights: 评分权重配置
        """
        self.weights = weights or ScoringWeights()
        self.confidence_calc = ConfidenceCalculator()
        self.quality_calc = QualityCalculator()
        self.popularity_calc = PopularityCalculator()
        self.freshness_calc = FreshnessCalculator()
        self.tag_extractor = TagExtractor()

    def score(self, query: str, result: dict[str, Any]) -> dict[str, float]:
        """
        计算评分

        Args:
            query: 搜索关键词
            result: 搜索结果字典

        Returns:
            评分详情字典
        """
        title = result.get("title", "")
        pub_date = result.get("pub_date")

        # 提取标签
        tags = self.tag_extractor.extract(title)

        # 计算各维度得分
        confidence = self.confidence_calc.calculate(query, title, tags)
        quality = self.quality_calc.calculate(title, tags)
        popularity = self.popularity_calc.calculate(0)  # pansou无浏览量数据
        freshness = self.freshness_calc.calculate(pub_date)

        # 计算动态权重
        alpha = self._calculate_alpha(confidence)
        pr_gate = self._calculate_pr_gate(confidence)

        # 计算最终评分
        score = (
            alpha * confidence
            + (1 - alpha) * quality
            + pr_gate * (self.weights.popularity * popularity + self.weights.freshness * freshness)
        )

        # 极低置信度直接返回
        if confidence < 0.08:
            score = confidence

        return {
            "score": round(score, 3),
            "confidence": round(confidence, 3),
            "quality": round(quality, 3),
            "popularity": round(popularity, 3),
            "freshness": round(freshness, 3),
            "alpha": round(alpha, 3),
            "pr_gate": pr_gate,
            "tags": list(tags),
        }

    def _calculate_alpha(self, confidence: float) -> float:
        """
        计算动态权重

        Args:
            confidence: 置信度

        Returns:
            动态权重值
        """
        if confidence < 0.5:
            return 0.7
        if confidence < 0.8:
            return 0.55
        return 0.4

    def _calculate_pr_gate(self, confidence: float) -> float:
        """
        计算PR门控

        Args:
            confidence: 置信度

        Returns:
            PR门控值
        """
        if confidence >= 0.6:
            return 1.0
        if confidence >= 0.4:
            return 0.3
        return 0.0
