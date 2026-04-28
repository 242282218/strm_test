from __future__ import annotations

import re
from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest

from app.services import search_service as ss


class _FakeScoringEngine:
    def score(self, _keyword: str, result_item: dict[str, Any]) -> dict[str, Any]:
        cloud_type = result_item["cloud_type"]
        base_score = 0.9 if cloud_type == "quark" else 0.6
        return {
            "score": base_score,
            "confidence": 0.8,
            "quality": 0.7,
            "popularity": 0.6,
            "freshness": 0.5,
            "tags": ["ok"],
        }


class _FakeSizeFetcher:
    def __init__(self, size_map: dict[str, int] | None = None) -> None:
        self.size_map = size_map or {}
        self.batch_calls: list[tuple[list[dict[str, str]], int]] = []

    def extract_share_key(self, url: str) -> str | None:
        match = re.search(r"/s/([a-zA-Z0-9_-]+)", url)
        return match.group(1) if match else None

    async def batch_get_sizes(self, share_items: list[dict[str, str]], min_size_bytes: int = 0) -> dict[str, int]:
        self.batch_calls.append((share_items, min_size_bytes))
        return dict(self.size_map)

    def format_size(self, size_bytes: int) -> str:
        return f"{size_bytes}B"


class _FakeResponse:
    def __init__(self, payload: dict[str, Any], raise_error: Exception | None = None) -> None:
        self._payload = payload
        self._raise_error = raise_error

    def raise_for_status(self) -> None:
        if self._raise_error is not None:
            raise self._raise_error

    def json(self) -> dict[str, Any]:
        return self._payload


def _make_result(result_id: str, score: float, link_type: str = "quark") -> dict[str, Any]:
    return {
        "id": result_id,
        "title": result_id,
        "content": result_id,
        "cloud_links": [{"type": link_type, "url": f"https://pan.quark.cn/s/{result_id}", "password": ""}],
        "score": score,
        "confidence": score,
        "quality": score,
        "pub_date": f"2026-04-{int(score * 10):02d}",
    }


@pytest.fixture
def service(monkeypatch: pytest.MonkeyPatch) -> tuple[ss.ResourceSearchService, _FakeSizeFetcher]:
    fake_fetcher = _FakeSizeFetcher()
    monkeypatch.setattr(ss, "ScoringEngine", _FakeScoringEngine)
    monkeypatch.setattr(ss, "get_size_fetcher", lambda: fake_fetcher)
    return ss.ResourceSearchService(), fake_fetcher


def test_default_pansou_base_url_uses_https(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PANSOU_API_URL", raising=False)
    monkeypatch.setattr(ss, "ScoringEngine", _FakeScoringEngine)
    monkeypatch.setattr(ss, "get_size_fetcher", lambda: _FakeSizeFetcher())

    service = ss.ResourceSearchService()

    assert service._base_url == "https://pansou.xzcccc.eu.org"


def test_transform_cloud_type_mapping(service: tuple[ss.ResourceSearchService, _FakeSizeFetcher]) -> None:
    search, _ = service

    assert search._transform_cloud_type("Ali") == "aliyun"
    assert search._transform_cloud_type("ALIYUN") == "aliyun"
    assert search._transform_cloud_type("unknown-type") == "unknown-type"


def test_transform_pansou_result_merges_and_scores(service: tuple[ss.ResourceSearchService, _FakeSizeFetcher]) -> None:
    search, _ = service
    pansou_data = {
        "merged_by_type": {
            "quark": [
                {"url": "https://pan.quark.cn/s/k1", "note": "Movie A", "source": "src-a", "datetime": "2026-04-16"}
            ],
            "baidu": [
                {"url": "https://pan.quark.cn/s/k2", "note": "Movie B", "source": "src-b", "datetime": "2026-04-15"}
            ],
        }
    }

    transformed = search._transform_pansou_result(pansou_data, "movie")

    assert transformed["total"] == 2
    assert transformed["results"][0]["id"].startswith("quark_")
    assert transformed["results"][0]["score"] == 0.9
    assert transformed["results"][1]["score"] == 0.6
    assert transformed["merged_by_type"] == pansou_data["merged_by_type"]


@pytest.mark.asyncio
async def test_apply_size_filter_skips_when_min_size_not_positive(
    service: tuple[ss.ResourceSearchService, _FakeSizeFetcher],
) -> None:
    search, _ = service
    results = [_make_result("a", 0.9)]

    filtered = await search._apply_size_filter(results, 0)

    assert filtered is results


@pytest.mark.asyncio
async def test_apply_size_filter_filters_top20_quark_by_size(
    service: tuple[ss.ResourceSearchService, _FakeSizeFetcher],
) -> None:
    search, fake_fetcher = service
    results = [_make_result(f"k{i}", 100 - i) for i in range(22)]
    fake_fetcher.size_map = {"k0": 5_000, "k1": 100}

    filtered = await search._apply_size_filter(results, min_size_bytes=1024)

    assert [item["id"] for item in filtered] == ["k0", "k20", "k21"]
    assert filtered[0]["file_size"] == 5_000
    assert filtered[0]["cloud_links"][0]["size_human"] == "5000B"
    assert fake_fetcher.batch_calls and len(fake_fetcher.batch_calls[0][0]) == 20


@pytest.mark.asyncio
async def test_apply_size_filter_keeps_top20_when_no_size_data(
    service: tuple[ss.ResourceSearchService, _FakeSizeFetcher],
) -> None:
    search, fake_fetcher = service
    fake_fetcher.size_map = {}
    results = [_make_result(f"n{i}", 50 - i) for i in range(3)]

    filtered = await search._apply_size_filter(results, min_size_bytes=1024)

    assert [item["id"] for item in filtered] == ["n0", "n1", "n2"]


def test_sort_results_with_supported_keys(service: tuple[ss.ResourceSearchService, _FakeSizeFetcher]) -> None:
    search, _ = service
    results = [
        {"id": "a", "score": 0.5, "confidence": 0.1, "quality": 0.8, "pub_date": "2026-01-01", "file_size": 10},
        {"id": "b", "score": 0.9, "confidence": 0.9, "quality": 0.2, "pub_date": "2026-03-01", "file_size": 100},
    ]

    assert [item["id"] for item in search._sort_results(results)] == ["b", "a"]
    assert [item["id"] for item in search._sort_results(results, "confidence")] == ["b", "a"]
    assert [item["id"] for item in search._sort_results(results, "quality")] == ["a", "b"]
    assert [item["id"] for item in search._sort_results(results, "time")] == ["b", "a"]
    assert [item["id"] for item in search._sort_results(results, "size")] == ["b", "a"]
    assert search._sort_results(results, "unknown") is results


@pytest.mark.asyncio
async def test_search_returns_error_when_keyword_empty(
    service: tuple[ss.ResourceSearchService, _FakeSizeFetcher],
) -> None:
    search, _ = service

    result = await search.search(keyword="   ")

    assert result["error"] == "keyword cannot be empty"
    assert result["total"] == 0


@pytest.mark.asyncio
async def test_search_success_with_pagination_and_param_mapping(
    service: tuple[ss.ResourceSearchService, _FakeSizeFetcher], monkeypatch: pytest.MonkeyPatch
) -> None:
    search, _ = service
    captured: dict[str, Any] = {}
    payload = {
        "code": 0,
        "data": {
            "merged_by_type": {
                "quark": [
                    {"url": "https://pan.quark.cn/s/qa", "note": "A", "source": "x", "datetime": "2026-04-16"},
                    {"url": "https://pan.quark.cn/s/qb", "note": "B", "source": "x", "datetime": "2026-04-15"},
                ]
            }
        },
    }

    class _FakeClient:
        def __init__(self, **_kwargs) -> None:
            self.response = _FakeResponse(payload)

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url: str, params: dict[str, Any]):
            captured["url"] = url
            captured["params"] = dict(params)
            return self.response

    monkeypatch.setattr(ss.httpx, "AsyncClient", _FakeClient)

    result = await search.search(
        keyword="avatar",
        cloud_types=["quark", "ali"],
        sources=["s1", "s2"],
        page=1,
        page_size=1,
        sort_by="score",
        min_file_size=0,
    )

    assert result["total"] == 2
    assert result["has_more"] is True
    assert len(result["results"]) == 1
    assert captured["url"].endswith("/api/search")
    assert captured["params"]["cloud_types"] == "quark,aliyun"
    assert captured["params"]["channels"] == "s1,s2"
    assert captured["params"]["kw"] == "avatar"


@pytest.mark.asyncio
async def test_search_returns_pansou_business_error(
    service: tuple[ss.ResourceSearchService, _FakeSizeFetcher], monkeypatch: pytest.MonkeyPatch
) -> None:
    search, _ = service

    class _FakeClient:
        def __init__(self, **_kwargs) -> None:
            self.response = _FakeResponse({"code": 1001, "message": "bad request"})

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, _url: str, params: dict[str, Any]):
            return self.response

    monkeypatch.setattr(ss.httpx, "AsyncClient", _FakeClient)

    result = await search.search(keyword="avatar")

    assert result["error"] == "pansou: bad request"
    assert result["results"] == []


@pytest.mark.asyncio
async def test_search_returns_connect_error_message(
    service: tuple[ss.ResourceSearchService, _FakeSizeFetcher], monkeypatch: pytest.MonkeyPatch
) -> None:
    search, _ = service
    connect_error = httpx.ConnectError("no route", request=httpx.Request("GET", "http://x"))

    class _FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, _url: str, params: dict[str, Any]):
            raise connect_error

    monkeypatch.setattr(ss.httpx, "AsyncClient", lambda **_kwargs: _FakeClient())

    result = await search.search(keyword="avatar")

    assert result["error"] == "pansou服务未启动，请检查PANSOU_API_URL配置"


@pytest.mark.asyncio
async def test_search_returns_generic_exception_message(
    service: tuple[ss.ResourceSearchService, _FakeSizeFetcher], monkeypatch: pytest.MonkeyPatch
) -> None:
    search, _ = service

    class _FakeClient:
        def __init__(self, **_kwargs) -> None:
            self.response = _FakeResponse({"code": 0, "data": {}}, raise_error=RuntimeError("status failed"))

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, _url: str, params: dict[str, Any]):
            return self.response

    monkeypatch.setattr(ss.httpx, "AsyncClient", _FakeClient)

    result = await search.search(keyword="avatar")

    assert result["error"] == "status failed"


@pytest.mark.asyncio
async def test_search_with_filters_passthrough_error(
    service: tuple[ss.ResourceSearchService, _FakeSizeFetcher],
) -> None:
    search, _ = service
    search.search = AsyncMock(return_value={"error": "downstream"})  # type: ignore[method-assign]

    result = await search.search_with_filters(keyword="avatar")

    assert result["error"] == "downstream"


@pytest.mark.asyncio
async def test_search_with_filters_applies_score_and_confidence(
    service: tuple[ss.ResourceSearchService, _FakeSizeFetcher],
) -> None:
    search, _ = service
    search.search = AsyncMock(  # type: ignore[method-assign]
        return_value={
            "results": [
                {"id": "a", "score": 0.95, "confidence": 0.92},
                {"id": "b", "score": 0.91, "confidence": 0.20},
                {"id": "c", "score": 0.20, "confidence": 0.99},
            ],
            "total": 3,
            "page": 2,
            "page_size": 10,
            "has_more": False,
            "merged_by_type": {"quark": []},
        }
    )

    result = await search.search_with_filters(keyword="avatar", min_score=0.9, min_confidence=0.9, page=2, page_size=10)

    assert [item["id"] for item in result["results"]] == ["a"]
    assert result["total"] == 1
    assert result["page"] == 2
    assert result["filters"]["applied"] is True
