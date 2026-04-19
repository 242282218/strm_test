from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from urllib.parse import parse_qs, urlsplit

import pytest
from aiohttp.http_exceptions import LineTooLong
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from fastapi.testclient import TestClient

import app.api.proxy as proxy_module
from app.api.emby import router as emby_router
from app.api.proxy import router as proxy_router
from app.core.dependencies import require_api_key
from app.core.url_validator import URLValidationError
from app.services.emby_proxy_service import EmbyProxyService
from app.services.playbackinfo_hook import PlaybackInfoHook


class _FakeEmbyProxyService:
    last_init: dict[str, str] | None = None
    last_proxy_playback_info_call: dict[str, object] | None = None

    def __init__(self, emby_base_url: str, api_key: str, cookie: str, proxy_base_url: str):
        self.emby_base_url = emby_base_url
        self.api_key = api_key
        self.cookie = cookie
        self.proxy_base_url = proxy_base_url
        _FakeEmbyProxyService.last_init = {
            "emby_base_url": emby_base_url,
            "api_key": api_key,
            "cookie": cookie,
            "proxy_base_url": proxy_base_url,
        }

    async def __aenter__(self):
        self.playback_hook = self
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return None

    async def hook_playback_info(
        self,
        item_id: str,
        user_id: str,
        media_source_id: str | None = None,
        is_web_client: bool = False,
        client_name: str | None = None,
        device_name: str | None = None,
        playback_request: dict[str, object] | None = None,
    ):
        _FakeEmbyProxyService.last_proxy_playback_info_call = {
            "item_id": item_id,
            "user_id": user_id,
            "media_source_id": media_source_id,
            "is_web_client": is_web_client,
            "client_name": client_name,
            "device_name": device_name,
            "playback_request": playback_request,
        }
        return {
            "item_id": item_id,
            "user_id": user_id,
            "media_source_id": media_source_id,
            "proxy_base_url": self.proxy_base_url,
            "is_web_client": is_web_client,
            "client_name": client_name,
            "device_name": device_name,
            "playback_request": playback_request,
        }


class _FakeQuarkService:
    def __init__(self, cookie: str):
        self.cookie = cookie

    async def get_transcoding_link(self, file_id: str):
        return SimpleNamespace(url=f"https://transcode.example/{file_id}.m3u8")

    async def close(self):
        return None


class _FakeLinkResolver:
    def __init__(self, quark_service):
        self.quark_service = quark_service

    async def resolve(self, file_id: str, path: str | None):
        return f"https://download.example/{file_id}.mp4"


class _FakeWebDAVFallback:
    def get_fallback_url(self, path: str | None):
        return None


def _build_proxy_client(*, raise_server_exceptions: bool = True) -> TestClient:
    app = FastAPI()
    app.include_router(proxy_router)
    app.dependency_overrides[require_api_key] = lambda: None
    return TestClient(app, raise_server_exceptions=raise_server_exceptions)


def _build_proxy_client_without_auth_override() -> TestClient:
    app = FastAPI()
    app.include_router(proxy_router)
    return TestClient(app)


def _build_emby_client(*, raise_server_exceptions: bool = True) -> TestClient:
    app = FastAPI()
    app.include_router(emby_router)
    return TestClient(app, raise_server_exceptions=raise_server_exceptions)


@pytest.mark.asyncio
async def test_playback_info_hook_when_remote_media_then_uses_redirect_url():
    emby_client = AsyncMock()
    emby_client.get_playback_info = AsyncMock(
        return_value={
            "MediaSources": [
                {
                    "Id": "media_source_1",
                    "Path": "http://example.com/api/proxy/stream/file123",
                    "IsRemote": True,
                }
            ]
        }
    )

    hook = PlaybackInfoHook(
        emby_client=emby_client,
        quark_service=AsyncMock(),
        proxy_base_url="http://proxy.example:18097",
    )

    result = await hook.hook_playback_info(item_id="item1", user_id="user1")

    media_source = result["MediaSources"][0]
    assert media_source["DirectStreamUrl"] == "http://proxy.example:18097/api/proxy/redirect/file123?Static=true"
    assert "SupportsTranscoding" not in media_source


@pytest.mark.asyncio
async def test_playback_info_hook_when_playback_info_fails_then_falls_back_to_item_media_sources():
    emby_client = AsyncMock()
    emby_client.get_playback_info = AsyncMock(side_effect=TimeoutError("playback info timeout"))
    emby_client.get_items = AsyncMock(
        return_value={
            "Id": "item1",
            "MediaType": "Video",
            "RunTimeTicks": 123456789,
            "MediaSources": [
                {
                    "Id": "media_source_1",
                    "Path": "http://example.com/api/proxy/stream/file123",
                    "IsRemote": True,
                }
            ],
        }
    )

    hook = PlaybackInfoHook(
        emby_client=emby_client,
        quark_service=AsyncMock(),
        proxy_base_url="http://proxy.example:18097",
    )

    result = await hook.hook_playback_info(item_id="item1", user_id="user1")

    assert result["Id"] == "item1"
    assert result["MediaType"] == "Video"
    assert result["RunTimeTicks"] == 123456789
    media_source = result["MediaSources"][0]
    assert media_source["DirectStreamUrl"] == "http://proxy.example:18097/api/proxy/redirect/file123?Static=true"
    assert "SupportsDirectPlay" not in media_source
    assert "SupportsDirectStream" not in media_source
    assert "SupportsTranscoding" not in media_source
    emby_client.get_items.assert_awaited_once_with(item_id="item1", user_id="user1")


@pytest.mark.asyncio
async def test_playback_info_hook_when_post_request_payload_provided_then_uses_post_playback_info():
    emby_client = AsyncMock()
    emby_client.get_playback_info = AsyncMock()
    emby_client.post_playback_info = AsyncMock(
        return_value={
            "MediaSources": [
                {
                    "Id": "media_source_1",
                    "Path": "http://example.com/api/proxy/stream/file123",
                    "IsRemote": True,
                }
            ]
        }
    )

    hook = PlaybackInfoHook(
        emby_client=emby_client,
        quark_service=AsyncMock(),
        proxy_base_url="http://proxy.example:18097",
    )
    playback_request = {
        "UserId": "user1",
        "MediaSourceId": "media_source_1",
        "DeviceProfile": {"Name": "Android TV"},
    }

    result = await hook.hook_playback_info(
        item_id="item1",
        user_id="user1",
        media_source_id="media_source_1",
        playback_request=playback_request,
    )

    assert result["MediaSources"][0]["DirectStreamUrl"] == (
        "http://proxy.example:18097/api/proxy/redirect/file123?Static=true"
    )
    emby_client.post_playback_info.assert_awaited_once_with(
        item_id="item1",
        user_id="user1",
        device_profile={
            "UserId": "user1",
            "MediaSourceId": "media_source_1",
            "DeviceProfile": {"Name": "Android TV"},
        },
    )
    emby_client.get_playback_info.assert_not_awaited()


@pytest.mark.asyncio
async def test_playback_info_hook_when_post_request_payload_has_null_device_profile_then_backfills_default_profile():
    emby_client = AsyncMock()
    emby_client.get_playback_info = AsyncMock()
    emby_client.post_playback_info = AsyncMock(
        return_value={
            "MediaSources": [
                {
                    "Id": "media_source_1",
                    "Path": "http://example.com/api/proxy/stream/file123",
                    "IsRemote": True,
                }
            ]
        }
    )
    emby_client._get_default_device_profile = Mock(return_value={"DeviceProfile": {"Name": "Android TV default"}})

    hook = PlaybackInfoHook(
        emby_client=emby_client,
        quark_service=AsyncMock(),
        proxy_base_url="http://proxy.example:18097",
    )
    playback_request = {
        "UserId": "user1",
        "DeviceProfile": None,
    }

    await hook.hook_playback_info(
        item_id="item1",
        user_id="user1",
        media_source_id="media_source_1",
        playback_request=playback_request,
    )

    emby_client._get_default_device_profile.assert_called_once_with()
    emby_client.post_playback_info.assert_awaited_once_with(
        item_id="item1",
        user_id="user1",
        device_profile={
            "UserId": "user1",
            "DeviceProfile": {"Name": "Android TV default"},
            "MediaSourceId": "media_source_1",
        },
    )
    emby_client.get_playback_info.assert_not_awaited()


@pytest.mark.asyncio
async def test_playback_info_hook_when_post_request_payload_uses_legacy_media_source_id_then_backfills_canonical_field():
    emby_client = AsyncMock()
    emby_client.get_playback_info = AsyncMock()
    emby_client.post_playback_info = AsyncMock(
        return_value={
            "MediaSources": [
                {
                    "Id": "media_source_1",
                    "Path": "http://example.com/api/proxy/stream/file123",
                    "IsRemote": True,
                }
            ]
        }
    )

    hook = PlaybackInfoHook(
        emby_client=emby_client,
        quark_service=AsyncMock(),
        proxy_base_url="http://proxy.example:18097",
    )
    playback_request = {
        "UserId": "user1",
        "media_source_id": "media_source_1",
        "DeviceProfile": {"Name": "Android TV"},
    }

    await hook.hook_playback_info(
        item_id="item1",
        user_id="user1",
        media_source_id="media_source_1",
        playback_request=playback_request,
    )

    posted_payload = emby_client.post_playback_info.await_args.kwargs["device_profile"]
    assert posted_payload.get("MediaSourceId") == "media_source_1"
    assert posted_payload["DeviceProfile"] == {"Name": "Android TV"}
    emby_client.get_playback_info.assert_not_awaited()


@pytest.mark.asyncio
async def test_playback_info_hook_when_playback_info_fails_for_local_media_then_reraises():
    emby_client = AsyncMock()
    emby_client.get_playback_info = AsyncMock(side_effect=TimeoutError("playback info timeout"))
    emby_client.get_items = AsyncMock(
        return_value={
            "Id": "item1",
            "MediaSources": [
                {
                    "Id": "media_source_1",
                    "Path": "D:/media/movie.mkv",
                    "IsRemote": False,
                }
            ],
        }
    )

    hook = PlaybackInfoHook(
        emby_client=emby_client,
        quark_service=AsyncMock(),
        proxy_base_url="http://proxy.example:18097",
    )

    with pytest.raises(TimeoutError, match="playback info timeout"):
        await hook.hook_playback_info(item_id="item1", user_id="user1")


@pytest.mark.asyncio
async def test_playback_info_hook_when_remote_source_explicitly_disables_capabilities_then_preserves_them():
    emby_client = AsyncMock()
    emby_client.get_playback_info = AsyncMock(
        return_value={
            "MediaSources": [
                {
                    "Id": "media_source_1",
                    "Path": "http://example.com/api/proxy/stream/file123",
                    "IsRemote": True,
                    "SupportsDirectPlay": False,
                    "SupportsDirectStream": False,
                    "SupportsTranscoding": False,
                }
            ]
        }
    )

    hook = PlaybackInfoHook(
        emby_client=emby_client,
        quark_service=AsyncMock(),
        proxy_base_url="http://proxy.example:18097",
    )

    result = await hook.hook_playback_info(item_id="item1", user_id="user1")

    media_source = result["MediaSources"][0]
    assert media_source["DirectStreamUrl"] == "http://proxy.example:18097/api/proxy/redirect/file123?Static=true"
    assert media_source["SupportsDirectPlay"] is False
    assert media_source["SupportsDirectStream"] is False
    assert media_source["SupportsTranscoding"] is False


@pytest.mark.asyncio
async def test_playback_info_hook_when_remote_source_has_transcoding_then_preserves_transcoding_fields():
    emby_client = AsyncMock()
    emby_client.get_playback_info = AsyncMock(
        return_value={
            "MediaSources": [
                {
                    "Id": "media_source_1",
                    "Path": "http://example.com/api/proxy/stream/file123",
                    "IsRemote": True,
                    "SupportsTranscoding": True,
                    "TranscodingUrl": "/Videos/77/master.m3u8",
                    "TranscodingSubProtocol": "hls",
                    "TranscodingContainer": "ts",
                }
            ]
        }
    )

    hook = PlaybackInfoHook(
        emby_client=emby_client,
        quark_service=AsyncMock(),
        proxy_base_url="http://proxy.example:18097",
    )

    result = await hook.hook_playback_info(item_id="item1", user_id="user1")

    media_source = result["MediaSources"][0]
    assert media_source["DirectStreamUrl"] == "http://proxy.example:18097/api/proxy/redirect/file123?Static=true"
    assert media_source["SupportsTranscoding"] is True
    assert media_source["TranscodingUrl"] == "/Videos/item1/master.m3u8?MediaSourceId=media_source_1&smart_media_proxy=1"
    assert media_source["TranscodingSubProtocol"] == "hls"
    assert media_source["TranscodingContainer"] == "ts"


@pytest.mark.asyncio
async def test_playback_info_hook_when_web_client_and_remote_source_then_rewrites_to_emby_style_stream_url():
    emby_client = AsyncMock()
    emby_client.get_playback_info = AsyncMock(
        return_value={
            "MediaSources": [
                {
                    "Id": "media_source_1",
                    "Path": "http://example.com/api/proxy/stream/file123",
                    "IsRemote": True,
                    "Container": "mkv",
                    "DirectStreamUrl": "/Videos/77/stream.mkv",
                    "SupportsTranscoding": True,
                    "TranscodingUrl": "/Videos/77/master.m3u8",
                }
            ]
        }
    )

    hook = PlaybackInfoHook(
        emby_client=emby_client,
        quark_service=AsyncMock(),
        proxy_base_url="http://proxy.example:18097",
    )

    result = await hook.hook_playback_info(item_id="item1", user_id="user1", is_web_client=True)

    media_source = result["MediaSources"][0]
    assert media_source["DirectStreamUrl"] == (
        "http://proxy.example:18097/Videos/item1/stream?MediaSourceId=media_source_1&Static=true"
        "&smart_media_proxy=1&container=mkv"
    )
    assert media_source["SupportsTranscoding"] is True
    assert media_source["TranscodingUrl"] == "/Videos/item1/master.m3u8?MediaSourceId=media_source_1&smart_media_proxy=1"


@pytest.mark.asyncio
async def test_playback_info_hook_when_non_web_client_and_remote_source_then_rewrites_to_proxy_redirect():
    emby_client = AsyncMock()
    emby_client.get_playback_info = AsyncMock(
        return_value={
            "MediaSources": [
                {
                    "Id": "media_source_1",
                    "Path": "http://example.com/api/proxy/stream/file123",
                    "IsRemote": True,
                    "DirectStreamUrl": "/Videos/77/stream.mkv",
                    "SupportsTranscoding": True,
                    "TranscodingUrl": "/Videos/77/master.m3u8",
                }
            ]
        }
    )

    hook = PlaybackInfoHook(
        emby_client=emby_client,
        quark_service=AsyncMock(),
        proxy_base_url="http://proxy.example:18097",
    )

    result = await hook.hook_playback_info(item_id="item1", user_id="user1", is_web_client=False)

    media_source = result["MediaSources"][0]
    assert media_source["DirectStreamUrl"] == "http://proxy.example:18097/api/proxy/redirect/file123?Static=true"
    assert media_source["SupportsTranscoding"] is True
    assert media_source["TranscodingUrl"] == "/Videos/item1/master.m3u8?MediaSourceId=media_source_1&smart_media_proxy=1"


@pytest.mark.asyncio
async def test_playback_info_hook_when_remote_source_uses_uppercase_scheme_then_still_rewrites_to_proxy_redirect():
    emby_client = AsyncMock()
    emby_client.get_playback_info = AsyncMock(
        return_value={
            "MediaSources": [
                {
                    "Id": "media_source_1",
                    "Path": "HTTPS://example.com/api/proxy/stream/file123",
                    "IsRemote": True,
                    "DirectStreamUrl": "/Videos/77/stream.mkv",
                    "SupportsTranscoding": True,
                    "TranscodingUrl": "/Videos/77/master.m3u8",
                }
            ]
        }
    )

    hook = PlaybackInfoHook(
        emby_client=emby_client,
        quark_service=AsyncMock(),
        proxy_base_url="http://proxy.example:18097",
    )

    result = await hook.hook_playback_info(item_id="item1", user_id="user1", is_web_client=False)

    media_source = result["MediaSources"][0]
    assert media_source["DirectStreamUrl"] == "http://proxy.example:18097/api/proxy/redirect/file123?Static=true"
    assert media_source["TranscodingUrl"] == "/Videos/item1/master.m3u8?MediaSourceId=media_source_1&smart_media_proxy=1"


@pytest.mark.asyncio
async def test_playback_info_hook_when_remote_transcoding_query_present_then_rewrites_to_local_master_playlist():
    emby_client = AsyncMock()
    emby_client.get_playback_info = AsyncMock(
        return_value={
            "MediaSources": [
                {
                    "Id": "media_source_1",
                    "Path": "http://example.com/api/proxy/stream/file123",
                    "IsRemote": True,
                    "SupportsTranscoding": True,
                    "TranscodingUrl": "/Videos/77/master.m3u8?PlaySessionId=session77&DeviceId=device77",
                }
            ]
        }
    )

    hook = PlaybackInfoHook(
        emby_client=emby_client,
        quark_service=AsyncMock(),
        proxy_base_url="http://proxy.example:18097",
    )

    result = await hook.hook_playback_info(item_id="item1", user_id="user1", is_web_client=True)

    transcoding_url = result["MediaSources"][0]["TranscodingUrl"]
    parsed = urlsplit(transcoding_url)
    query = parse_qs(parsed.query)
    assert parsed.path == "/Videos/item1/master.m3u8"
    assert query["MediaSourceId"] == ["media_source_1"]
    assert query["smart_media_proxy"] == ["1"]
    assert query["PlaySessionId"] == ["session77"]
    assert query["DeviceId"] == ["device77"]


@pytest.mark.asyncio
async def test_playback_info_hook_when_web_client_and_local_strm_source_then_rewrites_to_local_emby_routes(tmp_path):
    strm_file = tmp_path / "movie.strm"
    strm_file.write_text("quark://real_file_123\n", encoding="utf-8")

    emby_client = AsyncMock()
    emby_client.get_playback_info = AsyncMock(
        return_value={
            "MediaSources": [
                {
                    "Id": "media_source_1",
                    "Path": str(strm_file),
                    "IsRemote": False,
                    "Container": "mkv",
                    "SupportsTranscoding": True,
                    "TranscodingUrl": "/Videos/77/master.m3u8",
                }
            ]
        }
    )

    hook = PlaybackInfoHook(
        emby_client=emby_client,
        quark_service=AsyncMock(),
        proxy_base_url="http://proxy.example:18097",
    )

    result = await hook.hook_playback_info(item_id="item1", user_id="user1", is_web_client=True)

    media_source = result["MediaSources"][0]
    assert media_source["DirectStreamUrl"] == (
        "http://proxy.example:18097/Videos/item1/stream?MediaSourceId=media_source_1&Static=true"
        "&smart_media_proxy=1&container=mkv"
    )
    assert media_source["TranscodingUrl"] == "/Videos/item1/master.m3u8?MediaSourceId=media_source_1&smart_media_proxy=1"


@pytest.mark.asyncio
async def test_playback_info_hook_when_non_web_client_and_local_strm_source_has_transcoding_then_rewrites_master_playlist(
    tmp_path,
):
    strm_file = tmp_path / "movie.strm"
    strm_file.write_text("quark://real_file_123\n", encoding="utf-8")

    emby_client = AsyncMock()
    emby_client.get_playback_info = AsyncMock(
        return_value={
            "MediaSources": [
                {
                    "Id": "media_source_1",
                    "Path": str(strm_file),
                    "IsRemote": False,
                    "SupportsTranscoding": True,
                    "TranscodingUrl": "/Videos/77/master.m3u8?PlaySessionId=session77",
                }
            ]
        }
    )

    hook = PlaybackInfoHook(
        emby_client=emby_client,
        quark_service=AsyncMock(),
        proxy_base_url="http://proxy.example:18097",
    )

    result = await hook.hook_playback_info(item_id="item1", user_id="user1", is_web_client=False)

    media_source = result["MediaSources"][0]
    assert media_source["DirectStreamUrl"] == "http://proxy.example:18097/api/proxy/redirect/real_file_123?Static=true"
    assert media_source["TranscodingUrl"] == (
        "/Videos/item1/master.m3u8?PlaySessionId=session77&MediaSourceId=media_source_1&smart_media_proxy=1"
    )


@pytest.mark.asyncio
async def test_playback_info_hook_when_fallback_has_mixed_sources_then_keeps_only_remote_candidates():
    emby_client = AsyncMock()
    emby_client.get_playback_info = AsyncMock(side_effect=TimeoutError("playback info timeout"))
    emby_client.get_items = AsyncMock(
        return_value={
            "Id": "item1",
            "MediaSources": [
                {
                    "Id": "remote_source",
                    "Path": "http://example.com/api/proxy/stream/file123",
                    "IsRemote": True,
                },
                {
                    "Id": "local_source",
                    "Path": "D:/media/movie.mkv",
                    "IsRemote": False,
                },
            ],
        }
    )

    hook = PlaybackInfoHook(
        emby_client=emby_client,
        quark_service=AsyncMock(),
        proxy_base_url="http://proxy.example:18097",
    )

    result = await hook.hook_playback_info(item_id="item1", user_id="user1")

    assert [source["Id"] for source in result["MediaSources"]] == ["remote_source"]
    assert result["MediaSources"][0]["DirectStreamUrl"] == (
        "http://proxy.example:18097/api/proxy/redirect/file123?Static=true"
    )


@pytest.mark.asyncio
async def test_playback_info_hook_when_media_source_id_provided_then_fallback_filters_to_requested_source():
    emby_client = AsyncMock()
    emby_client.get_playback_info = AsyncMock(side_effect=TimeoutError("playback info timeout"))
    emby_client.get_items = AsyncMock(
        return_value={
            "Id": "item1",
            "MediaSources": [
                {
                    "Id": "remote_source",
                    "Path": "http://example.com/api/proxy/stream/file123",
                    "IsRemote": True,
                },
                {
                    "Id": "other_remote_source",
                    "Path": "http://example.com/api/proxy/stream/file456",
                    "IsRemote": True,
                },
            ],
        }
    )

    hook = PlaybackInfoHook(
        emby_client=emby_client,
        quark_service=AsyncMock(),
        proxy_base_url="http://proxy.example:18097",
    )

    result = await hook.hook_playback_info(item_id="item1", user_id="user1", media_source_id="other_remote_source")

    assert [source["Id"] for source in result["MediaSources"]] == ["other_remote_source"]
    assert result["MediaSources"][0]["DirectStreamUrl"] == (
        "http://proxy.example:18097/api/proxy/redirect/file456?Static=true"
    )


@pytest.mark.asyncio
async def test_resolve_media_source_file_id_when_path_is_local_strm_then_prefers_strm_content_over_proxy_placeholder(tmp_path):
    strm_dir = tmp_path / "movies"
    strm_dir.mkdir()
    strm_file = strm_dir / "demo.strm"
    strm_file.write_text("quark://real_file_123\n", encoding="utf-8")

    service = EmbyProxyService(
        emby_base_url="http://emby.example:8096",
        api_key="test-key",
        cookie="test-cookie",
        proxy_base_url="http://proxy.example:18097",
    )
    service.emby_client = AsyncMock()
    service.emby_client.get_items = AsyncMock(
        return_value={
            "Id": "item1",
            "MediaSources": [
                {
                    "Id": "media_source_1",
                    "Path": f"http://proxy.example:18097/api/proxy/redirect/placeholder123?path={strm_file.as_posix()}",
                    "IsRemote": True,
                }
            ],
        }
    )

    file_id = await service.resolve_media_source_file_id(item_id="item1", media_source_id="media_source_1")

    assert file_id == "real_file_123"


@pytest.mark.asyncio
async def test_resolve_media_source_file_id_when_item_path_is_local_strm_then_prefers_current_strm_content_over_stale_media_source(tmp_path):
    strm_dir = tmp_path / "movies"
    strm_dir.mkdir()
    strm_file = strm_dir / "current.strm"
    strm_file.write_text(
        "http://proxy.example:18097/api/proxy/redirect/placeholder999?path=%E5%BD%B1%E8%A7%86%E6%94%B6%E8%97%8F/%E7%94%B5%E5%BD%B1/%E4%BD%A0%E7%9A%84%E5%90%8D%E5%AD%97%E3%80%82%20%282016%29%20%5Btmdbid%3D372058%5D/movie.mkv\n",
        encoding="utf-8",
    )

    service = EmbyProxyService(
        emby_base_url="http://emby.example:8096",
        api_key="test-key",
        cookie="test-cookie",
        proxy_base_url="http://proxy.example:18097",
    )
    service.emby_client = AsyncMock()
    service.emby_client.get_items = AsyncMock(
        return_value={
            "Id": "item144",
            "Path": str(strm_file),
            "MediaSources": [
                {
                    "Id": "mediasource_144",
                    "Path": "http://proxy.example:18097/api/proxy/redirect/staleplaceholder?path=%E6%B5%81%E6%B5%AA%E5%9C%B0%E7%90%83/movie.mkv",
                    "IsRemote": True,
                }
            ],
        }
    )
    service.quark_service = AsyncMock()
    service.quark_service.get_file_by_path = AsyncMock(return_value=SimpleNamespace(fid="real_quark_fid_144"))

    file_id = await service.resolve_media_source_file_id(item_id="item144", media_source_id="mediasource_144")

    assert file_id == "real_quark_fid_144"
    service.quark_service.get_file_by_path.assert_awaited_once_with(
        "影视收藏/电影/你的名字。 (2016) [tmdbid=372058]/movie.mkv"
    )


@pytest.mark.asyncio
async def test_resolve_media_source_file_id_when_proxy_path_contains_remote_path_then_resolves_real_quark_fid():
    service = EmbyProxyService(
        emby_base_url="http://emby.example:8096",
        api_key="test-key",
        cookie="test-cookie",
        proxy_base_url="http://proxy.example:18097",
    )
    service.emby_client = AsyncMock()
    service.emby_client.get_items = AsyncMock(
        return_value={
            "Id": "item144",
            "MediaSources": [
                {
                    "Id": "mediasource_144",
                    "Path": "http://proxy.example:18097/api/proxy/redirect/placeholder123?path=%E6%B5%81%E6%B5%AA%E5%9C%B0%E7%90%83/movie.mkv",
                    "IsRemote": True,
                }
            ],
        }
    )
    service.quark_service = AsyncMock()
    service.quark_service.get_file_by_path = AsyncMock(return_value=SimpleNamespace(fid="real_quark_fid_144"))

    file_id = await service.resolve_media_source_file_id(item_id="item144", media_source_id="mediasource_144")

    assert file_id == "real_quark_fid_144"
    service.quark_service.get_file_by_path.assert_awaited_once_with("流浪地球/movie.mkv")


def test_get_playback_info_when_configured_proxy_base_url_then_uses_dedicated_proxy_url():
    client = _build_emby_client()
    app_config = SimpleNamespace(
        endpoints=[],
        emby=SimpleNamespace(proxy_base_url="http://proxy.example:18097"),
    )

    with (
        patch("app.api.emby.config_service.get_config", return_value=app_config),
        patch("app.api.emby.config.get_quark_cookie", return_value="test-cookie"),
        patch("app.api.emby.EmbyProxyService", _FakeEmbyProxyService),
    ):
        response = client.get(
            "/api/emby/items/item123/PlaybackInfo",
            params={"user_id": "user123"},
            headers={"X-Emby-Token": "emby-api-key"},
        )

    assert response.status_code == 200
    assert response.json()["proxy_base_url"] == "http://proxy.example:18097"
    assert _FakeEmbyProxyService.last_init is not None
    assert _FakeEmbyProxyService.last_init["proxy_base_url"] == "http://proxy.example:18097"


def test_get_playback_info_when_proxy_override_header_present_then_prefers_requested_proxy_base_url():
    client = _build_emby_client()
    app_config = SimpleNamespace(
        endpoints=[],
        emby=SimpleNamespace(proxy_base_url="http://proxy.example:18097"),
    )

    with (
        patch("app.api.emby.config_service.get_config", return_value=app_config),
        patch("app.api.emby.config.get_quark_cookie", return_value="test-cookie"),
        patch("app.api.emby.EmbyProxyService", _FakeEmbyProxyService),
    ):
        response = client.get(
            "/api/emby/items/item123/PlaybackInfo",
            params={"user_id": "user123"},
            headers={
                "X-Emby-Token": "emby-api-key",
                "X-Proxy-Server-Url": "https://public.proxy.example",
            },
        )

    assert response.status_code == 200
    assert response.json()["proxy_base_url"] == "https://public.proxy.example"
    assert _FakeEmbyProxyService.last_init is not None
    assert _FakeEmbyProxyService.last_init["proxy_base_url"] == "https://public.proxy.example"


def test_get_playback_info_when_proxy_override_header_is_invalid_then_returns_400():
    client = _build_emby_client(raise_server_exceptions=False)
    app_config = SimpleNamespace(
        endpoints=[],
        emby=SimpleNamespace(proxy_base_url="http://proxy.example:18097"),
    )

    with (
        patch("app.api.emby.config_service.get_config", return_value=app_config),
        patch("app.api.emby.config.get_quark_cookie", return_value="test-cookie"),
        patch(
            "app.api.emby.EmbyProxyService",
            new=Mock(side_effect=AssertionError("should reject invalid proxy override before proxy service init")),
        ),
    ):
        response = client.get(
            "/api/emby/items/item123/PlaybackInfo",
            params={"user_id": "user123"},
            headers={
                "X-Emby-Token": "emby-api-key",
                "X-Proxy-Server-Url": "not-a-url",
            },
        )

    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid proxy server URL"}


def test_get_playback_info_when_emby_override_header_present_then_prefers_requested_emby_base_url():
    client = _build_emby_client()
    app_config = SimpleNamespace(
        endpoints=[],
        emby=SimpleNamespace(proxy_base_url="http://proxy.example:18097", url="http://emby.example:8096"),
    )

    with (
        patch("app.api.emby.config_service.get_config", return_value=app_config),
        patch("app.api.emby.config.get_quark_cookie", return_value="test-cookie"),
        patch("app.api.emby.EmbyProxyService", _FakeEmbyProxyService),
    ):
        response = client.get(
            "/api/emby/items/item123/PlaybackInfo",
            params={"user_id": "user123"},
            headers={
                "X-Emby-Token": "emby-api-key",
                "X-Emby-Server-Url": "https://alt.emby.example:8920",
            },
        )

    assert response.status_code == 200
    assert _FakeEmbyProxyService.last_init is not None
    assert _FakeEmbyProxyService.last_init["emby_base_url"] == "https://alt.emby.example:8920"


def test_get_playback_info_when_emby_override_header_is_invalid_then_returns_400():
    client = _build_emby_client(raise_server_exceptions=False)
    app_config = SimpleNamespace(
        endpoints=[],
        emby=SimpleNamespace(proxy_base_url="http://proxy.example:18097", url="http://emby.example:8096"),
    )

    with (
        patch("app.api.emby.config_service.get_config", return_value=app_config),
        patch("app.api.emby.config.get_quark_cookie", return_value="test-cookie"),
        patch(
            "app.api.emby.EmbyProxyService",
            new=Mock(side_effect=AssertionError("should reject invalid Emby override before proxy service init")),
        ),
    ):
        response = client.get(
            "/api/emby/items/item123/PlaybackInfo",
            params={"user_id": "user123"},
            headers={
                "X-Emby-Token": "emby-api-key",
                "X-Emby-Server-Url": "not-a-url",
            },
        )

    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid Emby server URL"}


def test_get_playback_info_when_endpoint_emby_url_is_empty_then_falls_back_to_emby_config_url():
    client = _build_emby_client()
    app_config = SimpleNamespace(
        endpoints=[SimpleNamespace(emby_url="")],
        emby=SimpleNamespace(proxy_base_url="http://proxy.example:18097", url="http://emby.example:8096"),
    )

    with (
        patch("app.api.emby.config_service.get_config", return_value=app_config),
        patch("app.api.emby.config.get_quark_cookie", return_value="test-cookie"),
        patch("app.api.emby.EmbyProxyService", _FakeEmbyProxyService),
    ):
        response = client.get(
            "/api/emby/items/item123/PlaybackInfo",
            params={"user_id": "user123"},
            headers={"X-Emby-Token": "emby-api-key"},
        )

    assert response.status_code == 200
    assert _FakeEmbyProxyService.last_init is not None
    assert _FakeEmbyProxyService.last_init["emby_base_url"] == "http://emby.example:8096"


def test_get_playback_info_when_global_and_legacy_emby_urls_both_present_then_prefers_global_emby_url():
    client = _build_emby_client()
    app_config = SimpleNamespace(
        endpoints=[SimpleNamespace(emby_url="http://legacy.emby.example:8096")],
        emby=SimpleNamespace(proxy_base_url="http://proxy.example:18097", url="http://emby.example:8096"),
    )

    with (
        patch("app.api.emby.config_service.get_config", return_value=app_config),
        patch("app.api.emby.config.get_quark_cookie", return_value="test-cookie"),
        patch("app.api.emby.EmbyProxyService", _FakeEmbyProxyService),
    ):
        response = client.get(
            "/api/emby/items/item123/PlaybackInfo",
            params={"user_id": "user123"},
            headers={"X-Emby-Token": "emby-api-key"},
        )

    assert response.status_code == 200
    assert _FakeEmbyProxyService.last_init is not None
    assert _FakeEmbyProxyService.last_init["emby_base_url"] == "http://emby.example:8096"


def test_get_playback_info_when_web_headers_present_then_marks_request_as_web_client():
    client = _build_emby_client()
    app_config = SimpleNamespace(
        endpoints=[],
        emby=SimpleNamespace(proxy_base_url="http://proxy.example:18097"),
    )

    with (
        patch("app.api.emby.config_service.get_config", return_value=app_config),
        patch("app.api.emby.config.get_quark_cookie", return_value="test-cookie"),
        patch("app.api.emby.EmbyProxyService", _FakeEmbyProxyService),
    ):
        response = client.get(
            "/api/emby/items/item123/PlaybackInfo",
            params={"user_id": "user123"},
            headers={
                "X-Emby-Token": "emby-api-key",
                "X-Emby-Client": "Emby Web",
                "X-Emby-Device-Name": "Chrome on Windows",
            },
        )

    assert response.status_code == 200
    assert response.json()["is_web_client"] is True
    assert response.json()["client_name"] == "Emby Web"
    assert response.json()["device_name"] == "Chrome on Windows"
    assert _FakeEmbyProxyService.last_proxy_playback_info_call is not None
    assert _FakeEmbyProxyService.last_proxy_playback_info_call["is_web_client"] is True


def test_get_playback_info_when_media_source_id_sent_as_emby_param_then_forwards_canonical_media_source_id():
    client = _build_emby_client()
    app_config = SimpleNamespace(
        endpoints=[],
        emby=SimpleNamespace(proxy_base_url="http://proxy.example:18097"),
    )

    with (
        patch("app.api.emby.config_service.get_config", return_value=app_config),
        patch("app.api.emby.config.get_quark_cookie", return_value="test-cookie"),
        patch("app.api.emby.EmbyProxyService", _FakeEmbyProxyService),
    ):
        response = client.get(
            "/api/emby/items/item123/PlaybackInfo",
            params={"user_id": "user123", "MediaSourceId": "media_source_1"},
            headers={"X-Emby-Token": "emby-api-key"},
        )

    assert response.status_code == 200
    assert response.json()["media_source_id"] == "media_source_1"
    assert _FakeEmbyProxyService.last_proxy_playback_info_call is not None
    assert _FakeEmbyProxyService.last_proxy_playback_info_call["media_source_id"] == "media_source_1"


def test_get_playback_info_when_user_id_and_legacy_token_use_emby_contract_then_still_proxies_request():
    client = _build_emby_client()
    app_config = SimpleNamespace(
        endpoints=[],
        emby=SimpleNamespace(proxy_base_url="http://proxy.example:18097"),
    )

    with (
        patch("app.api.emby.config_service.get_config", return_value=app_config),
        patch("app.api.emby.config.get_quark_cookie", return_value="test-cookie"),
        patch("app.api.emby.EmbyProxyService", _FakeEmbyProxyService),
    ):
        response = client.get(
            "/api/emby/items/item123/PlaybackInfo",
            params={"UserId": "user123"},
            headers={"X-MediaBrowser-Token": "legacy-emby-api-key"},
        )

    assert response.status_code == 200
    assert response.json()["user_id"] == "user123"
    assert _FakeEmbyProxyService.last_init is not None
    assert _FakeEmbyProxyService.last_init["api_key"] == "legacy-emby-api-key"
    assert _FakeEmbyProxyService.last_proxy_playback_info_call is not None
    assert _FakeEmbyProxyService.last_proxy_playback_info_call["user_id"] == "user123"


def test_get_playback_info_when_native_authorization_header_present_then_uses_emby_auth_context():
    client = _build_emby_client()
    app_config = SimpleNamespace(
        endpoints=[],
        emby=SimpleNamespace(proxy_base_url="http://proxy.example:18097"),
    )

    with (
        patch("app.api.emby.config_service.get_config", return_value=app_config),
        patch("app.api.emby.config.get_quark_cookie", return_value="test-cookie"),
        patch("app.api.emby.EmbyProxyService", _FakeEmbyProxyService),
    ):
        response = client.get(
            "/api/emby/items/item123/PlaybackInfo",
            headers={
                "X-Emby-Authorization": (
                    'MediaBrowser Token="native-emby-api-key", UserId="user123", '
                    'Client="Emby Web", Device="Chrome on Windows"'
                ),
                "User-Agent": "Mozilla/5.0",
            },
        )

    assert response.status_code == 200
    assert response.json()["user_id"] == "user123"
    assert response.json()["client_name"] == "Emby Web"
    assert response.json()["device_name"] == "Chrome on Windows"
    assert response.json()["is_web_client"] is True
    assert _FakeEmbyProxyService.last_init is not None
    assert _FakeEmbyProxyService.last_init["api_key"] == "native-emby-api-key"
    assert _FakeEmbyProxyService.last_proxy_playback_info_call is not None
    assert _FakeEmbyProxyService.last_proxy_playback_info_call["user_id"] == "user123"
    assert _FakeEmbyProxyService.last_proxy_playback_info_call["is_web_client"] is True


def test_get_playback_info_when_request_token_missing_then_falls_back_to_configured_emby_api_key():
    client = _build_emby_client()
    app_config = SimpleNamespace(
        endpoints=[],
        emby=SimpleNamespace(proxy_base_url="http://proxy.example:18097", api_key="configured-emby-api-key"),
    )

    with (
        patch("app.api.emby.config_service.get_config", return_value=app_config),
        patch("app.api.emby.config.get_quark_cookie", return_value="test-cookie"),
        patch("app.api.emby.EmbyProxyService", _FakeEmbyProxyService),
    ):
        response = client.get(
            "/api/emby/items/item123/PlaybackInfo",
            params={"UserId": "user123"},
        )

    assert response.status_code == 200
    assert response.json()["user_id"] == "user123"
    assert _FakeEmbyProxyService.last_init is not None
    assert _FakeEmbyProxyService.last_init["api_key"] == "configured-emby-api-key"


def test_get_playback_info_when_global_api_key_missing_then_falls_back_to_legacy_endpoint_api_key():
    client = _build_emby_client()
    app_config = SimpleNamespace(
        endpoints=[SimpleNamespace(emby_api_key="legacy-endpoint-api-key")],
        emby=SimpleNamespace(proxy_base_url="http://proxy.example:18097", api_key=""),
    )

    with (
        patch("app.api.emby.config_service.get_config", return_value=app_config),
        patch("app.api.emby.config.get_quark_cookie", return_value="test-cookie"),
        patch("app.api.emby.EmbyProxyService", _FakeEmbyProxyService),
    ):
        response = client.get(
            "/api/emby/items/item123/PlaybackInfo",
            params={"UserId": "user123"},
        )

    assert response.status_code == 200
    assert response.json()["user_id"] == "user123"
    assert _FakeEmbyProxyService.last_init is not None
    assert _FakeEmbyProxyService.last_init["api_key"] == "legacy-endpoint-api-key"


def test_get_playback_info_when_native_items_path_used_then_still_hits_local_hook_route():
    client = _build_emby_client()
    app_config = SimpleNamespace(
        endpoints=[],
        emby=SimpleNamespace(proxy_base_url="http://proxy.example:18097"),
    )

    with (
        patch("app.api.emby.config_service.get_config", return_value=app_config),
        patch("app.api.emby.config.get_quark_cookie", return_value="test-cookie"),
        patch("app.api.emby.EmbyProxyService", _FakeEmbyProxyService),
        patch(
            "app.api.emby_gateway._forward_to_emby",
            new=AsyncMock(side_effect=AssertionError("should not fall back to generic upstream forwarding")),
        ),
    ):
        response = client.get(
            "/api/emby/Items/item123/PlaybackInfo",
            params={"UserId": "user123"},
            headers={"X-MediaBrowser-Token": "legacy-emby-api-key"},
        )

    assert response.status_code == 200
    assert response.json()["item_id"] == "item123"
    assert response.json()["user_id"] == "user123"
    assert _FakeEmbyProxyService.last_proxy_playback_info_call is not None
    assert _FakeEmbyProxyService.last_proxy_playback_info_call["item_id"] == "item123"


def test_get_playback_info_when_emby_prefixed_native_path_used_then_still_hits_local_hook_route():
    client = _build_emby_client()
    app_config = SimpleNamespace(
        endpoints=[],
        emby=SimpleNamespace(proxy_base_url="http://proxy.example:18097"),
    )

    with (
        patch("app.api.emby.config_service.get_config", return_value=app_config),
        patch("app.api.emby.config.get_quark_cookie", return_value="test-cookie"),
        patch("app.api.emby.EmbyProxyService", _FakeEmbyProxyService),
        patch(
            "app.api.emby_gateway._forward_to_emby",
            new=AsyncMock(side_effect=AssertionError("should not fall back to generic upstream forwarding")),
        ),
    ):
        response = client.get(
            "/api/emby/emby/Items/item123/PlaybackInfo",
            params={"UserId": "user123"},
            headers={"X-MediaBrowser-Token": "legacy-emby-api-key"},
        )

    assert response.status_code == 200
    assert response.json()["item_id"] == "item123"
    assert response.json()["user_id"] == "user123"
    assert _FakeEmbyProxyService.last_proxy_playback_info_call is not None
    assert _FakeEmbyProxyService.last_proxy_playback_info_call["item_id"] == "item123"


def test_get_playback_info_when_emby_prefixed_lowercase_path_used_then_still_hits_local_hook_route():
    client = _build_emby_client()
    app_config = SimpleNamespace(
        endpoints=[],
        emby=SimpleNamespace(proxy_base_url="http://proxy.example:18097"),
    )

    with (
        patch("app.api.emby.config_service.get_config", return_value=app_config),
        patch("app.api.emby.config.get_quark_cookie", return_value="test-cookie"),
        patch("app.api.emby.EmbyProxyService", _FakeEmbyProxyService),
        patch(
            "app.api.emby_gateway._forward_to_emby",
            new=AsyncMock(side_effect=AssertionError("should not fall back to generic upstream forwarding")),
        ),
    ):
        response = client.get(
            "/api/emby/emby/items/item123/PlaybackInfo",
            params={"UserId": "user123"},
            headers={"X-MediaBrowser-Token": "legacy-emby-api-key"},
        )

    assert response.status_code == 200
    assert response.json()["item_id"] == "item123"
    assert response.json()["user_id"] == "user123"
    assert _FakeEmbyProxyService.last_proxy_playback_info_call is not None
    assert _FakeEmbyProxyService.last_proxy_playback_info_call["item_id"] == "item123"


def test_get_playback_info_when_post_body_uses_emby_contract_then_forwards_payload_to_proxy_service():
    client = _build_emby_client()
    app_config = SimpleNamespace(
        endpoints=[],
        emby=SimpleNamespace(proxy_base_url="http://proxy.example:18097"),
    )

    with (
        patch("app.api.emby.config_service.get_config", return_value=app_config),
        patch("app.api.emby.config.get_quark_cookie", return_value="test-cookie"),
        patch("app.api.emby.EmbyProxyService", _FakeEmbyProxyService),
    ):
        response = client.post(
            "/api/emby/items/item123/PlaybackInfo",
            headers={"X-MediaBrowser-Token": "legacy-emby-api-key"},
            json={
                "UserId": "user123",
                "MediaSourceId": "media_source_1",
                "StartTimeTicks": 0,
                "DeviceProfile": {"Name": "Android TV"},
            },
        )

    assert response.status_code == 200
    assert response.json()["user_id"] == "user123"
    assert response.json()["media_source_id"] == "media_source_1"
    assert response.json()["playback_request"] == {
        "UserId": "user123",
        "MediaSourceId": "media_source_1",
        "StartTimeTicks": 0,
        "DeviceProfile": {"Name": "Android TV"},
    }
    assert _FakeEmbyProxyService.last_init is not None
    assert _FakeEmbyProxyService.last_init["api_key"] == "legacy-emby-api-key"
    assert _FakeEmbyProxyService.last_proxy_playback_info_call is not None
    assert _FakeEmbyProxyService.last_proxy_playback_info_call["playback_request"] == {
        "UserId": "user123",
        "MediaSourceId": "media_source_1",
        "StartTimeTicks": 0,
        "DeviceProfile": {"Name": "Android TV"},
    }


def test_get_playback_info_when_non_web_headers_present_then_keeps_request_as_non_web_client():
    client = _build_emby_client()
    app_config = SimpleNamespace(
        endpoints=[],
        emby=SimpleNamespace(proxy_base_url="http://proxy.example:18097"),
    )

    with (
        patch("app.api.emby.config_service.get_config", return_value=app_config),
        patch("app.api.emby.config.get_quark_cookie", return_value="test-cookie"),
        patch("app.api.emby.EmbyProxyService", _FakeEmbyProxyService),
    ):
        response = client.get(
            "/api/emby/items/item123/PlaybackInfo",
            params={"user_id": "user123"},
            headers={
                "X-Emby-Token": "emby-api-key",
                "X-Emby-Client": "Infuse",
                "X-Emby-Device-Name": "Apple TV",
            },
        )

    assert response.status_code == 200
    assert response.json()["is_web_client"] is False
    assert response.json()["client_name"] == "Infuse"
    assert response.json()["device_name"] == "Apple TV"
    assert _FakeEmbyProxyService.last_proxy_playback_info_call is not None
    assert _FakeEmbyProxyService.last_proxy_playback_info_call["is_web_client"] is False


def test_get_playback_info_when_internal_error_then_does_not_leak_error_detail():
    client = _build_emby_client()
    app_config = SimpleNamespace(
        endpoints=[],
        emby=SimpleNamespace(proxy_base_url="http://proxy.example:18097"),
    )

    with (
        patch("app.api.emby.config_service.get_config", return_value=app_config),
        patch("app.api.emby.config.get_quark_cookie", return_value="test-cookie"),
        patch("app.api.emby.EmbyProxyService") as mock_emby_proxy_service_cls,
    ):
        mock_playback_hook = SimpleNamespace(
            hook_playback_info=AsyncMock(side_effect=RuntimeError("internal secret path"))
        )
        mock_emby_proxy_service_cls.return_value.__aenter__.return_value = SimpleNamespace(playback_hook=mock_playback_hook)
        mock_emby_proxy_service_cls.return_value.__aexit__.return_value = None

        response = client.get(
            "/api/emby/items/item123/PlaybackInfo",
            params={"user_id": "user123"},
            headers={"X-Emby-Token": "emby-api-key"},
        )

    assert response.status_code == 500
    assert response.json() == {"detail": "Failed to get playback info"}


def test_get_item_when_user_id_legacy_token_and_emby_url_fallback_use_emby_contract_then_proxies_item_request():
    client = _build_emby_client()
    app_config = SimpleNamespace(
        endpoints=[SimpleNamespace(emby_url="")],
        emby=SimpleNamespace(url="http://emby.example:8096", proxy_base_url="http://proxy.example:18097"),
    )

    with (
        patch("app.api.emby.config_service.get_config", return_value=app_config),
        patch("app.api.emby.config.get_quark_cookie", return_value="test-cookie"),
        patch("app.api.emby.EmbyProxyService") as mock_emby_proxy_service_cls,
    ):
        mock_emby_proxy_service = AsyncMock()
        mock_emby_proxy_service.proxy_items_request = AsyncMock(
            return_value={"item_id": "item123", "user_id": "user123", "source": "proxy"}
        )
        mock_emby_proxy_service_cls.return_value.__aenter__.return_value = mock_emby_proxy_service
        mock_emby_proxy_service_cls.return_value.__aexit__.return_value = None

        response = client.get(
            "/api/emby/items/item123",
            params={"UserId": "user123"},
            headers={"X-MediaBrowser-Token": "legacy-emby-api-key"},
        )

    assert response.status_code == 200
    assert response.json() == {"item_id": "item123", "user_id": "user123", "source": "proxy"}
    assert mock_emby_proxy_service_cls.call_args.kwargs["emby_base_url"] == "http://emby.example:8096"
    assert mock_emby_proxy_service_cls.call_args.kwargs["api_key"] == "legacy-emby-api-key"
    mock_emby_proxy_service.proxy_items_request.assert_awaited_once_with(item_id="item123", user_id="user123")


def test_get_item_when_native_authorization_header_present_then_uses_emby_auth_context():
    client = _build_emby_client()
    app_config = SimpleNamespace(
        endpoints=[],
        emby=SimpleNamespace(url="http://emby.example:8096", proxy_base_url="http://proxy.example:18097"),
    )

    with (
        patch("app.api.emby.config_service.get_config", return_value=app_config),
        patch("app.api.emby.config.get_quark_cookie", return_value="test-cookie"),
        patch("app.api.emby.EmbyProxyService") as mock_emby_proxy_service_cls,
    ):
        mock_emby_proxy_service = AsyncMock()
        mock_emby_proxy_service.proxy_items_request = AsyncMock(
            return_value={"item_id": "item123", "user_id": "user123", "source": "proxy"}
        )
        mock_emby_proxy_service_cls.return_value.__aenter__.return_value = mock_emby_proxy_service
        mock_emby_proxy_service_cls.return_value.__aexit__.return_value = None

        response = client.get(
            "/api/emby/items/item123",
            headers={"Authorization": 'Emby Token="native-emby-api-key", UserId="user123"'},
        )

    assert response.status_code == 200
    assert response.json() == {"item_id": "item123", "user_id": "user123", "source": "proxy"}
    assert mock_emby_proxy_service_cls.call_args.kwargs["api_key"] == "native-emby-api-key"
    mock_emby_proxy_service.proxy_items_request.assert_awaited_once_with(item_id="item123", user_id="user123")


def test_get_item_when_emby_override_header_is_invalid_then_returns_400():
    client = _build_emby_client(raise_server_exceptions=False)
    app_config = SimpleNamespace(
        endpoints=[],
        emby=SimpleNamespace(url="http://emby.example:8096", proxy_base_url="http://proxy.example:18097"),
    )

    with (
        patch("app.api.emby.config_service.get_config", return_value=app_config),
        patch("app.api.emby.config.get_quark_cookie", return_value="test-cookie"),
        patch(
            "app.api.emby.EmbyProxyService",
            new=Mock(side_effect=AssertionError("should reject invalid Emby override before proxy service init")),
        ),
    ):
        response = client.get(
            "/api/emby/items/item123",
            params={"UserId": "user123"},
            headers={
                "X-MediaBrowser-Token": "legacy-emby-api-key",
                "X-Emby-Server-Url": "not-a-url",
            },
        )

    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid Emby server URL"}


def test_get_item_when_request_token_missing_then_falls_back_to_configured_emby_api_key():
    client = _build_emby_client()
    app_config = SimpleNamespace(
        endpoints=[SimpleNamespace(emby_url="")],
        emby=SimpleNamespace(
            url="http://emby.example:8096",
            proxy_base_url="http://proxy.example:18097",
            api_key="configured-emby-api-key",
        ),
    )

    with (
        patch("app.api.emby.config_service.get_config", return_value=app_config),
        patch("app.api.emby.config.get_quark_cookie", return_value="test-cookie"),
        patch("app.api.emby.EmbyProxyService") as mock_emby_proxy_service_cls,
    ):
        mock_emby_proxy_service = AsyncMock()
        mock_emby_proxy_service.proxy_items_request = AsyncMock(
            return_value={"item_id": "item123", "user_id": "user123", "source": "proxy"}
        )
        mock_emby_proxy_service_cls.return_value.__aenter__.return_value = mock_emby_proxy_service
        mock_emby_proxy_service_cls.return_value.__aexit__.return_value = None

        response = client.get(
            "/api/emby/items/item123",
            params={"UserId": "user123"},
        )

    assert response.status_code == 200
    assert response.json() == {"item_id": "item123", "user_id": "user123", "source": "proxy"}
    assert mock_emby_proxy_service_cls.call_args.kwargs["api_key"] == "configured-emby-api-key"
    mock_emby_proxy_service.proxy_items_request.assert_awaited_once_with(item_id="item123", user_id="user123")


def test_get_item_when_native_items_path_used_then_still_hits_local_item_route():
    client = _build_emby_client()
    app_config = SimpleNamespace(
        endpoints=[SimpleNamespace(emby_url="")],
        emby=SimpleNamespace(url="http://emby.example:8096", proxy_base_url="http://proxy.example:18097"),
    )

    with (
        patch("app.api.emby.config_service.get_config", return_value=app_config),
        patch("app.api.emby.config.get_quark_cookie", return_value="test-cookie"),
        patch("app.api.emby.EmbyProxyService") as mock_emby_proxy_service_cls,
        patch(
            "app.api.emby_gateway._forward_to_emby",
            new=AsyncMock(side_effect=AssertionError("should not fall back to generic upstream forwarding")),
        ),
    ):
        mock_emby_proxy_service = AsyncMock()
        mock_emby_proxy_service.proxy_items_request = AsyncMock(
            return_value={"item_id": "item123", "user_id": "user123", "source": "proxy"}
        )
        mock_emby_proxy_service_cls.return_value.__aenter__.return_value = mock_emby_proxy_service
        mock_emby_proxy_service_cls.return_value.__aexit__.return_value = None

        response = client.get(
            "/api/emby/Items/item123",
            params={"UserId": "user123"},
            headers={"X-MediaBrowser-Token": "legacy-emby-api-key"},
        )

    assert response.status_code == 200
    assert response.json() == {"item_id": "item123", "user_id": "user123", "source": "proxy"}
    mock_emby_proxy_service.proxy_items_request.assert_awaited_once_with(item_id="item123", user_id="user123")


def test_get_item_when_emby_prefixed_native_path_used_then_still_hits_local_item_route():
    client = _build_emby_client()
    app_config = SimpleNamespace(
        endpoints=[SimpleNamespace(emby_url="")],
        emby=SimpleNamespace(url="http://emby.example:8096", proxy_base_url="http://proxy.example:18097"),
    )

    with (
        patch("app.api.emby.config_service.get_config", return_value=app_config),
        patch("app.api.emby.config.get_quark_cookie", return_value="test-cookie"),
        patch("app.api.emby.EmbyProxyService") as mock_emby_proxy_service_cls,
        patch(
            "app.api.emby_gateway._forward_to_emby",
            new=AsyncMock(side_effect=AssertionError("should not fall back to generic upstream forwarding")),
        ),
    ):
        mock_emby_proxy_service = AsyncMock()
        mock_emby_proxy_service.proxy_items_request = AsyncMock(
            return_value={"item_id": "item123", "user_id": "user123", "source": "proxy"}
        )
        mock_emby_proxy_service_cls.return_value.__aenter__.return_value = mock_emby_proxy_service
        mock_emby_proxy_service_cls.return_value.__aexit__.return_value = None

        response = client.get(
            "/api/emby/emby/Items/item123",
            params={"UserId": "user123"},
            headers={"X-MediaBrowser-Token": "legacy-emby-api-key"},
        )

    assert response.status_code == 200
    assert response.json() == {"item_id": "item123", "user_id": "user123", "source": "proxy"}
    mock_emby_proxy_service.proxy_items_request.assert_awaited_once_with(item_id="item123", user_id="user123")


def test_get_item_when_emby_prefixed_lowercase_path_used_then_still_hits_local_item_route():
    client = _build_emby_client()
    app_config = SimpleNamespace(
        endpoints=[SimpleNamespace(emby_url="")],
        emby=SimpleNamespace(url="http://emby.example:8096", proxy_base_url="http://proxy.example:18097"),
    )

    with (
        patch("app.api.emby.config_service.get_config", return_value=app_config),
        patch("app.api.emby.config.get_quark_cookie", return_value="test-cookie"),
        patch("app.api.emby.EmbyProxyService") as mock_emby_proxy_service_cls,
        patch(
            "app.api.emby_gateway._forward_to_emby",
            new=AsyncMock(side_effect=AssertionError("should not fall back to generic upstream forwarding")),
        ),
    ):
        mock_emby_proxy_service = AsyncMock()
        mock_emby_proxy_service.proxy_items_request = AsyncMock(
            return_value={"item_id": "item123", "user_id": "user123", "source": "proxy"}
        )
        mock_emby_proxy_service_cls.return_value.__aenter__.return_value = mock_emby_proxy_service
        mock_emby_proxy_service_cls.return_value.__aexit__.return_value = None

        response = client.get(
            "/api/emby/emby/items/item123",
            params={"UserId": "user123"},
            headers={"X-MediaBrowser-Token": "legacy-emby-api-key"},
        )

    assert response.status_code == 200
    assert response.json() == {"item_id": "item123", "user_id": "user123", "source": "proxy"}
    mock_emby_proxy_service.proxy_items_request.assert_awaited_once_with(item_id="item123", user_id="user123")


def test_get_item_when_internal_error_then_does_not_leak_error_detail():
    client = _build_emby_client()
    app_config = SimpleNamespace(
        endpoints=[SimpleNamespace(emby_url="")],
        emby=SimpleNamespace(url="http://emby.example:8096", proxy_base_url="http://proxy.example:18097"),
    )

    with (
        patch("app.api.emby.config_service.get_config", return_value=app_config),
        patch("app.api.emby.config.get_quark_cookie", return_value="test-cookie"),
        patch("app.api.emby.EmbyProxyService") as mock_emby_proxy_service_cls,
    ):
        mock_emby_proxy_service = AsyncMock()
        mock_emby_proxy_service.proxy_items_request = AsyncMock(side_effect=RuntimeError("internal secret path"))
        mock_emby_proxy_service_cls.return_value.__aenter__.return_value = mock_emby_proxy_service
        mock_emby_proxy_service_cls.return_value.__aexit__.return_value = None

        response = client.get(
            "/api/emby/items/item123",
            params={"UserId": "user123"},
            headers={"X-MediaBrowser-Token": "legacy-emby-api-key"},
        )

    assert response.status_code == 500
    assert response.json() == {"detail": "Failed to get item info"}


def test_proxy_emby_request_when_head_and_endpoint_url_empty_then_reuses_gateway_forwarder_with_emby_url_fallback():
    client = _build_emby_client()
    app_config = SimpleNamespace(
        endpoints=[SimpleNamespace(emby_url="")],
        emby=SimpleNamespace(url="http://emby.example:8096"),
    )

    with (
        patch("app.api.emby.config_service.get_config", return_value=app_config),
        patch(
            "app.api.emby_gateway._forward_to_emby",
            new=AsyncMock(
                return_value=Response(
                    content=b"",
                    status_code=200,
                    media_type="application/json",
                    headers={"Content-Length": "2"},
                )
            ),
        ) as mock_forward,
    ):
        response = client.head("/api/emby/System/Info/Public")

    assert response.status_code == 200
    assert response.content == b""
    assert mock_forward.await_args.args[1] is app_config
    assert mock_forward.await_args.args[2] == "System/Info/Public"


def test_proxy_emby_request_when_proxy_override_header_present_then_passes_proxy_base_url_to_gateway_forwarder():
    client = _build_emby_client()
    app_config = SimpleNamespace(
        endpoints=[SimpleNamespace(emby_url="")],
        emby=SimpleNamespace(url="http://emby.example:8096", proxy_base_url="http://proxy.internal:18097"),
    )

    with (
        patch("app.api.emby.config_service.get_config", return_value=app_config),
        patch(
            "app.api.emby_gateway._forward_to_emby",
            new=AsyncMock(
                return_value=Response(
                    content=b'{"ok":true}',
                    status_code=200,
                    media_type="application/json",
                )
            ),
        ) as mock_forward,
    ):
        response = client.get(
            "/api/emby/System/Info/Public",
            headers={"X-Proxy-Server-Url": "https://public.proxy.example"},
        )

    assert response.status_code == 200
    assert mock_forward.await_args.kwargs["proxy_base_url"] == "https://public.proxy.example"


def test_proxy_emby_request_when_proxy_override_header_is_invalid_then_returns_400():
    client = _build_emby_client(raise_server_exceptions=False)
    app_config = SimpleNamespace(
        endpoints=[SimpleNamespace(emby_url="")],
        emby=SimpleNamespace(url="http://emby.example:8096", proxy_base_url="http://proxy.internal:18097"),
    )

    with patch("app.api.emby.config_service.get_config", return_value=app_config):
        response = client.get(
            "/api/emby/System/Info/Public",
            headers={"X-Proxy-Server-Url": "not-a-url"},
        )

    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid proxy server URL"}


def test_proxy_emby_request_when_emby_override_header_uses_blocked_hostname_then_returns_400():
    client = _build_emby_client()
    app_config = SimpleNamespace(
        endpoints=[SimpleNamespace(emby_url="")],
        emby=SimpleNamespace(url="http://emby.example:8096"),
    )

    with (
        patch("app.api.emby.config_service.get_config", return_value=app_config),
        patch(
            "app.api.emby_gateway._forward_to_emby",
            new=AsyncMock(side_effect=AssertionError("should reject blocked Emby override before forwarding")),
        ),
    ):
        response = client.get(
            "/api/emby/System/Info/Public",
            headers={"X-Emby-Server-Url": "http://localhost:8096"},
        )

    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid Emby server URL"}


def test_proxy_emby_request_when_emby_override_header_is_invalid_then_returns_400():
    client = _build_emby_client(raise_server_exceptions=False)
    app_config = SimpleNamespace(
        endpoints=[SimpleNamespace(emby_url="")],
        emby=SimpleNamespace(url="http://emby.example:8096"),
    )

    with (
        patch("app.api.emby.config_service.get_config", return_value=app_config),
        patch(
            "app.api.emby_gateway._forward_to_emby",
            new=AsyncMock(side_effect=AssertionError("should reject invalid Emby override before forwarding")),
        ),
    ):
        response = client.get(
            "/api/emby/System/Info/Public",
            headers={"X-Emby-Server-Url": "not-a-url"},
        )

    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid Emby server URL"}


def test_proxy_emby_request_when_emby_override_header_present_then_validates_override_url_once():
    client = _build_emby_client()
    app_config = SimpleNamespace(
        endpoints=[SimpleNamespace(emby_url="")],
        emby=SimpleNamespace(url="http://emby.example:8096"),
    )

    with (
        patch("app.api.emby.config_service.get_config", return_value=app_config),
        patch("app.api.emby.emby_validator.validate") as mock_validate,
        patch(
            "app.api.emby_gateway._forward_to_emby",
            new=AsyncMock(
                return_value=Response(
                    content=b'{"ok":true}',
                    status_code=200,
                    media_type="application/json",
                )
            ),
        ),
    ):
        response = client.get(
            "/api/emby/System/Info/Public",
            headers={"X-Emby-Server-Url": "https://alt.emby.example:8920/base"},
        )

    assert response.status_code == 200
    mock_validate.assert_called_once_with("https://alt.emby.example:8920/base")


def test_proxy_emby_request_when_internal_error_then_does_not_leak_error_detail():
    client = _build_emby_client()
    app_config = SimpleNamespace(
        endpoints=[SimpleNamespace(emby_url="")],
        emby=SimpleNamespace(url="http://emby.example:8096"),
    )

    with (
        patch("app.api.emby.config_service.get_config", return_value=app_config),
        patch(
            "app.api.emby_gateway._forward_to_emby",
            new=AsyncMock(side_effect=RuntimeError("internal secret path")),
        ),
    ):
        response = client.get("/api/emby/System/Info/Public")

    assert response.status_code == 500
    assert response.json() == {"detail": "Failed to proxy Emby request"}


def test_proxy_emby_request_when_gateway_forward_raises_502_then_passes_through():
    client = _build_emby_client()
    app_config = SimpleNamespace(
        endpoints=[SimpleNamespace(emby_url="")],
        emby=SimpleNamespace(url="http://emby.example:8096"),
    )

    with (
        patch("app.api.emby.config_service.get_config", return_value=app_config),
        patch(
            "app.api.emby_gateway._forward_to_emby",
            new=AsyncMock(side_effect=HTTPException(status_code=502, detail="Failed to proxy Emby request")),
        ),
    ):
        response = client.get("/api/emby/System/Info/Public")

    assert response.status_code == 502
    assert response.json() == {"detail": "Failed to proxy Emby request"}


def test_proxy_router_emby_request_when_endpoint_url_empty_then_reuses_gateway_forwarder_with_emby_url_fallback():
    client = _build_proxy_client()
    app_config = SimpleNamespace(
        endpoints=[SimpleNamespace(emby_url="")],
        emby=SimpleNamespace(url="http://emby.example:8096"),
    )

    with (
        patch("app.api.proxy.config_service.get_config", return_value=app_config),
        patch(
            "app.api.emby_gateway._forward_to_emby",
            new=AsyncMock(
                return_value=Response(
                    content=b'{"ok":true}',
                    status_code=200,
                    media_type="application/json",
                )
            ),
        ) as mock_forward,
    ):
        response = client.get("/api/proxy/emby/System/Info/Public")

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert mock_forward.await_args.args[1] is app_config
    assert mock_forward.await_args.args[2] == "System/Info/Public"


def test_proxy_router_emby_request_when_emby_override_header_present_then_validates_override_url():
    client = _build_proxy_client()
    app_config = SimpleNamespace(
        endpoints=[SimpleNamespace(emby_url="")],
        emby=SimpleNamespace(url="http://emby.example:8096"),
    )

    with (
        patch("app.api.proxy.config_service.get_config", return_value=app_config),
        patch("app.api.proxy.emby_validator.validate") as mock_validate,
        patch(
            "app.api.emby_gateway._forward_to_emby",
            new=AsyncMock(
                return_value=Response(
                    content=b'{"ok":true}',
                    status_code=200,
                    media_type="application/json",
                )
            ),
        ),
    ):
        response = client.get(
            "/api/proxy/emby/System/Info/Public",
            headers={"X-Emby-Server-Url": "https://alt.emby.example:8920/base"},
        )

    assert response.status_code == 200
    mock_validate.assert_called_once_with("https://alt.emby.example:8920/base")


def test_proxy_router_emby_request_when_proxy_override_header_present_then_passes_proxy_base_url_to_gateway_forwarder():
    client = _build_proxy_client()
    app_config = SimpleNamespace(
        endpoints=[SimpleNamespace(emby_url="")],
        emby=SimpleNamespace(url="http://emby.example:8096", proxy_base_url="http://proxy.internal:18097"),
    )

    with (
        patch("app.api.proxy.config_service.get_config", return_value=app_config),
        patch(
            "app.api.emby_gateway._forward_to_emby",
            new=AsyncMock(
                return_value=Response(
                    content=b'{"ok":true}',
                    status_code=200,
                    media_type="application/json",
                )
            ),
        ) as mock_forward,
    ):
        response = client.get(
            "/api/proxy/emby/System/Info/Public",
            headers={"X-Proxy-Server-Url": "https://public.proxy.example"},
        )

    assert response.status_code == 200
    assert mock_forward.await_args.kwargs["proxy_base_url"] == "https://public.proxy.example"


def test_proxy_router_emby_request_when_proxy_override_header_is_invalid_then_returns_400():
    client = _build_proxy_client(raise_server_exceptions=False)
    app_config = SimpleNamespace(
        endpoints=[SimpleNamespace(emby_url="")],
        emby=SimpleNamespace(url="http://emby.example:8096", proxy_base_url="http://proxy.internal:18097"),
    )

    with patch("app.api.proxy.config_service.get_config", return_value=app_config):
        response = client.get(
            "/api/proxy/emby/System/Info/Public",
            headers={"X-Proxy-Server-Url": "not-a-url"},
        )

    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid proxy server URL"}


def test_proxy_router_emby_request_when_emby_override_header_uses_blocked_hostname_then_returns_400():
    client = _build_proxy_client()
    app_config = SimpleNamespace(
        endpoints=[SimpleNamespace(emby_url="")],
        emby=SimpleNamespace(url="http://emby.example:8096"),
    )

    with (
        patch("app.api.proxy.config_service.get_config", return_value=app_config),
        patch(
            "app.api.emby_gateway._forward_to_emby",
            new=AsyncMock(side_effect=AssertionError("should reject blocked Emby override before forwarding")),
        ),
    ):
        response = client.get(
            "/api/proxy/emby/System/Info/Public",
            headers={"X-Emby-Server-Url": "http://localhost:8096"},
        )

    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid Emby server URL"}


def test_proxy_router_emby_request_when_emby_override_header_is_invalid_then_returns_400():
    client = _build_proxy_client(raise_server_exceptions=False)
    app_config = SimpleNamespace(
        endpoints=[SimpleNamespace(emby_url="")],
        emby=SimpleNamespace(url="http://emby.example:8096"),
    )

    with (
        patch("app.api.proxy.config_service.get_config", return_value=app_config),
        patch(
            "app.api.emby_gateway._forward_to_emby",
            new=AsyncMock(side_effect=AssertionError("should reject invalid Emby override before forwarding")),
        ),
    ):
        response = client.get(
            "/api/proxy/emby/System/Info/Public",
            headers={"X-Emby-Server-Url": "not-a-url"},
        )

    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid Emby server URL"}


def test_proxy_router_emby_request_when_internal_error_then_does_not_leak_error_detail():
    client = _build_proxy_client()
    app_config = SimpleNamespace(
        endpoints=[SimpleNamespace(emby_url="")],
        emby=SimpleNamespace(url="http://emby.example:8096"),
    )

    with (
        patch("app.api.proxy.config_service.get_config", return_value=app_config),
        patch(
            "app.api.emby_gateway._forward_to_emby",
            new=AsyncMock(side_effect=RuntimeError("internal secret path")),
        ),
    ):
        response = client.get("/api/proxy/emby/System/Info/Public")

    assert response.status_code == 500
    assert response.json() == {"detail": "Failed to proxy Emby request"}


def test_proxy_router_emby_request_when_gateway_forward_raises_504_then_passes_through():
    client = _build_proxy_client()
    app_config = SimpleNamespace(
        endpoints=[SimpleNamespace(emby_url="")],
        emby=SimpleNamespace(url="http://emby.example:8096"),
    )

    with (
        patch("app.api.proxy.config_service.get_config", return_value=app_config),
        patch(
            "app.api.emby_gateway._forward_to_emby",
            new=AsyncMock(side_effect=HTTPException(status_code=504, detail="Emby upstream timeout")),
        ),
    ):
        response = client.get("/api/proxy/emby/System/Info/Public")

    assert response.status_code == 504
    assert response.json() == {"detail": "Emby upstream timeout"}


def test_stream_video_when_media_source_id_is_not_file_id_then_resolves_item_media_source_and_returns_stream_response():
    client = _build_emby_client()
    app_config = SimpleNamespace(
        endpoints=[],
        emby=SimpleNamespace(proxy_base_url="http://proxy.example:18097"),
    )

    with (
        patch("app.api.emby.config_service.get_config", return_value=app_config),
        patch("app.api.emby.config.get_quark_cookie", return_value="test-cookie"),
        patch("app.api.emby.EmbyProxyService") as mock_emby_proxy_service_cls,
        patch(
            "app.api.emby.proxy_stream_by_file_id",
            new=AsyncMock(return_value=Response(content=b"stream-body", media_type="video/mp4", status_code=200)),
        ) as mock_proxy_stream,
    ):
        mock_emby_proxy_service = AsyncMock()
        mock_emby_proxy_service.resolve_media_source_file_id = AsyncMock(return_value="file123")
        mock_emby_proxy_service_cls.return_value.__aenter__.return_value = mock_emby_proxy_service
        mock_emby_proxy_service_cls.return_value.__aexit__.return_value = None

        response = client.get(
            "/api/emby/videos/item123/stream",
            params={"media_source_id": "media_source_1", "static": "true", "container": "mkv"},
            follow_redirects=False,
        )

    assert response.status_code == 200
    assert response.content == b"stream-body"
    mock_emby_proxy_service.resolve_media_source_file_id.assert_awaited_once_with(
        item_id="item123", media_source_id="media_source_1"
    )
    mock_proxy_stream.assert_awaited_once()


def test_stream_video_when_emby_override_header_is_invalid_then_returns_400():
    client = _build_emby_client(raise_server_exceptions=False)
    app_config = SimpleNamespace(
        endpoints=[],
        emby=SimpleNamespace(proxy_base_url="http://proxy.example:18097", url="http://emby.example:8096"),
    )

    with (
        patch("app.api.emby.config_service.get_config", return_value=app_config),
        patch("app.api.emby.config.get_quark_cookie", return_value="test-cookie"),
        patch(
            "app.api.emby.EmbyProxyService",
            new=Mock(side_effect=AssertionError("should reject invalid Emby override before proxy service init")),
        ),
    ):
        response = client.get(
            "/api/emby/videos/item123/stream",
            params={"media_source_id": "media_source_1"},
            headers={
                "X-Emby-Token": "emby-api-key",
                "X-Emby-Server-Url": "not-a-url",
            },
            follow_redirects=False,
        )

    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid Emby server URL"}


def test_stream_video_when_container_suffix_requested_then_handles_locally():
    client = _build_emby_client()
    app_config = SimpleNamespace(
        endpoints=[],
        emby=SimpleNamespace(proxy_base_url="http://proxy.example:18097"),
    )

    with (
        patch("app.api.emby.config_service.get_config", return_value=app_config),
        patch("app.api.emby.config.get_quark_cookie", return_value="test-cookie"),
        patch("app.api.emby.EmbyProxyService") as mock_emby_proxy_service_cls,
        patch(
            "app.api.emby.proxy_stream_by_file_id",
            new=AsyncMock(return_value=Response(content=b"stream-body", media_type="video/mp4", status_code=200)),
        ) as mock_proxy_stream,
    ):
        mock_emby_proxy_service = AsyncMock()
        mock_emby_proxy_service.resolve_media_source_file_id = AsyncMock(return_value="file123")
        mock_emby_proxy_service_cls.return_value.__aenter__.return_value = mock_emby_proxy_service
        mock_emby_proxy_service_cls.return_value.__aexit__.return_value = None

        response = client.get(
            "/api/emby/videos/item123/stream.mkv",
            params={"media_source_id": "media_source_1", "static": "true"},
            follow_redirects=False,
        )

    assert response.status_code == 200
    assert response.content == b"stream-body"
    mock_emby_proxy_service.resolve_media_source_file_id.assert_awaited_once_with(
        item_id="item123", media_source_id="media_source_1"
    )
    mock_proxy_stream.assert_awaited_once()


def test_stream_video_when_native_videos_path_used_then_handles_locally():
    client = _build_emby_client()
    app_config = SimpleNamespace(
        endpoints=[],
        emby=SimpleNamespace(proxy_base_url="http://proxy.example:18097"),
    )

    with (
        patch("app.api.emby.config_service.get_config", return_value=app_config),
        patch("app.api.emby.config.get_quark_cookie", return_value="test-cookie"),
        patch("app.api.emby.EmbyProxyService") as mock_emby_proxy_service_cls,
        patch(
            "app.api.emby.proxy_stream_by_file_id",
            new=AsyncMock(return_value=Response(content=b"stream-body", media_type="video/mp4", status_code=200)),
        ) as mock_proxy_stream,
        patch(
            "app.api.emby_gateway._forward_to_emby",
            new=AsyncMock(side_effect=AssertionError("should not fall back to generic upstream forwarding")),
        ),
    ):
        mock_emby_proxy_service = AsyncMock()
        mock_emby_proxy_service.resolve_media_source_file_id = AsyncMock(return_value="file123")
        mock_emby_proxy_service_cls.return_value.__aenter__.return_value = mock_emby_proxy_service
        mock_emby_proxy_service_cls.return_value.__aexit__.return_value = None

        response = client.get(
            "/api/emby/Videos/item123/stream.mkv",
            params={"media_source_id": "media_source_1", "static": "true"},
            follow_redirects=False,
        )

    assert response.status_code == 200
    assert response.content == b"stream-body"
    mock_emby_proxy_service.resolve_media_source_file_id.assert_awaited_once_with(
        item_id="item123", media_source_id="media_source_1"
    )
    mock_proxy_stream.assert_awaited_once()


def test_stream_video_when_emby_prefixed_native_path_used_then_handles_locally():
    client = _build_emby_client()
    app_config = SimpleNamespace(
        endpoints=[],
        emby=SimpleNamespace(proxy_base_url="http://proxy.example:18097"),
    )

    with (
        patch("app.api.emby.config_service.get_config", return_value=app_config),
        patch("app.api.emby.config.get_quark_cookie", return_value="test-cookie"),
        patch("app.api.emby.EmbyProxyService") as mock_emby_proxy_service_cls,
        patch(
            "app.api.emby.proxy_stream_by_file_id",
            new=AsyncMock(return_value=Response(content=b"stream-body", media_type="video/mp4", status_code=200)),
        ) as mock_proxy_stream,
        patch(
            "app.api.emby_gateway._forward_to_emby",
            new=AsyncMock(side_effect=AssertionError("should not fall back to generic upstream forwarding")),
        ),
    ):
        mock_emby_proxy_service = AsyncMock()
        mock_emby_proxy_service.resolve_media_source_file_id = AsyncMock(return_value="file123")
        mock_emby_proxy_service_cls.return_value.__aenter__.return_value = mock_emby_proxy_service
        mock_emby_proxy_service_cls.return_value.__aexit__.return_value = None

        response = client.get(
            "/api/emby/emby/Videos/item123/stream.mkv",
            params={"media_source_id": "media_source_1", "static": "true"},
            follow_redirects=False,
        )

    assert response.status_code == 200
    assert response.content == b"stream-body"
    mock_emby_proxy_service.resolve_media_source_file_id.assert_awaited_once_with(
        item_id="item123", media_source_id="media_source_1"
    )
    mock_proxy_stream.assert_awaited_once()


def test_stream_video_when_emby_prefixed_lowercase_path_used_then_handles_locally():
    client = _build_emby_client()
    app_config = SimpleNamespace(
        endpoints=[],
        emby=SimpleNamespace(proxy_base_url="http://proxy.example:18097"),
    )

    with (
        patch("app.api.emby.config_service.get_config", return_value=app_config),
        patch("app.api.emby.config.get_quark_cookie", return_value="test-cookie"),
        patch("app.api.emby.EmbyProxyService") as mock_emby_proxy_service_cls,
        patch(
            "app.api.emby.proxy_stream_by_file_id",
            new=AsyncMock(return_value=Response(content=b"stream-body", media_type="video/mp4", status_code=200)),
        ) as mock_proxy_stream,
        patch(
            "app.api.emby_gateway._forward_to_emby",
            new=AsyncMock(side_effect=AssertionError("should not fall back to generic upstream forwarding")),
        ),
    ):
        mock_emby_proxy_service = AsyncMock()
        mock_emby_proxy_service.resolve_media_source_file_id = AsyncMock(return_value="file123")
        mock_emby_proxy_service_cls.return_value.__aenter__.return_value = mock_emby_proxy_service
        mock_emby_proxy_service_cls.return_value.__aexit__.return_value = None

        response = client.get(
            "/api/emby/emby/videos/item123/stream.mkv",
            params={"media_source_id": "media_source_1", "static": "true"},
            follow_redirects=False,
        )

    assert response.status_code == 200
    assert response.content == b"stream-body"
    mock_emby_proxy_service.resolve_media_source_file_id.assert_awaited_once_with(
        item_id="item123", media_source_id="media_source_1"
    )
    mock_proxy_stream.assert_awaited_once()


def test_stream_video_when_legacy_token_header_present_then_uses_it_for_media_source_resolution():
    client = _build_emby_client()
    app_config = SimpleNamespace(
        endpoints=[],
        emby=SimpleNamespace(proxy_base_url="http://proxy.example:18097"),
    )

    with (
        patch("app.api.emby.config_service.get_config", return_value=app_config),
        patch("app.api.emby.config.get_quark_cookie", return_value="test-cookie"),
        patch("app.api.emby.EmbyProxyService") as mock_emby_proxy_service_cls,
        patch(
            "app.api.emby.proxy_stream_by_file_id",
            new=AsyncMock(return_value=Response(content=b"stream-body", media_type="video/mp4", status_code=200)),
        ),
    ):
        mock_emby_proxy_service = AsyncMock()
        mock_emby_proxy_service.resolve_media_source_file_id = AsyncMock(return_value="file123")
        mock_emby_proxy_service_cls.return_value.__aenter__.return_value = mock_emby_proxy_service
        mock_emby_proxy_service_cls.return_value.__aexit__.return_value = None

        response = client.get(
            "/api/emby/videos/item123/stream",
            params={"MediaSourceId": "media_source_1", "static": "true"},
            headers={"X-MediaBrowser-Token": "legacy-emby-api-key"},
            follow_redirects=False,
        )

    assert response.status_code == 200
    assert mock_emby_proxy_service_cls.call_args is not None
    assert mock_emby_proxy_service_cls.call_args.kwargs["api_key"] == "legacy-emby-api-key"
    mock_emby_proxy_service.resolve_media_source_file_id.assert_awaited_once_with(
        item_id="item123", media_source_id="media_source_1"
    )


def test_get_master_playlist_when_media_source_id_is_not_file_id_then_resolves_item_media_source_and_returns_proxy_transcoding_playlist():
    client = _build_emby_client()
    app_config = SimpleNamespace(
        endpoints=[],
        emby=SimpleNamespace(proxy_base_url="http://proxy.example:18097"),
    )

    with (
        patch("app.api.emby.config_service.get_config", return_value=app_config),
        patch("app.api.emby.config.get_quark_cookie", return_value="test-cookie"),
        patch("app.api.emby.EmbyProxyService") as mock_emby_proxy_service_cls,
    ):
        mock_emby_proxy_service = AsyncMock()
        mock_emby_proxy_service.resolve_media_source_file_id = AsyncMock(return_value="file123")
        mock_emby_proxy_service_cls.return_value.__aenter__.return_value = mock_emby_proxy_service
        mock_emby_proxy_service_cls.return_value.__aexit__.return_value = None

        response = client.get(
            "/api/emby/videos/item123/master.m3u8",
            params={"MediaSourceId": "media_source_1", "api_key": "emby-api-key"},
        )

    assert response.status_code == 200
    assert response.headers["Content-Type"].startswith("application/vnd.apple.mpegurl")
    assert "/api/proxy/transcoding/file123" in response.text
    mock_emby_proxy_service.resolve_media_source_file_id.assert_awaited_once_with(
        item_id="item123", media_source_id="media_source_1"
    )


def test_get_master_playlist_when_emby_override_header_is_invalid_then_returns_400():
    client = _build_emby_client(raise_server_exceptions=False)
    app_config = SimpleNamespace(
        endpoints=[],
        emby=SimpleNamespace(proxy_base_url="http://proxy.example:18097", url="http://emby.example:8096"),
    )

    with (
        patch("app.api.emby.config_service.get_config", return_value=app_config),
        patch("app.api.emby.config.get_quark_cookie", return_value="test-cookie"),
        patch(
            "app.api.emby.EmbyProxyService",
            new=Mock(side_effect=AssertionError("should reject invalid Emby override before proxy service init")),
        ),
    ):
        response = client.get(
            "/api/emby/videos/item123/master.m3u8",
            params={"MediaSourceId": "media_source_1"},
            headers={
                "X-Emby-Token": "emby-api-key",
                "X-Emby-Server-Url": "not-a-url",
            },
        )

    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid Emby server URL"}


def test_get_master_playlist_when_native_videos_path_used_then_handles_locally():
    client = _build_emby_client()
    app_config = SimpleNamespace(
        endpoints=[],
        emby=SimpleNamespace(proxy_base_url="http://proxy.example:18097"),
    )

    with (
        patch("app.api.emby.config_service.get_config", return_value=app_config),
        patch("app.api.emby.config.get_quark_cookie", return_value="test-cookie"),
        patch("app.api.emby.EmbyProxyService") as mock_emby_proxy_service_cls,
        patch(
            "app.api.emby_gateway._forward_to_emby",
            new=AsyncMock(side_effect=AssertionError("should not fall back to generic upstream forwarding")),
        ),
    ):
        mock_emby_proxy_service = AsyncMock()
        mock_emby_proxy_service.resolve_media_source_file_id = AsyncMock(return_value="file123")
        mock_emby_proxy_service_cls.return_value.__aenter__.return_value = mock_emby_proxy_service
        mock_emby_proxy_service_cls.return_value.__aexit__.return_value = None

        response = client.get(
            "/api/emby/Videos/item123/master.m3u8",
            params={"MediaSourceId": "media_source_1", "api_key": "emby-api-key"},
        )

    assert response.status_code == 200
    assert response.headers["Content-Type"].startswith("application/vnd.apple.mpegurl")
    assert "/api/proxy/transcoding/file123" in response.text
    mock_emby_proxy_service.resolve_media_source_file_id.assert_awaited_once_with(
        item_id="item123", media_source_id="media_source_1"
    )


def test_get_master_playlist_when_emby_prefixed_native_path_used_then_handles_locally():
    client = _build_emby_client()
    app_config = SimpleNamespace(
        endpoints=[],
        emby=SimpleNamespace(proxy_base_url="http://proxy.example:18097"),
    )

    with (
        patch("app.api.emby.config_service.get_config", return_value=app_config),
        patch("app.api.emby.config.get_quark_cookie", return_value="test-cookie"),
        patch("app.api.emby.EmbyProxyService") as mock_emby_proxy_service_cls,
        patch(
            "app.api.emby_gateway._forward_to_emby",
            new=AsyncMock(side_effect=AssertionError("should not fall back to generic upstream forwarding")),
        ),
    ):
        mock_emby_proxy_service = AsyncMock()
        mock_emby_proxy_service.resolve_media_source_file_id = AsyncMock(return_value="file123")
        mock_emby_proxy_service_cls.return_value.__aenter__.return_value = mock_emby_proxy_service
        mock_emby_proxy_service_cls.return_value.__aexit__.return_value = None

        response = client.get(
            "/api/emby/emby/Videos/item123/master.m3u8",
            params={"MediaSourceId": "media_source_1", "api_key": "emby-api-key"},
        )

    assert response.status_code == 200
    assert response.headers["Content-Type"].startswith("application/vnd.apple.mpegurl")
    assert "/api/proxy/transcoding/file123" in response.text
    mock_emby_proxy_service.resolve_media_source_file_id.assert_awaited_once_with(
        item_id="item123", media_source_id="media_source_1"
    )


def test_get_master_playlist_when_emby_prefixed_lowercase_path_used_then_handles_locally():
    client = _build_emby_client()
    app_config = SimpleNamespace(
        endpoints=[],
        emby=SimpleNamespace(proxy_base_url="http://proxy.example:18097"),
    )

    with (
        patch("app.api.emby.config_service.get_config", return_value=app_config),
        patch("app.api.emby.config.get_quark_cookie", return_value="test-cookie"),
        patch("app.api.emby.EmbyProxyService") as mock_emby_proxy_service_cls,
        patch(
            "app.api.emby_gateway._forward_to_emby",
            new=AsyncMock(side_effect=AssertionError("should not fall back to generic upstream forwarding")),
        ),
    ):
        mock_emby_proxy_service = AsyncMock()
        mock_emby_proxy_service.resolve_media_source_file_id = AsyncMock(return_value="file123")
        mock_emby_proxy_service_cls.return_value.__aenter__.return_value = mock_emby_proxy_service
        mock_emby_proxy_service_cls.return_value.__aexit__.return_value = None

        response = client.get(
            "/api/emby/emby/videos/item123/master.m3u8",
            params={"MediaSourceId": "media_source_1", "api_key": "emby-api-key"},
        )

    assert response.status_code == 200
    assert response.headers["Content-Type"].startswith("application/vnd.apple.mpegurl")
    assert "/api/proxy/transcoding/file123" in response.text
    mock_emby_proxy_service.resolve_media_source_file_id.assert_awaited_once_with(
        item_id="item123", media_source_id="media_source_1"
    )


def test_get_master_playlist_when_head_requested_then_handles_locally_without_fallback_proxy():
    client = _build_emby_client()
    app_config = SimpleNamespace(
        endpoints=[],
        emby=SimpleNamespace(proxy_base_url="http://proxy.example:18097"),
    )

    with (
        patch("app.api.emby.config_service.get_config", return_value=app_config),
        patch("app.api.emby.config.get_quark_cookie", return_value="test-cookie"),
        patch("app.api.emby.EmbyProxyService") as mock_emby_proxy_service_cls,
    ):
        mock_emby_proxy_service = AsyncMock()
        mock_emby_proxy_service.resolve_media_source_file_id = AsyncMock(return_value="file123")
        mock_emby_proxy_service_cls.return_value.__aenter__.return_value = mock_emby_proxy_service
        mock_emby_proxy_service_cls.return_value.__aexit__.return_value = None

        response = client.head(
            "/api/emby/videos/item123/master.m3u8",
            params={"MediaSourceId": "media_source_1", "api_key": "emby-api-key"},
        )

    assert response.status_code == 200
    assert response.headers["Content-Type"].startswith("application/vnd.apple.mpegurl")
    assert response.headers["Cache-Control"] == "no-cache"
    assert response.content == b""
    mock_emby_proxy_service.resolve_media_source_file_id.assert_awaited_once_with(
        item_id="item123", media_source_id="media_source_1"
    )


def test_get_master_playlist_when_internal_error_then_does_not_leak_error_detail():
    client = _build_emby_client()
    app_config = SimpleNamespace(
        endpoints=[],
        emby=SimpleNamespace(proxy_base_url="http://proxy.example:18097"),
    )

    with (
        patch("app.api.emby.config_service.get_config", return_value=app_config),
        patch("app.api.emby.config.get_quark_cookie", return_value="test-cookie"),
        patch("app.api.emby.EmbyProxyService") as mock_emby_proxy_service_cls,
    ):
        mock_emby_proxy_service = AsyncMock()
        mock_emby_proxy_service.resolve_media_source_file_id = AsyncMock(side_effect=RuntimeError("internal secret path"))
        mock_emby_proxy_service_cls.return_value.__aenter__.return_value = mock_emby_proxy_service
        mock_emby_proxy_service_cls.return_value.__aexit__.return_value = None

        response = client.get(
            "/api/emby/videos/item123/master.m3u8",
            params={"MediaSourceId": "media_source_1", "api_key": "emby-api-key"},
        )

    assert response.status_code == 500
    assert response.json() == {"detail": "Failed to get master playlist"}


def test_redirect_route_when_direct_and_transcoding_not_playable_then_falls_back_to_stream_proxy():
    client = _build_proxy_client()

    with (
        patch("app.api.proxy.config.get_quark_cookie", return_value="test-cookie"),
        patch("app.api.proxy.QuarkService", _FakeQuarkService),
        patch("app.services.quark_service.QuarkService", _FakeQuarkService),
        patch("app.api.proxy.LinkResolver", _FakeLinkResolver),
        patch("app.api.proxy.WebDAVFallback", _FakeWebDAVFallback),
        patch("app.api.proxy._is_internal_redirect_enabled", return_value=False),
        patch("app.api.proxy._is_url_directly_playable", side_effect=[False, False]),
    ):
        response = client.get("/api/proxy/redirect/file123", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "/api/proxy/stream/file123"


def test_redirect_route_when_placeholder_file_id_and_path_present_then_resolves_real_quark_fid_before_redirect():
    client = _build_proxy_client()

    class _FakePathAwareQuarkService(_FakeQuarkService):
        last_lookup_path = None

        async def get_file_by_path(self, path: str):
            _FakePathAwareQuarkService.last_lookup_path = path
            return SimpleNamespace(fid="real_file_123")

    class _FakePathAwareLinkResolver:
        last_file_id = None
        last_path = None

        def __init__(self, quark_service):
            self.quark_service = quark_service

        async def resolve(self, file_id: str, path: str | None):
            _FakePathAwareLinkResolver.last_file_id = file_id
            _FakePathAwareLinkResolver.last_path = path
            return f"https://download.example/{file_id}.mp4"

    with (
        patch("app.api.proxy.config.get_quark_cookie", return_value="test-cookie"),
        patch("app.api.proxy.QuarkService", _FakePathAwareQuarkService),
        patch("app.services.quark_service.QuarkService", _FakePathAwareQuarkService),
        patch("app.api.proxy.LinkResolver", _FakePathAwareLinkResolver),
        patch("app.api.proxy.WebDAVFallback", _FakeWebDAVFallback),
        patch("app.api.proxy._is_url_directly_playable", return_value=True),
    ):
        response = client.get(
            "/api/proxy/redirect/placeholder123",
            params={"path": "流浪地球/movie.mkv"},
            follow_redirects=False,
        )

    assert response.status_code == 302
    assert response.headers["location"] == "https://download.example/real_file_123.mp4"
    assert _FakePathAwareQuarkService.last_lookup_path == "流浪地球/movie.mkv"
    assert _FakePathAwareLinkResolver.last_file_id == "real_file_123"
    assert _FakePathAwareLinkResolver.last_path == "流浪地球/movie.mkv"


def test_redirect_route_when_direct_first_disabled_then_redirects_to_local_proxy_stream():
    client = _build_proxy_client()
    mock_config = SimpleNamespace(
        playback=SimpleNamespace(direct_first=False, force_proxy_clients=[], force_proxy_hosts=[])
    )

    with (
        patch("app.api.proxy.config.get_quark_cookie", return_value="test-cookie"),
        patch("app.api.proxy.QuarkService", _FakeQuarkService),
        patch("app.services.quark_service.QuarkService", _FakeQuarkService),
        patch("app.api.proxy.LinkResolver", _FakeLinkResolver),
        patch("app.api.proxy.WebDAVFallback", _FakeWebDAVFallback),
        patch("app.services.playback_decision_service.get_config_service") as mock_get_config_service,
        patch("app.api.proxy._is_url_directly_playable", return_value=True),
    ):
        mock_get_config_service.return_value.get_config.return_value = mock_config
        response = client.get("/api/proxy/redirect/file123", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == "/api/proxy/stream/file123?source=download"


def test_redirect_route_when_native_authorization_header_marks_force_proxy_client_then_redirects_to_local_proxy_stream():
    client = _build_proxy_client()
    mock_config = SimpleNamespace(
        playback=SimpleNamespace(direct_first=True, force_proxy_clients=["infuse"], force_proxy_hosts=[])
    )

    with (
        patch("app.api.proxy.config.get_quark_cookie", return_value="test-cookie"),
        patch("app.api.proxy.QuarkService", _FakeQuarkService),
        patch("app.services.quark_service.QuarkService", _FakeQuarkService),
        patch("app.api.proxy.LinkResolver", _FakeLinkResolver),
        patch("app.api.proxy.WebDAVFallback", _FakeWebDAVFallback),
        patch("app.services.playback_decision_service.get_config_service") as mock_get_config_service,
        patch(
            "app.api.proxy._resolve_redirect_target",
            new=AsyncMock(return_value=("https://download.example/file123.mp4", None)),
        ) as mock_resolve_redirect_target,
    ):
        mock_get_config_service.return_value.get_config.return_value = mock_config
        response = client.get(
            "/api/proxy/redirect/file123",
            headers={"X-Emby-Authorization": 'MediaBrowser Client="Infuse", Device="Apple TV"'},
            follow_redirects=False,
        )

    assert response.status_code == 302
    assert response.headers["location"] == "/api/proxy/stream/file123?source=download"
    assert mock_resolve_redirect_target.await_args.kwargs["client_name"] == "Infuse"
    assert mock_resolve_redirect_target.await_args.kwargs["device_name"] == "Apple TV"


def test_redirect_route_when_resolved_redirect_url_invalid_then_falls_back_to_local_proxy_stream():
    client = _build_proxy_client()

    with (
        patch("app.api.proxy.config.get_quark_cookie", return_value="test-cookie"),
        patch("app.api.proxy.QuarkService", _FakeQuarkService),
        patch("app.services.quark_service.QuarkService", _FakeQuarkService),
        patch("app.api.proxy.LinkResolver", _FakeLinkResolver),
        patch("app.api.proxy.WebDAVFallback", _FakeWebDAVFallback),
        patch("app.api.proxy._is_internal_redirect_enabled", return_value=True),
        patch("app.api.proxy._is_url_directly_playable", return_value=True),
        patch(
            "app.api.proxy.general_validator.validate",
            side_effect=URLValidationError("Private IP address '127.0.0.1' is not allowed"),
        ),
    ):
        response = client.get("/api/proxy/redirect/file123", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == "/api/proxy/stream/file123?source=download"


def test_redirect_route_when_same_client_host_failed_recently_then_uses_sticky_proxy():
    client = _build_proxy_client()
    mock_config = SimpleNamespace(
        playback=SimpleNamespace(
            direct_first=True,
            force_proxy_clients=[],
            force_proxy_hosts=[],
            sticky_downgrade_threshold=1,
            sticky_downgrade_ttl_sec=3600,
        )
    )

    proxy_module.playback_decision_service.reset_route_health()

    with (
        patch("app.api.proxy.config.get_quark_cookie", return_value="test-cookie"),
        patch("app.api.proxy.QuarkService", _FakeQuarkService),
        patch("app.services.quark_service.QuarkService", _FakeQuarkService),
        patch("app.api.proxy.LinkResolver", _FakeLinkResolver),
        patch("app.api.proxy.WebDAVFallback", _FakeWebDAVFallback),
        patch("app.services.playback_decision_service.get_config_service") as mock_get_config_service,
        patch("app.api.proxy._is_url_directly_playable", side_effect=[False, True, True]),
    ):
        mock_get_config_service.return_value.get_config.return_value = mock_config

        first_response = client.get(
            "/api/proxy/redirect/file123",
            headers={"X-Emby-Client": "Infuse"},
            follow_redirects=False,
        )
        second_response = client.get(
            "/api/proxy/redirect/file123",
            headers={"X-Emby-Client": "Infuse"},
            follow_redirects=False,
        )

    assert first_response.status_code == 302
    assert first_response.headers["location"] == "https://transcode.example/file123.m3u8"
    assert second_response.status_code == 302
    assert second_response.headers["location"] == "/api/proxy/stream/file123?source=download"

    proxy_module.playback_decision_service.reset_route_health()


def test_redirect_route_when_placeholder_file_id_falls_back_to_stream_then_uses_resolved_real_file_id():
    client = _build_proxy_client()

    class _FakePathAwareQuarkService(_FakeQuarkService):
        last_lookup_path = None

        async def get_file_by_path(self, path: str):
            _FakePathAwareQuarkService.last_lookup_path = path
            return SimpleNamespace(fid="real_file_123")

    class _FakePathAwareLinkResolver:
        last_file_id = None
        last_path = None

        def __init__(self, quark_service):
            self.quark_service = quark_service

        async def resolve(self, file_id: str, path: str | None):
            _FakePathAwareLinkResolver.last_file_id = file_id
            _FakePathAwareLinkResolver.last_path = path
            return f"https://download.example/{file_id}.mp4"

    with (
        patch("app.api.proxy.config.get_quark_cookie", return_value="test-cookie"),
        patch("app.api.proxy.QuarkService", _FakePathAwareQuarkService),
        patch("app.services.quark_service.QuarkService", _FakePathAwareQuarkService),
        patch("app.api.proxy.LinkResolver", _FakePathAwareLinkResolver),
        patch("app.api.proxy.WebDAVFallback", _FakeWebDAVFallback),
        patch("app.api.proxy._is_internal_redirect_enabled", return_value=True),
        patch("app.api.proxy._is_url_directly_playable", side_effect=[False, False]),
    ):
        response = client.get(
            "/api/proxy/redirect/placeholder123",
            params={"path": "流浪地球/movie.mkv"},
            follow_redirects=False,
        )

    assert response.status_code == 302
    assert response.headers["location"] == "/api/proxy/stream/real_file_123?source=download"
    assert _FakePathAwareQuarkService.last_lookup_path == "流浪地球/movie.mkv"
    assert _FakePathAwareLinkResolver.last_file_id == "real_file_123"
    assert _FakePathAwareLinkResolver.last_path == "流浪地球/movie.mkv"


def test_proxy_playback_routes_when_no_auth_then_still_accessible_for_emby_clients():
    client = _build_proxy_client_without_auth_override()

    with patch("app.api.proxy.config.get_quark_cookie", return_value="test-cookie"):
        stream_response = client.get("/api/proxy/stream/file123")
        redirect_response = client.get("/api/proxy/redirect/file123", follow_redirects=False)

    assert stream_response.status_code != 401
    assert redirect_response.status_code != 401


def test_redirect_route_when_internal_redirect_enabled_then_returns_302_to_download_stream_proxy():
    client = _build_proxy_client()

    with (
        patch("app.api.proxy.config.get_quark_cookie", return_value="test-cookie"),
        patch("app.api.proxy.QuarkService", _FakeQuarkService),
        patch("app.services.quark_service.QuarkService", _FakeQuarkService),
        patch("app.api.proxy.LinkResolver", _FakeLinkResolver),
        patch("app.api.proxy.WebDAVFallback", _FakeWebDAVFallback),
        patch("app.api.proxy._is_internal_redirect_enabled", return_value=True),
        patch("app.api.proxy._is_url_directly_playable", side_effect=[False, False]),
        patch(
            "app.api.proxy.proxy_stream",
            new=AsyncMock(return_value=Response(content=b"stream-fallback", media_type="video/mp4")),
        ),
    ):
        response = client.get("/api/proxy/redirect/file123", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == "/api/proxy/stream/file123?source=download"


def test_stream_route_when_source_omitted_then_uses_download_link_first():
    client = _build_proxy_client()

    class _FakeUpstreamResponse:
        status = 206
        headers = {
            "Content-Type": "video/mp4",
            "Content-Length": "1024",
            "Content-Range": "bytes 0-1023/2048",
            "Accept-Ranges": "bytes",
        }

        class _Content:
            @staticmethod
            async def iter_chunked(_size):
                _FakeUpstreamResponse.last_chunk_size = _size
                yield b"x" * 16

        content = _Content()

        def close(self):
            return None

    class _FakeAiohttpSession:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

        async def get(self, url, headers=None, allow_redirects=True):
            _FakeAiohttpSession.last_url = url
            _FakeAiohttpSession.last_headers = headers or {}
            _FakeAiohttpSession.last_allow_redirects = allow_redirects
            return _FakeUpstreamResponse()

        async def close(self):
            return None

    class _FakeDownloadQuarkService:
        last_instance = None

        def __init__(self, cookie: str):
            self.cookie = cookie
            self.download_calls = 0
            self.transcoding_calls = 0
            _FakeDownloadQuarkService.last_instance = self

        async def get_download_link(self, file_id: str):
            self.download_calls += 1
            return SimpleNamespace(url=f"https://download.example/{file_id}.mp4", headers={})

        async def get_transcoding_link(self, file_id: str):
            self.transcoding_calls += 1
            return SimpleNamespace(url=f"https://transcode.example/{file_id}.m3u8", headers={})

        async def close(self):
            return None

    with (
        patch("app.api.proxy.config.get_quark_cookie", return_value="test-cookie"),
        patch("app.api.proxy.QuarkService", _FakeDownloadQuarkService),
        patch("app.services.quark_service.QuarkService", _FakeDownloadQuarkService),
        patch("app.api.proxy.aiohttp.ClientSession", _FakeAiohttpSession),
    ):
        response = client.get("/api/proxy/stream/file123")

    assert response.status_code == 206
    assert _FakeDownloadQuarkService.last_instance is not None
    assert _FakeDownloadQuarkService.last_instance.download_calls == 1
    assert _FakeDownloadQuarkService.last_instance.transcoding_calls == 0
    assert _FakeAiohttpSession.last_url == "https://download.example/file123.mp4"
    assert _FakeAiohttpSession.last_headers["Accept-Encoding"] == "identity"
    assert _FakeUpstreamResponse.last_chunk_size == 1024 * 1024
    assert response.headers["Content-Length"] == "1024"


def test_stream_route_when_zero_offset_bounded_range_hits_first_segment_cache_then_second_request_skips_upstream():
    client = _build_proxy_client()
    proxy_module.first_segment_cache_service.clear()

    class _FakeSegmentUpstreamResponse:
        status = 206
        headers = {
            "Content-Type": "video/mp4",
            "Content-Length": "8",
            "Content-Range": "bytes 0-7/2048",
            "Accept-Ranges": "bytes",
            "ETag": "etag-1",
        }

        class _Content:
            @staticmethod
            async def iter_chunked(_size):
                yield b"abcdefgh"

        content = _Content()

        def close(self):
            return None

    class _FakeSegmentAiohttpSession:
        calls: list[dict[str, str]] = []

        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

        async def get(self, url, headers=None, allow_redirects=True):
            _ = url, allow_redirects
            _FakeSegmentAiohttpSession.calls.append(dict(headers or {}))
            return _FakeSegmentUpstreamResponse()

        async def close(self):
            return None

    class _FakeDownloadQuarkService:
        def __init__(self, cookie: str):
            self.cookie = cookie

        async def get_download_link(self, file_id: str):
            return SimpleNamespace(url=f"https://download.example/{file_id}.mp4", headers={})

        async def get_transcoding_link(self, file_id: str):
            return SimpleNamespace(url=f"https://transcode.example/{file_id}.m3u8", headers={})

        async def close(self):
            return None

    mock_config = SimpleNamespace(
        playback=SimpleNamespace(
            first_segment_cache_enabled=True,
            first_segment_cache_mb=1,
            first_segment_cache_ttl_sec=3600,
        )
    )

    with (
        patch("app.api.proxy.config.get_quark_cookie", return_value="test-cookie"),
        patch("app.api.proxy.QuarkService", _FakeDownloadQuarkService),
        patch("app.services.quark_service.QuarkService", _FakeDownloadQuarkService),
        patch("app.api.proxy.aiohttp.ClientSession", _FakeSegmentAiohttpSession),
        patch("app.services.first_segment_cache_service.get_config_service") as mock_get_config_service,
    ):
        mock_get_config_service.return_value.get_config.return_value = mock_config
        first_response = client.get("/api/proxy/stream/file123", headers={"Range": "bytes=0-3"})
        second_response = client.get("/api/proxy/stream/file123", headers={"Range": "bytes=0-3"})

    assert first_response.status_code == 206
    assert first_response.content == b"abcd"
    assert first_response.headers["Content-Range"] == "bytes 0-3/2048"
    assert second_response.status_code == 206
    assert second_response.content == b"abcd"
    assert len(_FakeSegmentAiohttpSession.calls) == 1
    assert _FakeSegmentAiohttpSession.calls[0]["Range"] == "bytes=0-1048575"

    proxy_module.first_segment_cache_service.clear()


def test_stream_route_when_range_does_not_start_at_zero_then_bypasses_first_segment_cache():
    client = _build_proxy_client()
    proxy_module.first_segment_cache_service.clear()

    class _FakeOffsetUpstreamResponse:
        status = 206
        headers = {
            "Content-Type": "video/mp4",
            "Content-Length": "4",
            "Content-Range": "bytes 100-103/2048",
            "Accept-Ranges": "bytes",
        }

        class _Content:
            @staticmethod
            async def iter_chunked(_size):
                yield b"WXYZ"

        content = _Content()

        def close(self):
            return None

    class _FakeOffsetAiohttpSession:
        calls: list[dict[str, str]] = []

        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

        async def get(self, url, headers=None, allow_redirects=True):
            _ = url, allow_redirects
            _FakeOffsetAiohttpSession.calls.append(dict(headers or {}))
            return _FakeOffsetUpstreamResponse()

        async def close(self):
            return None

    class _FakeDownloadQuarkService:
        def __init__(self, cookie: str):
            self.cookie = cookie

        async def get_download_link(self, file_id: str):
            return SimpleNamespace(url=f"https://download.example/{file_id}.mp4", headers={})

        async def get_transcoding_link(self, file_id: str):
            return SimpleNamespace(url=f"https://transcode.example/{file_id}.m3u8", headers={})

        async def close(self):
            return None

    mock_config = SimpleNamespace(
        playback=SimpleNamespace(
            first_segment_cache_enabled=True,
            first_segment_cache_mb=1,
            first_segment_cache_ttl_sec=3600,
        )
    )

    with (
        patch("app.api.proxy.config.get_quark_cookie", return_value="test-cookie"),
        patch("app.api.proxy.QuarkService", _FakeDownloadQuarkService),
        patch("app.services.quark_service.QuarkService", _FakeDownloadQuarkService),
        patch("app.api.proxy.aiohttp.ClientSession", _FakeOffsetAiohttpSession),
        patch("app.services.first_segment_cache_service.get_config_service") as mock_get_config_service,
    ):
        mock_get_config_service.return_value.get_config.return_value = mock_config
        first_response = client.get("/api/proxy/stream/file123", headers={"Range": "bytes=100-103"})
        second_response = client.get("/api/proxy/stream/file123", headers={"Range": "bytes=100-103"})

    assert first_response.status_code == 206
    assert first_response.content == b"WXYZ"
    assert second_response.status_code == 206
    assert second_response.content == b"WXYZ"
    assert len(_FakeOffsetAiohttpSession.calls) == 2
    assert _FakeOffsetAiohttpSession.calls[0]["Range"] == "bytes=100-103"
    assert _FakeOffsetAiohttpSession.calls[1]["Range"] == "bytes=100-103"

    proxy_module.first_segment_cache_service.clear()


def test_stream_route_when_head_requested_then_returns_seek_headers_without_body():
    client = _build_proxy_client()

    class _FakeHeadUpstreamResponse:
        status = 200
        headers = {
            "Content-Type": "video/mp4",
            "Content-Length": "2048",
            "Accept-Ranges": "bytes",
        }

        class _Content:
            @staticmethod
            async def iter_chunked(_size):
                yield b"should-not-stream"

        content = _Content()

        def close(self):
            return None

    class _FakeHeadAiohttpSession:
        last_method = None
        last_url = None
        last_headers = None

        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

        async def get(self, url, headers=None, allow_redirects=True):
            _FakeHeadAiohttpSession.last_method = "GET"
            _FakeHeadAiohttpSession.last_url = url
            _FakeHeadAiohttpSession.last_headers = headers or {}
            return _FakeHeadUpstreamResponse()

        async def head(self, url, headers=None, allow_redirects=True):
            _FakeHeadAiohttpSession.last_method = "HEAD"
            _FakeHeadAiohttpSession.last_url = url
            _FakeHeadAiohttpSession.last_headers = headers or {}
            return _FakeHeadUpstreamResponse()

        async def close(self):
            return None

    class _FakeDownloadQuarkService:
        def __init__(self, cookie: str):
            self.cookie = cookie

        async def get_download_link(self, file_id: str):
            return SimpleNamespace(url=f"https://download.example/{file_id}.mp4", headers={})

        async def get_transcoding_link(self, file_id: str):
            return SimpleNamespace(url=f"https://transcode.example/{file_id}.m3u8", headers={})

        async def close(self):
            return None

    with (
        patch("app.api.proxy.config.get_quark_cookie", return_value="test-cookie"),
        patch("app.api.proxy.QuarkService", _FakeDownloadQuarkService),
        patch("app.services.quark_service.QuarkService", _FakeDownloadQuarkService),
        patch("app.api.proxy.aiohttp.ClientSession", _FakeHeadAiohttpSession),
    ):
        response = client.head("/api/proxy/stream/file123")

    assert response.status_code == 200
    assert response.content == b""
    assert response.headers["Content-Length"] == "2048"
    assert response.headers["Accept-Ranges"] == "bytes"
    assert response.headers["Content-Type"].startswith("video/mp4")
    assert _FakeHeadAiohttpSession.last_method == "HEAD"
    assert _FakeHeadAiohttpSession.last_url == "https://download.example/file123.mp4"
    assert _FakeHeadAiohttpSession.last_headers["Accept-Encoding"] == "identity"


def test_stream_route_when_head_upstream_headers_too_long_then_falls_back_to_range_probe():
    client = _build_proxy_client()

    class _FakeRangeProbeResponse:
        status = 206
        headers = {
            "Content-Type": "video/mp4",
            "Content-Length": "1",
            "Content-Range": "bytes 0-0/2048",
            "Accept-Ranges": "bytes",
        }

        class _Content:
            @staticmethod
            async def iter_chunked(_size):
                yield b"x"

        content = _Content()

        def close(self):
            return None

    class _FakeFallbackHeadAiohttpSession:
        calls: list[tuple[str, str, dict[str, str]]] = []

        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

        async def get(self, url, headers=None, allow_redirects=True):
            headers = headers or {}
            _FakeFallbackHeadAiohttpSession.calls.append(("GET", url, dict(headers)))
            return _FakeRangeProbeResponse()

        async def head(self, url, headers=None, allow_redirects=True):
            headers = headers or {}
            _FakeFallbackHeadAiohttpSession.calls.append(("HEAD", url, dict(headers)))
            raise LineTooLong("header value", "8190", "9572")

        async def close(self):
            return None

    class _FakeDownloadQuarkService:
        def __init__(self, cookie: str):
            self.cookie = cookie

        async def get_download_link(self, file_id: str):
            return SimpleNamespace(url=f"https://download.example/{file_id}.mp4", headers={})

        async def get_transcoding_link(self, file_id: str):
            return SimpleNamespace(url=f"https://transcode.example/{file_id}.m3u8", headers={})

        async def close(self):
            return None

    with (
        patch("app.api.proxy.config.get_quark_cookie", return_value="test-cookie"),
        patch("app.api.proxy.QuarkService", _FakeDownloadQuarkService),
        patch("app.services.quark_service.QuarkService", _FakeDownloadQuarkService),
        patch("app.api.proxy.aiohttp.ClientSession", _FakeFallbackHeadAiohttpSession),
    ):
        response = client.head("/api/proxy/stream/file123")

    assert response.status_code == 200
    assert response.content == b""
    assert response.headers["Content-Length"] == "2048"
    assert response.headers["Accept-Ranges"] == "bytes"
    assert response.headers["Content-Type"].startswith("video/mp4")
    assert "Content-Range" not in response.headers
    assert len(_FakeFallbackHeadAiohttpSession.calls) == 2
    assert _FakeFallbackHeadAiohttpSession.calls[0][0] == "HEAD"
    assert _FakeFallbackHeadAiohttpSession.calls[1][0] == "GET"
    assert _FakeFallbackHeadAiohttpSession.calls[1][2]["Range"] == "bytes=0-0"
    assert _FakeFallbackHeadAiohttpSession.calls[1][2]["Accept-Encoding"] == "identity"


def test_stream_video_when_range_requested_then_returns_partial_content_headers():
    client = _build_emby_client()
    app_config = SimpleNamespace(
        endpoints=[],
        emby=SimpleNamespace(proxy_base_url="http://proxy.example:18097"),
    )

    with (
        patch("app.api.emby.config_service.get_config", return_value=app_config),
        patch("app.api.emby.config.get_quark_cookie", return_value="test-cookie"),
        patch("app.api.emby.EmbyProxyService") as mock_emby_proxy_service_cls,
        patch(
            "app.api.emby.proxy_stream_by_file_id",
            new=AsyncMock(
                return_value=Response(
                    content=b"ab",
                    status_code=206,
                    media_type="video/mp4",
                    headers={
                        "Content-Range": "bytes 0-1/2048",
                        "Accept-Ranges": "bytes",
                        "Content-Type": "video/mp4",
                    },
                )
            ),
        ) as mock_proxy_stream,
    ):
        mock_emby_proxy_service = AsyncMock()
        mock_emby_proxy_service.resolve_media_source_file_id = AsyncMock(return_value="file123")
        mock_emby_proxy_service_cls.return_value.__aenter__.return_value = mock_emby_proxy_service
        mock_emby_proxy_service_cls.return_value.__aexit__.return_value = None

        response = client.get(
            "/api/emby/videos/item123/stream",
            params={"media_source_id": "media_source_1", "static": "true", "container": "mkv"},
            headers={"Range": "bytes=0-1"},
        )

    assert response.status_code == 206
    assert response.headers["Content-Range"] == "bytes 0-1/2048"
    assert response.headers["Accept-Ranges"] == "bytes"
    assert response.headers["Content-Type"].startswith("video/mp4")
    mock_proxy_stream.assert_awaited_once()


def test_stream_video_when_head_requested_then_returns_seek_headers_without_body():
    client = _build_emby_client()
    app_config = SimpleNamespace(
        endpoints=[],
        emby=SimpleNamespace(proxy_base_url="http://proxy.example:18097"),
    )

    with (
        patch("app.api.emby.config_service.get_config", return_value=app_config),
        patch("app.api.emby.config.get_quark_cookie", return_value="test-cookie"),
        patch("app.api.emby.EmbyProxyService") as mock_emby_proxy_service_cls,
        patch(
            "app.api.emby.proxy_stream_by_file_id",
            new=AsyncMock(
                return_value=Response(
                    content=b"",
                    status_code=200,
                    media_type="video/mp4",
                    headers={
                        "Content-Length": "67600285904",
                        "Accept-Ranges": "bytes",
                        "Content-Type": "video/x-matroska",
                    },
                )
            ),
        ) as mock_proxy_stream,
    ):
        mock_emby_proxy_service = AsyncMock()
        mock_emby_proxy_service.resolve_media_source_file_id = AsyncMock(return_value="file123")
        mock_emby_proxy_service_cls.return_value.__aenter__.return_value = mock_emby_proxy_service
        mock_emby_proxy_service_cls.return_value.__aexit__.return_value = None

        response = client.head(
            "/api/emby/videos/item123/stream",
            params={"media_source_id": "media_source_1", "static": "true", "container": "mkv"},
        )

    assert response.status_code == 200
    assert response.content == b""
    assert response.headers["Content-Length"] == "67600285904"
    assert response.headers["Accept-Ranges"] == "bytes"
    assert response.headers["Content-Type"].startswith("video/x-matroska")
    mock_proxy_stream.assert_awaited_once()


def test_stream_video_when_head_requested_with_container_suffix_then_returns_seek_headers_without_body():
    client = _build_emby_client()
    app_config = SimpleNamespace(
        endpoints=[],
        emby=SimpleNamespace(proxy_base_url="http://proxy.example:18097"),
    )

    with (
        patch("app.api.emby.config_service.get_config", return_value=app_config),
        patch("app.api.emby.config.get_quark_cookie", return_value="test-cookie"),
        patch("app.api.emby.EmbyProxyService") as mock_emby_proxy_service_cls,
        patch(
            "app.api.emby.proxy_stream_by_file_id",
            new=AsyncMock(
                return_value=Response(
                    content=b"",
                    status_code=200,
                    media_type="video/mp4",
                    headers={
                        "Content-Length": "67600285904",
                        "Accept-Ranges": "bytes",
                        "Content-Type": "video/x-matroska",
                    },
                )
            ),
        ) as mock_proxy_stream,
    ):
        mock_emby_proxy_service = AsyncMock()
        mock_emby_proxy_service.resolve_media_source_file_id = AsyncMock(return_value="file123")
        mock_emby_proxy_service_cls.return_value.__aenter__.return_value = mock_emby_proxy_service
        mock_emby_proxy_service_cls.return_value.__aexit__.return_value = None

        response = client.head(
            "/api/emby/videos/item123/stream.mkv",
            params={"media_source_id": "media_source_1", "static": "true"},
        )

    assert response.status_code == 200
    assert response.content == b""
    assert response.headers["Content-Length"] == "67600285904"
    assert response.headers["Accept-Ranges"] == "bytes"
    assert response.headers["Content-Type"].startswith("video/x-matroska")
    mock_proxy_stream.assert_awaited_once()


def test_stream_video_when_internal_error_then_does_not_leak_error_detail():
    client = _build_emby_client()
    app_config = SimpleNamespace(
        endpoints=[],
        emby=SimpleNamespace(proxy_base_url="http://proxy.example:18097"),
    )

    with (
        patch("app.api.emby.config_service.get_config", return_value=app_config),
        patch("app.api.emby.config.get_quark_cookie", return_value="test-cookie"),
        patch("app.api.emby.EmbyProxyService") as mock_emby_proxy_service_cls,
    ):
        mock_emby_proxy_service = AsyncMock()
        mock_emby_proxy_service.resolve_media_source_file_id = AsyncMock(side_effect=RuntimeError("internal secret path"))
        mock_emby_proxy_service_cls.return_value.__aenter__.return_value = mock_emby_proxy_service
        mock_emby_proxy_service_cls.return_value.__aexit__.return_value = None

        response = client.get(
            "/api/emby/videos/item123/stream",
            params={"media_source_id": "media_source_1", "static": "true"},
        )

    assert response.status_code == 500
    assert response.json() == {"detail": "Failed to stream video"}


@pytest.mark.asyncio
async def test_url_playability_probe_when_cache_hit_then_skips_second_network_call():
    class _FakeResp:
        status = 206

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            return None

    class _FakeSession:
        calls = 0

        def __init__(self, *args, **kwargs):
            _ = args, kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            return None

        def get(self, *args, **kwargs):
            _ = args, kwargs
            _FakeSession.calls += 1
            return _FakeResp()

    proxy_module._probe_cache.clear()
    with (
        patch("app.api.proxy._get_probe_cache_ttl_seconds", return_value=60),
        patch("app.api.proxy.aiohttp.ClientSession", _FakeSession),
    ):
        first = await proxy_module._is_url_directly_playable("https://playable.example/video.mp4")
        second = await proxy_module._is_url_directly_playable("https://playable.example/video.mp4")

    assert first is True
    assert second is True
    assert _FakeSession.calls == 1


def test_transcoding_endpoint_does_not_leak_internal_errors():
    client = _build_proxy_client()

    class _BrokenQuarkService:
        def __init__(self, cookie: str):
            self.cookie = cookie

        async def get_transcoding_link(self, file_id: str):
            raise RuntimeError("internal secret path")

        async def close(self):
            return None

    with (
        patch("app.api.proxy.config.get_quark_cookie", return_value="test-cookie"),
        patch("app.api.proxy.QuarkService", _BrokenQuarkService),
    ):
        response = client.get("/api/proxy/transcoding/file123", follow_redirects=False)

    assert response.status_code == 500
    assert response.json() == {"detail": "Failed to get transcoding link"}


def test_cache_stats_route_when_first_segment_cache_has_entries_then_includes_first_segment_cache_stats():
    client = _build_proxy_client()
    proxy_module.first_segment_cache_service.clear()

    mock_config = SimpleNamespace(
        playback=SimpleNamespace(
            first_segment_cache_enabled=True,
            first_segment_cache_mb=1,
            first_segment_cache_ttl_sec=3600,
        )
    )

    with (
        patch("app.api.proxy.config.get_quark_cookie", return_value="test-cookie"),
        patch("app.services.first_segment_cache_service.get_config_service") as mock_get_config_service,
        patch("app.api.proxy.ProxyService") as mock_proxy_service_cls,
    ):
        mock_get_config_service.return_value.get_config.return_value = mock_config
        mock_proxy_service = AsyncMock()
        mock_proxy_service.get_cache_stats = AsyncMock(return_value={"total_entries": 2, "mode": "unified"})
        mock_proxy_service_cls.return_value.__aenter__.return_value = mock_proxy_service
        mock_proxy_service_cls.return_value.__aexit__.return_value = None

        proxy_module.first_segment_cache_service.put(
            "file123:download",
            data=b"abcdefgh",
            total_length=2048,
            content_type="video/mp4",
            accept_ranges="bytes",
            etag="etag-1",
            last_modified=None,
        )

        response = client.get("/api/proxy/cache/stats")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "stats": {
            "total_entries": 2,
            "mode": "unified",
            "first_segment_cache": {
                "enabled": True,
                "entry_count": 1,
                "total_bytes": 8,
                "segment_size_bytes": 1048576,
                "ttl_seconds": 3600,
            },
        },
    }
    mock_proxy_service.get_cache_stats.assert_awaited_once()
    proxy_module.first_segment_cache_service.clear()


def test_clear_cache_route_when_first_segment_cache_has_entries_then_clears_both_caches():
    client = _build_proxy_client()
    proxy_module.first_segment_cache_service.clear()

    mock_config = SimpleNamespace(
        playback=SimpleNamespace(
            first_segment_cache_enabled=True,
            first_segment_cache_mb=1,
            first_segment_cache_ttl_sec=3600,
        )
    )

    with (
        patch("app.api.proxy.config.get_quark_cookie", return_value="test-cookie"),
        patch("app.services.first_segment_cache_service.get_config_service") as mock_get_config_service,
        patch("app.api.proxy.ProxyService") as mock_proxy_service_cls,
    ):
        mock_get_config_service.return_value.get_config.return_value = mock_config
        mock_proxy_service = AsyncMock()
        mock_proxy_service.clear_cache = AsyncMock()
        mock_proxy_service_cls.return_value.__aenter__.return_value = mock_proxy_service
        mock_proxy_service_cls.return_value.__aexit__.return_value = None

        proxy_module.first_segment_cache_service.put(
            "file123:download",
            data=b"abcdefgh",
            total_length=2048,
            content_type="video/mp4",
            accept_ranges="bytes",
            etag="etag-1",
            last_modified=None,
        )

        assert proxy_module.first_segment_cache_service.get("file123:download") is not None

        response = client.post("/api/proxy/cache/clear")

        assert proxy_module.first_segment_cache_service.get("file123:download") is None

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "message": "Cache cleared"}
    mock_proxy_service.clear_cache.assert_awaited_once()
    proxy_module.first_segment_cache_service.clear()
