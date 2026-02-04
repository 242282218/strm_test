import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.dependencies import get_quark_cookie
from app.models.quark import FileModel
from app.services.quark_service import QuarkService


class DummyDB:
    def __init__(self, *args, **kwargs):
        pass

    def save_record(self, remote_dir: str) -> bool:
        return True

    def close(self):
        return None


@pytest.fixture
def client(monkeypatch):
    import app.api.strm as strm_api

    app.dependency_overrides[get_quark_cookie] = lambda: "dummy_cookie"
    monkeypatch.setattr(strm_api, "Database", DummyDB)

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


def _dir(fid: str, name: str) -> FileModel:
    return FileModel(
        fid=fid,
        file_name=name,
        category=0,
        size=0,
        l_created_at=0,
        l_updated_at=0,
        file=False,
        created_at=0,
        updated_at=0,
        mime_type=None,
        etag=None,
    )


def _file(fid: str, name: str) -> FileModel:
    return FileModel(
        fid=fid,
        file_name=name,
        category=1,
        size=123,
        l_created_at=0,
        l_updated_at=0,
        file=True,
        created_at=0,
        updated_at=0,
        mime_type="video/mp4",
        etag=None,
    )


@pytest.mark.parametrize(
    "mode,expected_substring",
    [
        ("redirect", "/api/proxy/redirect/f1"),
        ("webdav", "/dav/video/a.mp4"),
    ],
)
def test_strm_scan_generates_strm_for_modes(client, tmp_path, monkeypatch, mode, expected_substring):
    async def fake_get_file_by_path(self, path: str):
        assert path == "/video"
        return _dir("dir1", "video")

    async def fake_get_files(self, parent: str, page_size: int = 100, only_video: bool = False):
        if parent == "dir1":
            return [_file("f1", "a.mp4")]
        return []

    monkeypatch.setattr(QuarkService, "get_file_by_path", fake_get_file_by_path, raising=True)
    monkeypatch.setattr(QuarkService, "get_files", fake_get_files, raising=True)

    if mode == "webdav":
        import app.services.strm_generator as strm_gen_mod

        class DummyCfg:
            def get_webdav_config(self):
                return {
                    "enabled": True,
                    "fallback_enabled": True,
                    "mount_path": "/dav",
                    "username": "u",
                    "password": "p",
                }

        monkeypatch.setattr(strm_gen_mod, "get_config", lambda: DummyCfg(), raising=True)

    out_dir = tmp_path / "out"
    response = client.post(
        "/api/strm/scan",
        params={
            "remote_path": "/video",
            "local_path": str(out_dir),
            "recursive": "true",
            "concurrent_limit": "2",
            "base_url": "http://example.com:8000",
            "strm_url_mode": mode,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
    assert data["strms"] == ["video/a.mp4.strm"]

    strm_path = out_dir / "video" / "a.mp4.strm"
    assert strm_path.exists()
    content = strm_path.read_text(encoding="utf-8").strip()

    assert expected_substring in content

    if mode == "webdav":
        assert "u:p@" in content
    else:
        assert "path=video/a.mp4" in content
