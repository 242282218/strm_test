from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api import tmdb


def _build_config(*, canonical_api_key: str = "", legacy_api_key: str = "") -> SimpleNamespace:
    return SimpleNamespace(
        tmdb=SimpleNamespace(api_key=canonical_api_key),
        api_keys=SimpleNamespace(tmdb_api_key=legacy_api_key),
    )


def test_get_tmdb_service_prefers_canonical_runtime_config(monkeypatch: pytest.MonkeyPatch) -> None:
    config = _build_config(canonical_api_key="canonical-key", legacy_api_key="legacy-key")
    cache_service = object()
    captured: dict[str, object] = {}

    monkeypatch.setattr(tmdb, "get_config_service", lambda: SimpleNamespace(get_config=lambda: config))
    monkeypatch.setattr(tmdb, "get_cache_service", lambda: cache_service)

    def fake_get_tmdb_service(*, api_key: str, language: str, cache_service: object) -> dict[str, object]:
        captured.update({"api_key": api_key, "language": language, "cache_service": cache_service})
        return captured

    monkeypatch.setattr(tmdb, "get_tmdb_service", fake_get_tmdb_service)

    service = tmdb._get_tmdb_service()

    assert service is captured
    assert captured == {
        "api_key": "canonical-key",
        "language": "zh-CN",
        "cache_service": cache_service,
    }


def test_get_tmdb_service_falls_back_to_legacy_api_keys_section(monkeypatch: pytest.MonkeyPatch) -> None:
    config = _build_config(canonical_api_key="", legacy_api_key="legacy-key")
    cache_service = object()

    monkeypatch.setattr(tmdb, "get_config_service", lambda: SimpleNamespace(get_config=lambda: config))
    monkeypatch.setattr(tmdb, "get_cache_service", lambda: cache_service)
    monkeypatch.setattr(
        tmdb,
        "get_tmdb_service",
        lambda *, api_key, language, cache_service: {
            "api_key": api_key,
            "language": language,
            "cache_service": cache_service,
        },
    )

    service = tmdb._get_tmdb_service()

    assert service["api_key"] == "legacy-key"
    assert service["language"] == "zh-CN"
    assert service["cache_service"] is cache_service


def test_get_tmdb_service_raises_when_runtime_config_has_no_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tmdb, "get_config_service", lambda: SimpleNamespace(get_config=lambda: SimpleNamespace()))

    with pytest.raises(HTTPException) as exc_info:
        tmdb._get_tmdb_service()

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "TMDB API key not configured"
