from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

from app.config.settings import AppConfig
from app.services.ai_parser_service import AIParseResult as ParserAIParseResult
from app.services.ai_parser_service import AIParserService
from app.utils.media_parser import MediaParser
from app.services import unified_ai_service as unified_ai_service_module


class _FakeConfigService:
    def __init__(self, config: AppConfig) -> None:
        self._config = config

    def get_config(self) -> AppConfig:
        return self._config


class _FakeUnifiedService:
    def __init__(self) -> None:
        self.api_key = "unified-key"
        self.calls: list[tuple[str, int | None]] = []

    def has_available_provider(self) -> bool:
        return True

    async def parse_filename(
        self,
        filename: str,
        max_timeout_seconds: int | None = None,
    ) -> unified_ai_service_module.AIParseResult:
        self.calls.append((filename, max_timeout_seconds))
        return unified_ai_service_module.AIParseResult(
            title="Parsed Title",
            original_title="Original Title",
            year=2024,
            season=1,
            episode=2,
            media_type="tv",
            confidence=0.95,
        )


def _build_app_config() -> AppConfig:
    return AppConfig.model_validate(
        {
            "ai": {
                "providers": [
                    {
                        "name": "backup",
                        "api_key": "backup-key",
                        "base_url": "https://backup.example.com/v1",
                        "model": "backup-model",
                        "timeout": 30,
                        "enabled": True,
                        "priority": 10,
                    },
                    {
                        "name": "primary",
                        "api_key": "primary-key",
                        "base_url": "https://primary.example.com/v1",
                        "model": "primary-model",
                        "timeout": 25,
                        "enabled": True,
                        "priority": 100,
                    },
                    {
                        "name": "disabled",
                        "api_key": "disabled-key",
                        "base_url": "https://disabled.example.com/v1",
                        "model": "disabled-model",
                        "timeout": 20,
                        "enabled": False,
                        "priority": 999,
                    },
                ]
            }
        }
    )


def test_unified_ai_service_reads_runtime_providers_from_config_service() -> None:
    service = unified_ai_service_module.UnifiedAIService()
    config = _build_app_config()

    with patch(
        "app.services.unified_ai_service.get_config_service",
        return_value=_FakeConfigService(config),
    ):
        providers = service._get_providers()
        assert service.api_key == "primary-key"
        assert service.has_available_provider() is True

    assert [provider.name for provider in providers] == ["primary", "backup"]


def test_unified_ai_service_parse_filename_forwards_timeout_cap() -> None:
    service = unified_ai_service_module.UnifiedAIService()
    provider = unified_ai_service_module.AIProviderConfig(
        name="primary",
        api_key="primary-key",
        base_url="https://primary.example.com/v1",
        model="primary-model",
        timeout=30,
        enabled=True,
        priority=100,
    )
    service._provider_getter = lambda: [provider]
    service._call_provider = AsyncMock(  # type: ignore[method-assign]
        return_value=unified_ai_service_module.AIParseResult(title="Parsed", media_type="movie")
    )

    result = asyncio.run(service.parse_filename("Movie.2024.mkv", max_timeout_seconds=5))

    assert result.title == "Parsed"
    service._call_provider.assert_awaited_once_with(provider, "Movie.2024.mkv", timeout_seconds=5)


def test_unified_ai_service_returns_none_when_all_providers_fail() -> None:
    service = unified_ai_service_module.UnifiedAIService()
    provider = unified_ai_service_module.AIProviderConfig(
        name="primary",
        api_key="primary-key",
        base_url="https://primary.example.com/v1",
        model="primary-model",
        timeout=30,
        enabled=True,
        priority=100,
    )
    service._provider_getter = lambda: [provider]
    service._call_provider = AsyncMock(return_value=None)  # type: ignore[method-assign]

    result = asyncio.run(service.parse_filename("Movie.2024.mkv", max_timeout_seconds=5))

    assert result is None
    service._call_provider.assert_awaited_once_with(provider, "Movie.2024.mkv", timeout_seconds=5)


def test_unified_ai_service_parses_fenced_json_payload() -> None:
    class _FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {
                "choices": [
                    {
                        "message": {
                            "content": '```json\n{"title":"Parsed","media_type":"tv","season":1,"episode":2}\n```'
                        }
                    }
                ]
            }

    class _FakeClient:
        is_closed = False

        async def post(self, *args, **kwargs) -> _FakeResponse:
            return _FakeResponse()

    service = unified_ai_service_module.UnifiedAIService()
    provider = unified_ai_service_module.AIProviderConfig(
        name="primary",
        api_key="primary-key",
        base_url="https://primary.example.com/v1",
        model="primary-model",
        timeout=30,
        enabled=True,
        priority=100,
    )
    service._client = _FakeClient()  # type: ignore[assignment]

    result = asyncio.run(service._call_provider(provider, "Show.S01E02.mkv", timeout_seconds=5))

    assert result is not None
    assert result.title == "Parsed"
    assert result.media_type == "tv"
    assert result.season == 1
    assert result.episode == 2


def test_ai_parser_service_keeps_compatibility_contract() -> None:
    fake_unified_service = _FakeUnifiedService()

    with patch(
        "app.services.ai_parser_service.get_unified_ai_service",
        return_value=fake_unified_service,
    ):
        service = AIParserService()
        result = asyncio.run(service.parse_filename("Show.S01E02.mkv", max_timeout_seconds=7))

    assert service.api_key == "unified-key"
    assert service.has_available_provider() is True
    assert fake_unified_service.calls == [("Show.S01E02.mkv", 7)]
    assert isinstance(result, ParserAIParseResult)
    assert result.title == "Parsed Title"
    assert result.original_title == "Original Title"
    assert result.year == 2024
    assert result.season == 1
    assert result.episode == 2
    assert result.media_type == "tv"
    assert result.confidence == 0.95


def test_media_parser_keeps_regex_result_when_ai_parse_fails() -> None:
    class _FailingAIService:
        def has_available_provider(self) -> bool:
            return True

        async def parse_filename(
            self,
            filename: str,
            max_timeout_seconds: int | None = None,
        ) -> None:
            return None

    with patch(
        "app.services.ai_parser_service.get_ai_parser_service",
        return_value=_FailingAIService(),
    ):
        result = asyncio.run(MediaParser.parse_with_ai("Show.S01E02.mkv", force=True, ai_timeout_seconds=3))

    assert result["title"] == "Show"
    assert result["season"] == 1
    assert result["episode"] == 2
    assert result["ai_parsed"] is False
    assert result["source"] == "regex"
