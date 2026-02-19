import aiohttp
import asyncio
import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Literal, Optional

from app.services.config_service import ConfigManager
from app.core.logging import get_logger

logger = get_logger(__name__)

ProviderName = Literal["kimi", "glm", "deepseek"]


@dataclass
class AIParseResult:
    title: str
    original_title: Optional[str] = None
    year: Optional[int] = None
    season: Optional[int] = None
    episode: Optional[int] = None
    media_type: str = "movie"  # movie/tv/anime
    confidence: float = 0.0


@dataclass
class ProviderRuntimeConfig:
    provider: ProviderName
    api_key: str
    base_url: str
    model: str
    timeout_seconds: int


class AIParserService:
    """
    AI parser with provider fallback.

    Default order: kimi -> glm -> deepseek
    """

    SYSTEM_PROMPT = """You are a media filename parser.
Return JSON only. Do not wrap in markdown.
If parsing fails, return {"title":"<original filename>","media_type":"unknown"}.
Expected fields:
- title (required)
- original_title (optional)
- year (optional integer)
- media_type (movie|tv|anime|unknown)
- season (optional integer)
- episode (optional integer)
"""

    DEFAULT_PROVIDER_ORDER: tuple[ProviderName, ...] = ("kimi", "glm", "deepseek")
    PROVIDER_TIMEOUT_CAP_SECONDS = 8
    _instance = None
    _semaphore = None

    def __init__(self):
        self._config = ConfigManager()
        if AIParserService._semaphore is None:
            AIParserService._semaphore = asyncio.Semaphore(5)

        self.provider_order = self._resolve_provider_order()
        self.provider_configs = [self._build_provider_config(name) for name in self.provider_order]

        # Compatibility fields used by legacy call sites.
        self.api_key = next((cfg.api_key for cfg in self.provider_configs if cfg.api_key), "")
        primary = self.provider_configs[0] if self.provider_configs else ProviderRuntimeConfig(
            provider="glm",
            api_key="",
            base_url="https://open.bigmodel.cn/api/paas/v4",
            model="glm-4.7-flash",
            timeout_seconds=30,
        )
        self.model = primary.model
        self.base_url = primary.base_url
        self.timeout = primary.timeout_seconds

    @classmethod
    def get_instance(cls):
        if not cls._instance:
            cls._instance = AIParserService()
        return cls._instance

    @staticmethod
    def _first_non_empty(*values: Any, fallback: str = "") -> str:
        for value in values:
            if value is None:
                continue
            text = str(value).strip()
            if text:
                return text
        return fallback

    @staticmethod
    def _coerce_timeout(value: Any, default: int = 30) -> int:
        try:
            parsed = int(value)
            if parsed <= 0:
                return default
            return min(parsed, 120)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _normalize_base_url(base_url: str) -> str:
        return base_url.rstrip("/")

    def _resolve_provider_order(self) -> list[ProviderName]:
        raw = self._config.get("ai.provider_order")
        candidates: list[str] = []
        if isinstance(raw, list):
            candidates = [str(item).strip().lower() for item in raw]
        elif isinstance(raw, str):
            candidates = [part.strip().lower() for part in raw.split(",")]

        if not candidates:
            candidates = list(self.DEFAULT_PROVIDER_ORDER)

        valid: list[ProviderName] = []
        for name in candidates:
            if name in ("kimi", "glm", "deepseek") and name not in valid:
                valid.append(name)  # type: ignore[arg-type]

        # Ensure all defaults are present to keep fallback complete.
        for name in self.DEFAULT_PROVIDER_ORDER:
            if name not in valid:
                valid.append(name)
        return valid

    def _build_provider_config(self, provider: ProviderName) -> ProviderRuntimeConfig:
        if provider == "kimi":
            api_key = self._first_non_empty(
                self._config.get("kimi.api_key"),
                os.getenv("SMART_MEDIA_KIMI_API_KEY"),
                os.getenv("NVIDIA_API_KEY"),
                os.getenv("NVIDIA_API_TOKEN"),
                os.getenv("KIMI_API_KEY"),
                fallback="",
            )
            base_url = self._first_non_empty(
                self._config.get("kimi.base_url"),
                os.getenv("KIMI_BASE_URL"),
                fallback="https://integrate.api.nvidia.com/v1",
            )
            model = self._first_non_empty(
                self._config.get("kimi.model"),
                os.getenv("KIMI_MODEL"),
                fallback="moonshotai/kimi-k2.5",
            )
            timeout = self._coerce_timeout(
                self._first_non_empty(
                    self._config.get("kimi.timeout"),
                    os.getenv("KIMI_TIMEOUT"),
                    fallback="30",
                ),
                default=30,
            )
            return ProviderRuntimeConfig(
                provider=provider,
                api_key=api_key,
                base_url=self._normalize_base_url(base_url),
                model=model,
                timeout_seconds=timeout,
            )

        if provider == "deepseek":
            api_key = self._first_non_empty(
                self._config.get("deepseek.api_key"),
                os.getenv("SMART_MEDIA_DEEPSEEK_API_KEY"),
                os.getenv("DEEPSEEK_API_KEY"),
                fallback="",
            )
            base_url = self._first_non_empty(
                self._config.get("deepseek.base_url"),
                os.getenv("DEEPSEEK_BASE_URL"),
                fallback="https://api.deepseek.com/v1",
            )
            model = self._first_non_empty(
                self._config.get("deepseek.model"),
                os.getenv("DEEPSEEK_MODEL"),
                fallback="deepseek-chat",
            )
            timeout = self._coerce_timeout(
                self._first_non_empty(
                    self._config.get("deepseek.timeout"),
                    os.getenv("DEEPSEEK_TIMEOUT"),
                    fallback="30",
                ),
                default=30,
            )
            return ProviderRuntimeConfig(
                provider=provider,
                api_key=api_key,
                base_url=self._normalize_base_url(base_url),
                model=model,
                timeout_seconds=timeout,
            )

        api_key = self._first_non_empty(
            self._config.get("glm.api_key"),
            self._config.get("zhipu.api_key"),
            os.getenv("SMART_MEDIA_GLM_API_KEY"),
            os.getenv("GLM_API_KEY"),
            os.getenv("SMART_MEDIA_ZHIPU_API_KEY"),
            os.getenv("ZHIPUAI_API_KEY"),
            self._config.get("api_keys.ai_api_key"),
            fallback="",
        )
        base_url = self._first_non_empty(
            self._config.get("glm.base_url"),
            self._config.get("ai.base_url"),
            os.getenv("GLM_BASE_URL"),
            fallback="https://open.bigmodel.cn/api/paas/v4",
        )
        model = self._first_non_empty(
            self._config.get("glm.model"),
            self._config.get("ai.model"),
            os.getenv("GLM_MODEL"),
            fallback="glm-4.7-flash",
        )
        timeout = self._coerce_timeout(
            self._first_non_empty(
                self._config.get("glm.timeout"),
                self._config.get("ai.timeout"),
                os.getenv("GLM_TIMEOUT"),
                fallback="30",
            ),
            default=30,
        )
        return ProviderRuntimeConfig(
            provider=provider,
            api_key=api_key,
            base_url=self._normalize_base_url(base_url),
            model=model,
            timeout_seconds=timeout,
        )

    def has_available_provider(self) -> bool:
        return any(cfg.api_key for cfg in self.provider_configs)

    async def _post_request(self, url: str, headers: dict, payload: dict, timeout_seconds: int) -> dict:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=timeout_seconds),
            ) as resp:
                if resp.status in {408, 429} or resp.status >= 500:
                    text = await resp.text()
                    logger.warning(f"AI API transient status={resp.status}, body={text[:300]}")
                    return {}
                if resp.status != 200:
                    text = await resp.text()
                    logger.warning(f"AI API error status={resp.status}, body={text[:300]}")
                    return {}
                return await resp.json()

    def _extract_json(self, content: str) -> Optional[Dict[str, Any]]:
        import re

        cleaned = re.sub(r"```(?:json)?\\s*", "", content)
        cleaned = cleaned.replace("```", "").strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            json_str = match.group()
            try:
                return json.loads(json_str)
            except json.JSONDecodeError as exc:
                logger.warning("Extracted JSON is invalid: %s", exc)
        return None

    def _validate_result(self, result: Dict[str, Any]) -> bool:
        if not result or not isinstance(result, dict):
            return False
        if not result.get("title"):
            return False
        if result.get("media_type") not in ["movie", "tv", "anime", "unknown"]:
            result["media_type"] = "unknown"
        return True

    async def _parse_with_provider(
        self,
        filename: str,
        cfg: ProviderRuntimeConfig,
        timeout_seconds: Optional[int] = None,
    ) -> Optional[AIParseResult]:
        effective_timeout = self._coerce_timeout(
            timeout_seconds if timeout_seconds is not None else cfg.timeout_seconds,
            default=self.PROVIDER_TIMEOUT_CAP_SECONDS,
        )
        effective_timeout = min(effective_timeout, self.PROVIDER_TIMEOUT_CAP_SECONDS)
        url = f"{cfg.base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {cfg.api_key}",
        }
        payload = {
            "model": cfg.model,
            "messages": [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": f"Parse this filename: {filename}"},
            ],
            "max_tokens": 512,
            "temperature": 0.1,
            "stream": False,
        }

        data = await self._post_request(url, headers, payload, effective_timeout)
        if not data or "choices" not in data or not data["choices"]:
            return None

        content = data["choices"][0]["message"]["content"]
        result = self._extract_json(content)
        if not self._validate_result(result):
            logger.warning(
                f"AI response validation failed for provider={cfg.provider} filename={filename} content={content[:200]}"
            )
            return None

        return AIParseResult(
            title=result.get("title", ""),
            original_title=result.get("original_title"),
            year=result.get("year"),
            season=result.get("season"),
            episode=result.get("episode"),
            media_type=result.get("media_type", "movie"),
            confidence=0.95,
        )

    async def parse_filename(
        self,
        filename: str,
        max_timeout_seconds: Optional[int] = None,
    ) -> Optional[AIParseResult]:
        if not self.has_available_provider():
            logger.warning("No AI provider API key configured")
            return None

        bounded_timeout = None
        if max_timeout_seconds is not None:
            bounded_timeout = self._coerce_timeout(max_timeout_seconds, default=self.PROVIDER_TIMEOUT_CAP_SECONDS)
            bounded_timeout = min(bounded_timeout, self.PROVIDER_TIMEOUT_CAP_SECONDS)

        async with self._semaphore:
            for cfg in self.provider_configs:
                if not cfg.api_key:
                    continue
                try:
                    provider_timeout = min(cfg.timeout_seconds, self.PROVIDER_TIMEOUT_CAP_SECONDS)
                    if bounded_timeout is not None:
                        provider_timeout = min(provider_timeout, bounded_timeout)
                    parsed = await self._parse_with_provider(filename, cfg, timeout_seconds=provider_timeout)
                    if parsed:
                        return parsed
                except Exception as exc:
                    logger.warning(f"AI parse failed on provider={cfg.provider} filename={filename} error={exc}")
                    continue

        return None


def get_ai_parser_service() -> AIParserService:
    return AIParserService.get_instance()
