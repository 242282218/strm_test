import pytest

from app.utils.strm_url import (
    build_proxy_url,
    extract_file_id_from_proxy_url,
    extract_file_id_from_strm_content,
    read_strm_file_content,
)
from app.services.playbackinfo_hook import PlaybackInfoHook
from app.services.emby_proxy_service import EmbyProxyService


@pytest.mark.parametrize(
    "url,file_id",
    [
        ("http://localhost:8000/api/proxy/redirect/abc123", "abc123"),
        ("/api/proxy/stream/XYZ789", "XYZ789"),
        ("/api/proxy/video/aaa111?x=1", "aaa111"),
    ],
)
def test_extract_file_id_from_proxy_url(url, file_id):
    assert extract_file_id_from_proxy_url(url) == file_id


@pytest.mark.parametrize(
    "content,file_id",
    [
        ("quark://qk_001", "qk_001"),
        ("http://localhost:8000/api/proxy/redirect/xyz888", "xyz888"),
        ("/api/proxy/stream/stream555", "stream555"),
    ],
)
def test_extract_file_id_from_strm_content(content, file_id):
    assert extract_file_id_from_strm_content(content) == file_id


@pytest.mark.asyncio
async def test_read_strm_file_content(tmp_path):
    path = tmp_path / "a.strm"
    path.write_text("  quark://p1  ", encoding="utf-8")
    content = await read_strm_file_content(str(path))
    assert content == "quark://p1"


@pytest.mark.asyncio
async def test_playbackinfo_hook_sets_direct_stream_url_from_strm(tmp_path):
    strm_path = tmp_path / "movie.strm"
    strm_path.write_text("http://localhost:8000/api/proxy/redirect/fid123", encoding="utf-8")

    hook = PlaybackInfoHook(
        emby_client=object(),
        quark_service=object(),
        proxy_base_url="http://localhost:8000",
    )

    source = {
        "Id": "media123",
        "Path": str(strm_path),
        "IsRemote": True,
    }

    updated = await hook._process_media_source(source, item_id="1", user_id="u")
    assert updated["DirectStreamUrl"].startswith("http://localhost:8000/api/proxy/stream/fid123")


@pytest.mark.asyncio
async def test_emby_proxy_extract_file_id_from_strm(tmp_path):
    strm_path = tmp_path / "movie.strm"
    strm_path.write_text("http://localhost:8000/api/proxy/stream/fid999", encoding="utf-8")

    service = EmbyProxyService(
        emby_base_url="http://localhost:8096",
        api_key="k",
        cookie="c",
    )

    file_id = await service._extract_file_id_from_strm(str(strm_path))
    assert file_id == "fid999"


@pytest.mark.parametrize(
    "mode",
    ["redirect", "stream", "video"],
)
def test_build_proxy_url(mode):
    url = build_proxy_url("http://localhost:8000/", "abc", mode=mode)
    assert url == f"http://localhost:8000/api/proxy/{mode}/abc"
