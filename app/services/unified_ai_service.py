"""
统一 AI 服务（OpenAI 兼容）

支持任意 OpenAI 兼容的 API，自动 fallback
"""

import asyncio
import json
from dataclasses import dataclass
from typing import Any

import httpx

from app.config.ai_config import AIProviderConfig
from app.core.http_pool import ClientType, get_http_pool
from app.core.logging import get_logger
from app.services.config_service import get_config_service


logger = get_logger(__name__)


@dataclass
class AIParseResult:
    """AI 解析结果"""

    title: str
    original_title: str | None = None
    year: int | None = None
    season: int | None = None
    episode: int | None = None
    media_type: str = "movie"
    confidence: float = 0.0


def get_unified_ai_providers() -> list[AIProviderConfig]:
    app_config = get_config_service().get_config()
    ai_config = getattr(app_config, "ai", None)
    if ai_config is None:
        return []

    get_enabled_providers = getattr(ai_config, "get_enabled_providers", None)
    if callable(get_enabled_providers):
        return list(get_enabled_providers())

    providers = getattr(ai_config, "providers", None)
    if not isinstance(providers, list):
        return []

    return [
        provider
        for provider in providers
        if getattr(provider, "enabled", True) and bool(getattr(provider, "api_key", ""))
    ]


class UnifiedAIService:
    """统一 AI 服务（OpenAI 兼容）"""

    SYSTEM_PROMPT = """You are a media filename parser.
Return JSON only. Do not wrap in markdown.
Expected fields:
- title (required)
- original_title (optional)
- year (optional integer)
- media_type (movie|tv|anime|unknown)
- season (optional integer)
- episode (optional integer)"""

    _instance = None
    _semaphore = None

    def __init__(self):
        if UnifiedAIService._semaphore is None:
            UnifiedAIService._semaphore = asyncio.Semaphore(5)
        self._pool = None
        self._client: httpx.AsyncClient | None = None
        self._provider_getter = get_unified_ai_providers

    @classmethod
    def get_instance(cls):
        if not cls._instance:
            cls._instance = UnifiedAIService()
        return cls._instance

    async def _get_client(self) -> httpx.AsyncClient:
        """获取 HTTP 客户端"""
        if self._client is None or self._client.is_closed:
            if self._pool is None:
                self._pool = await get_http_pool()
            self._client = await self._pool.get_client(ClientType.AI_PARSER)
        return self._client

    @property
    def api_key(self) -> str | None:
        providers = self._get_providers()
        if not providers:
            return None
        return providers[0].api_key

    def _get_providers(self) -> list[AIProviderConfig]:
        """获取已启用的 providers"""
        try:
            return list(self._provider_getter())
        except Exception as exc:
            logger.warning("Failed to resolve unified AI providers: %s", exc)
            return []

    def has_available_provider(self) -> bool:
        return bool(self._get_providers())

    @staticmethod
    def _resolve_timeout(provider_timeout: int, max_timeout_seconds: int | None) -> int:
        if max_timeout_seconds is None:
            return provider_timeout
        try:
            requested_timeout = int(max_timeout_seconds)
        except (TypeError, ValueError):
            return provider_timeout
        if requested_timeout <= 0:
            return provider_timeout
        return min(provider_timeout, requested_timeout)

    @staticmethod
    def _extract_json_payload(content: str) -> dict[str, Any] | None:
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        cleaned = content.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            if len(lines) >= 3 and lines[0].startswith("```") and lines[-1] == "```":
                cleaned = "\n".join(lines[1:-1]).strip()
                if cleaned.lower().startswith("json"):
                    cleaned = cleaned[4:].lstrip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None

        try:
            return json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError:
            return None

    async def parse_filename(self, filename: str, max_timeout_seconds: int | None = None) -> AIParseResult | None:
        """解析文件名"""
        providers = self._get_providers()
        if not providers:
            logger.warning("No AI providers configured")
            return None

        async with self._semaphore:
            for provider in providers:
                try:
                    result = await self._call_provider(
                        provider,
                        filename,
                        timeout_seconds=self._resolve_timeout(provider.timeout, max_timeout_seconds),
                    )
                    if result:
                        return result
                except Exception as e:
                    logger.warning(f"Provider {provider.name} failed: {e}")
                    continue

        return None

    async def _call_provider(
        self,
        provider: AIProviderConfig,
        filename: str,
        timeout_seconds: int | None = None,
    ) -> AIParseResult | None:
        """调用单个 provider"""
        client = await self._get_client()
        request_timeout = timeout_seconds or provider.timeout

        payload = {
            "model": provider.model,
            "messages": [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": f"Parse this filename: {filename}"},
            ],
            "temperature": 0.1,
        }

        headers = {
            "Authorization": f"Bearer {provider.api_key}",
            "Content-Type": "application/json",
        }

        url = f"{provider.base_url}/chat/completions"

        try:
            response = await client.post(url, json=payload, headers=headers, timeout=request_timeout)
            response.raise_for_status()
            data = response.json()

            content = data["choices"][0]["message"]["content"]
            parsed = self._extract_json_payload(content)
            if not parsed or not parsed.get("title"):
                return None
            media_type = parsed.get("media_type", "unknown")
            if media_type not in {"movie", "tv", "anime", "unknown"}:
                media_type = "unknown"

            return AIParseResult(
                title=parsed.get("title", filename),
                original_title=parsed.get("original_title"),
                year=parsed.get("year"),
                season=parsed.get("season"),
                episode=parsed.get("episode"),
                media_type=media_type,
                confidence=0.8,
            )
        except Exception as e:
            logger.debug(f"Provider {provider.name} call failed: {e}")
            return None


def get_unified_ai_service() -> UnifiedAIService:
    """获取统一 AI 服务实例"""
    return UnifiedAIService.get_instance()
