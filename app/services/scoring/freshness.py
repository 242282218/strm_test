"""
Freshness calculator - 新鲜度计算器

计算资源的新鲜度得分
"""

import math
from datetime import UTC, datetime


class FreshnessCalculator:
    """新鲜度计算器"""

    def calculate(self, pub_date: str | None) -> float:
        """
        计算新鲜度

        Args:
            pub_date: 发布日期字符串 (ISO格式)

        Returns:
            新鲜度 (0-1)
        """
        if not pub_date:
            return 0.5  # 未知时间给中等分

        try:
            # 解析日期
            dt = datetime.fromisoformat(pub_date.replace("Z", "+00:00"))
            now = datetime.now(UTC)

            # 计算天数差
            days = (now - dt).total_seconds() / 86400

            # 指数衰减，60天为半衰期
            return math.exp(-max(0, days) / 60)
        except (ValueError, TypeError, OverflowError):
            return 0.5
