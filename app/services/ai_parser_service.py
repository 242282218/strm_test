from dataclasses import dataclass

from app.core.logging import get_logger
from app.services.unified_ai_service import get_unified_ai_service


logger = get_logger(__name__)


@dataclass
class AIParseResult:
    title: str
    original_title: str | None = None
    year: int | None = None
    season: int | None = None
    episode: int | None = None
    media_type: str = "movie"
    confidence: float = 0.0


class AIParserService:
    """AI parser (兼容层) - 推荐使用 UnifiedAIService"""

    _instance = None

    def __init__(self):
        self._unified_service = get_unified_ai_service()
        logger.info("AIParserService initialized (using UnifiedAIService)")

    @classmethod
    def get_instance(cls):
        if not cls._instance:
            cls._instance = AIParserService()
        return cls._instance

    @property
    def api_key(self) -> str | None:
        return self._unified_service.api_key

    def has_available_provider(self) -> bool:
        return self._unified_service.has_available_provider()

    async def parse_filename(self, filename: str, max_timeout_seconds: int | None = None) -> AIParseResult | None:
        """解析文件名（转发到统一服务）"""
        result = await self._unified_service.parse_filename(filename, max_timeout_seconds=max_timeout_seconds)
        if result is None:
            return None
        return AIParseResult(
            title=result.title,
            original_title=result.original_title,
            year=result.year,
            season=result.season,
            episode=result.episode,
            media_type=result.media_type,
            confidence=result.confidence,
        )


def get_ai_parser_service() -> AIParserService:
    return AIParserService.get_instance()
