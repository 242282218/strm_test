"""
稳定播放入口相关测试
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.services.emby_proxy_service import EmbyProxyService
from app.services.playbackinfo_hook import PlaybackInfoHook


@pytest.mark.asyncio
async def test_playback_info_hook_when_remote_source_has_stable_media_url_then_keeps_media_id_entrypoint():
    emby_client = AsyncMock()
    emby_client.get_playback_info = AsyncMock(
        return_value={
            "MediaSources": [
                {
                    "Id": "media_source_1",
                    "Path": "http://proxy.example:18097/strm/v1/m/media123/Avatar%20(2009).mkv",
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

    result = await hook.hook_playback_info(item_id="item1", user_id="user1", is_web_client=False)

    media_source = result["MediaSources"][0]
    assert media_source["DirectStreamUrl"] == (
        "http://proxy.example:18097/strm/v1/m/media123/Avatar%20(2009).mkv?Static=true"
    )


@pytest.mark.asyncio
async def test_playback_info_hook_when_local_strm_contains_stable_media_url_with_query_then_keeps_stable_entrypoint(
    tmp_path,
):
    strm_file = tmp_path / "movie.strm"
    strm_file.write_text(
        "http://proxy.example:18097/strm/v1/m/media123/Avatar%20(2009).mkv?token=abc\n",
        encoding="utf-8",
    )

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
    assert media_source["DirectStreamUrl"] == (
        "http://proxy.example:18097/strm/v1/m/media123/Avatar%20(2009).mkv?token=abc&Static=true"
    )
    assert media_source["TranscodingUrl"] == (
        "/Videos/item1/master.m3u8?PlaySessionId=session77&MediaSourceId=media_source_1&smart_media_proxy=1"
    )


@pytest.mark.asyncio
async def test_playback_info_hook_when_force_proxy_client_then_rewrites_to_emby_stream_url():
    emby_client = AsyncMock()
    emby_client.get_playback_info = AsyncMock(
        return_value={
            "MediaSources": [
                {
                    "Id": "media_source_1",
                    "Path": "http://proxy.example:18097/strm/v1/m/media123/Avatar%20(2009).mkv",
                    "IsRemote": True,
                    "Container": "mkv",
                }
            ]
        }
    )

    hook = PlaybackInfoHook(
        emby_client=emby_client,
        quark_service=AsyncMock(),
        proxy_base_url="http://proxy.example:18097",
    )

    mock_config = SimpleNamespace(
        playback=SimpleNamespace(direct_first=True, force_proxy_clients=["infuse"], force_proxy_hosts=[])
    )
    with patch("app.services.playback_decision_service.get_config_service") as mock_get_config_service:
        mock_get_config_service.return_value.get_config.return_value = mock_config
        result = await hook.hook_playback_info(
            item_id="item1",
            user_id="user1",
            is_web_client=False,
            client_name="Infuse",
        )

    media_source = result["MediaSources"][0]
    assert media_source["DirectStreamUrl"] == (
        "http://proxy.example:18097/Videos/item1/stream?MediaSourceId=media_source_1&Static=true"
        "&smart_media_proxy=1&container=mkv"
    )


@pytest.mark.asyncio
async def test_resolve_media_source_file_id_when_media_source_path_is_stable_url_then_uses_media_mapping():
    service = EmbyProxyService(
        emby_base_url="http://emby.example:8096",
        api_key="test-key",
        cookie="test-cookie",
        proxy_base_url="http://proxy.example:18097",
    )
    mapping = service.media_mapping_service.get_or_create(
        provider_file_id="real_quark_fid_144",
        source_path="/影视收藏/电影/你的名字。 (2016) [tmdbid=372058]/movie.mkv",
        display_name="movie.mkv",
    )

    service.emby_client = AsyncMock()
    service.emby_client.get_items = AsyncMock(
        return_value={
            "Id": "item144",
            "MediaSources": [
                {
                    "Id": "mediasource_144",
                    "Path": f"http://proxy.example:18097/strm/v1/m/{mapping.media_id}/movie.mkv",
                    "IsRemote": True,
                }
            ],
        }
    )
    service.quark_service = AsyncMock()
    service.quark_service.get_file_by_path = AsyncMock(return_value=SimpleNamespace(fid="should_not_be_used"))

    file_id = await service.resolve_media_source_file_id(item_id="item144", media_source_id="mediasource_144")

    assert file_id == "real_quark_fid_144"
    service.quark_service.get_file_by_path.assert_not_awaited()
