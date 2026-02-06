"""
AI connectivity test service for smart rename flows.

Tests provider connectivity for:
- kimi (NVIDIA OpenAI-compatible endpoint)
- deepseek
- glm (Zhipu)
"""

from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional, Sequence

import aiohttp

from app.core.config_manager import ConfigManager
from app.core.logging import get_logger

logger = get_logger(__name__)

ProviderName = Literal["kimi", "deepseek", "glm"]


@dataclass
class ProviderRuntimeConfig:
    provider: ProviderName
    api_key: str
    base_url: str
    model: str
    timeout_seconds: int


class AIConnectivityService:
    _instance: Optional["AIConnectivityService"] = None

    def __init__(self):
        self._config = ConfigManager()

    @classmethod
    def get_instance(cls) -> "AIConnectivityService":
        if cls._instance is None:
            cls._instance = AIConnectivityService()
        return cls._instance

    @staticmethod
    def _first_non_empty(values: Sequence[Any], fallback: str = "") -> str:
        for value in values:
            if value is None:
                continue
            text = str(value).strip()
            if text:
                return text
        return fallback

    @staticmethod
    def _normalize_base_url(base_url: str) -> str:
        return base_url.rstrip("/")

    @staticmethod
    def _coerce_timeout(value: Any, default: int = 8) -> int:
        try:
            parsed = int(value)
            if parsed <= 0:
                return default
            return min(parsed, 60)
        except (TypeError, ValueError):
            return default

    def _get_provider_config(self, provider: ProviderName) -> ProviderRuntimeConfig:
        if provider == "kimi":
            api_key = self._first_non_empty(
                [
                    self._config.get("kimi.api_key"),
                    os.getenv("SMART_MEDIA_KIMI_API_KEY"),
                    os.getenv("NVIDIA_API_KEY"),
                    os.getenv("NVIDIA_API_TOKEN"),
                    os.getenv("KIMI_API_KEY"),
                ]
            )
            base_url = self._first_non_empty(
                [
                    self._config.get("kimi.base_url"),
                    os.getenv("KIMI_BASE_URL"),
                    "https://integrate.api.nvidia.com/v1",
                ]
            )
            model = self._first_non_empty(
                [
                    self._config.get("kimi.model"),
                    os.getenv("KIMI_MODEL"),
                    "moonshotai/kimi-k2.5",
                ]
            )
            timeout = self._coerce_timeout(
                self._first_non_empty(
                    [
                        self._config.get("kimi.timeout"),
                        os.getenv("KIMI_TIMEOUT"),
                        8,
                    ],
                    fallback="8",
                )
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
                [
                    self._config.get("deepseek.api_key"),
                    os.getenv("SMART_MEDIA_DEEPSEEK_API_KEY"),
                    os.getenv("DEEPSEEK_API_KEY"),
                ]
            )
            base_url = self._first_non_empty(
                [
                    self._config.get("deepseek.base_url"),
                    os.getenv("DEEPSEEK_BASE_URL"),
                    "https://api.deepseek.com/v1",
                ]
            )
            model = self._first_non_empty(
                [
                    self._config.get("deepseek.model"),
                    os.getenv("DEEPSEEK_MODEL"),
                    "deepseek-chat",
                ]
            )
            timeout = self._coerce_timeout(
                self._first_non_empty(
                    [
                        self._config.get("deepseek.timeout"),
                        os.getenv("DEEPSEEK_TIMEOUT"),
                        8,
                    ],
                    fallback="8",
                )
            )
            return ProviderRuntimeConfig(
                provider=provider,
                api_key=api_key,
                base_url=self._normalize_base_url(base_url),
                model=model,
                timeout_seconds=timeout,
            )

        api_key = self._first_non_empty(
            [
                self._config.get("glm.api_key"),
                self._config.get("zhipu.api_key"),
                os.getenv("SMART_MEDIA_GLM_API_KEY"),
                os.getenv("GLM_API_KEY"),
                os.getenv("SMART_MEDIA_ZHIPU_API_KEY"),
                os.getenv("ZHIPUAI_API_KEY"),
                self._config.get("api_keys.ai_api_key"),
            ]
        )
        base_url = self._first_non_empty(
            [
                self._config.get("glm.base_url"),
                self._config.get("ai.base_url"),
                os.getenv("GLM_BASE_URL"),
                "https://open.bigmodel.cn/api/paas/v4",
            ]
        )
        model = self._first_non_empty(
            [
                self._config.get("glm.model"),
                self._config.get("ai.model"),
                os.getenv("GLM_MODEL"),
                "glm-4.7-flash",
            ]
        )
        timeout = self._coerce_timeout(
            self._first_non_empty(
                [
                    self._config.get("glm.timeout"),
                    self._config.get("ai.timeout"),
                    os.getenv("GLM_TIMEOUT"),
                    8,
                ],
                fallback="8",
            )
        )
        return ProviderRuntimeConfig(
            provider=provider,
            api_key=api_key,
            base_url=self._normalize_base_url(base_url),
            model=model,
            timeout_seconds=timeout,
        )

    async def test_provider(
        self,
        provider: ProviderName,
        timeout_seconds: Optional[int] = None,
    ) -> Dict[str, Any]:
        cfg = self._get_provider_config(provider)
        effective_timeout = timeout_seconds or cfg.timeout_seconds

        base_result: Dict[str, Any] = {
            "provider": provider,
            "configured": bool(cfg.api_key),
            "connected": False,
            "model": cfg.model,
            "base_url": cfg.base_url,
            "response_time_ms": None,
            "message": "",
        }

        if not cfg.api_key:
            base_result["message"] = "API key not configured"
            return base_result

        request_url = f"{cfg.base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {cfg.api_key}",
        }
        payload = {
            "model": cfg.model,
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 1,
            "temperature": 0,
            "stream": False,
        }

        start = time.perf_counter()
        try:
            timeout = aiohttp.ClientTimeout(total=self._coerce_timeout(effective_timeout, default=8))
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(request_url, headers=headers, json=payload) as resp:
                    elapsed_ms = int((time.perf_counter() - start) * 1000)
                    base_result["response_time_ms"] = elapsed_ms
                    if resp.status == 200:
                        base_result["connected"] = True
                        base_result["message"] = "ok"
                        return base_result

                    text = (await resp.text())[:200]
                    base_result["message"] = f"HTTP {resp.status}: {text}"
                    return base_result
        except Exception as exc:
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            base_result["response_time_ms"] = elapsed_ms
            base_result["message"] = str(exc)
            logger.warning("AI connectivity test failed for %s: %s", provider, exc)
            return base_result

    async def test_providers(
        self,
        providers: Sequence[ProviderName] = ("kimi", "deepseek", "glm"),
        timeout_seconds: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        normalized: List[ProviderName] = []
        for name in providers:
            if name in ("kimi", "deepseek", "glm") and name not in normalized:
                normalized.append(name)

        tasks = [self.test_provider(provider=name, timeout_seconds=timeout_seconds) for name in normalized]
        if not tasks:
            return []
        return await asyncio.gather(*tasks)


def get_ai_connectivity_service() -> AIConnectivityService:
    return AIConnectivityService.get_instance()
