"""
AI connectivity test service for smart rename flows.

Tests provider connectivity for:
- kimi (NVIDIA OpenAI-compatible endpoint)
- deepseek
- glm (Zhipu)
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import aiohttp

from app.core.logging import get_logger
from app.services.config_service import get_config_service


logger = get_logger(__name__)


@dataclass
class ProviderRuntimeConfig:
    provider: str
    api_key: str
    base_url: str
    model: str
    timeout_seconds: int


def get_ai_provider_configs() -> list[dict[str, Any]]:
    app_config = get_config_service().get_config()
    ai_config = getattr(app_config, "ai", None)
    providers = getattr(ai_config, "providers", None)
    if providers is None:
        return []
    return [item.model_dump() if hasattr(item, "model_dump") else item for item in providers]


class AIConnectivityService:
    _instance: AIConnectivityService | None = None

    def __init__(self):
        self._provider_configs_getter = get_ai_provider_configs

    @classmethod
    def get_instance(cls) -> AIConnectivityService:
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

    @staticmethod
    def _format_exception_message(exc: Exception) -> str:
        text = str(exc).strip()
        if text:
            return text
        if isinstance(exc, asyncio.TimeoutError):
            return "request timeout"
        if isinstance(exc, aiohttp.ClientConnectionError):
            return "connection error"
        if isinstance(exc, aiohttp.ClientError):
            return exc.__class__.__name__
        return exc.__class__.__name__

    def _get_unified_provider_map(self) -> dict[str, dict[str, Any]]:
        providers = self._provider_configs_getter()
        if not isinstance(providers, list):
            return {}
        return {
            str(item.get("name")).strip(): item
            for item in providers
            if isinstance(item, dict) and str(item.get("name", "")).strip()
        }

    def _get_default_provider_names(self) -> list[str]:
        provider_map = self._get_unified_provider_map()
        return list(provider_map.keys())

    def _get_provider_config(self, provider: str) -> ProviderRuntimeConfig:
        provider_map = self._get_unified_provider_map()
        unified_provider = provider_map.get(provider)
        if isinstance(unified_provider, dict):
            api_key = self._first_non_empty([unified_provider.get("api_key")])
            base_url = self._first_non_empty([unified_provider.get("base_url")], fallback="https://api.deepseek.com/v1")
            model = self._first_non_empty([unified_provider.get("model")])
            timeout = self._coerce_timeout(unified_provider.get("timeout"), default=8)
            return ProviderRuntimeConfig(
                provider=provider,
                api_key=api_key,
                base_url=self._normalize_base_url(base_url),
                model=model,
                timeout_seconds=timeout,
            )

        return ProviderRuntimeConfig(
            provider=provider,
            api_key="",
            base_url="https://api.deepseek.com/v1",
            model="",
            timeout_seconds=8,
        )

    async def test_provider(
        self,
        provider: str,
        timeout_seconds: int | None = None,
    ) -> dict[str, Any]:
        cfg = self._get_provider_config(provider)
        effective_timeout = timeout_seconds or cfg.timeout_seconds

        base_result: dict[str, Any] = {
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
            base_result["message"] = self._format_exception_message(exc)
            logger.warning("AI connectivity test failed for %s: %s", provider, base_result["message"])
            return base_result

    async def test_providers(
        self,
        providers: Sequence[str] | None = None,
        timeout_seconds: int | None = None,
    ) -> list[dict[str, Any]]:
        candidate_names = list(providers) if providers is not None else self._get_default_provider_names()
        normalized: list[str] = []
        for name in candidate_names:
            provider_name = str(name).strip()
            if provider_name and provider_name not in normalized:
                normalized.append(provider_name)

        tasks = [self.test_provider(provider=name, timeout_seconds=timeout_seconds) for name in normalized]
        if not tasks:
            return []
        return await asyncio.gather(*tasks)


def get_ai_connectivity_service() -> AIConnectivityService:
    return AIConnectivityService.get_instance()
