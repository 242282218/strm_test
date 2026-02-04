import os
import pytest

from app.services.playbackinfo_hook import PlaybackInfoHook
from app.utils.strm_url import build_proxy_url


class DummyEmbyClient:
    def __init__(self, playback_info):
        self._playback_info = playback_info

    async def get_playback_info(self, item_id: str, user_id: str, media_source_id: str | None = None):
        return self._playback_info


@pytest.mark.asyncio
async def test_playbackinfo_end_to_end_strm_to_proxy(tmp_path):
    strm_path = tmp_path / "movie.strm"
    strm_path.write_text(build_proxy_url("http://localhost:8000", "fid777", mode="redirect"), encoding="utf-8")

    playback_info = {
        "MediaSources": [
            {
                "Id": "media_source_1",
                "Path": str(strm_path),
                "IsRemote": True,
            }
        ]
    }

    hook = PlaybackInfoHook(
        emby_client=DummyEmbyClient(playback_info),
        quark_service=object(),
        proxy_base_url="http://localhost:8000",
    )

    result = await hook.hook_playback_info(item_id="1", user_id="u")
    media_source = result["MediaSources"][0]

    assert media_source["DirectStreamUrl"].startswith("http://localhost:8000/api/proxy/stream/fid777")
    assert media_source["SupportsDirectPlay"] is True
    assert media_source["SupportsDirectStream"] is True


@pytest.mark.asyncio
async def test_playbackinfo_end_to_end_proxy_path_to_proxy_url():
    playback_info = {
        "MediaSources": [
            {
                "Id": "media_source_2",
                "Path": "http://localhost:8000/api/proxy/stream/fid888",
                "IsRemote": True,
            }
        ]
    }

    hook = PlaybackInfoHook(
        emby_client=DummyEmbyClient(playback_info),
        quark_service=object(),
        proxy_base_url="http://localhost:8000",
    )

    result = await hook.hook_playback_info(item_id="2", user_id="u")
    media_source = result["MediaSources"][0]

    assert media_source["DirectStreamUrl"].startswith("http://localhost:8000/api/proxy/stream/fid888")


@pytest.mark.asyncio
async def test_playbackinfo_multiple_media_sources_local_and_remote(tmp_path):
    strm_path = tmp_path / "movie.strm"
    strm_path.write_text(build_proxy_url("http://localhost:8000", "fid999", mode="redirect"), encoding="utf-8")

    playback_info = {
        "MediaSources": [
            {
                "Id": "local_1",
                "Path": str(tmp_path / "local_movie.mkv"),
                "IsRemote": False,
            },
            {
                "Id": "remote_1",
                "Path": str(strm_path),
                "IsRemote": True,
            },
            {
                "Id": "live_1",
                "Path": "http://example.com/live.m3u8",
                "IsRemote": True,
                "IsInfiniteStream": True,
            },
        ]
    }

    hook = PlaybackInfoHook(
        emby_client=DummyEmbyClient(playback_info),
        quark_service=object(),
        proxy_base_url="http://localhost:8000",
    )

    result = await hook.hook_playback_info(item_id="3", user_id="u")
    sources = result["MediaSources"]

    # local media should be preserved without proxy rewrite
    local_source = next(s for s in sources if s["Id"] == "local_1")
    assert local_source.get("DirectStreamUrl") is None

    # remote STRM should be rewritten to proxy stream URL
    remote_source = next(s for s in sources if s["Id"] == "remote_1")
    assert remote_source["DirectStreamUrl"].startswith("http://localhost:8000/api/proxy/stream/fid999")

    # infinite stream should be filtered out
    assert all(s["Id"] != "live_1" for s in sources)
