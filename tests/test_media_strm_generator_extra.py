from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services.media import strm_generator as sg


class _FakeFileModel:
    def __init__(self, *, file_name: str, fid: str, is_dir: bool, category: int, size: int = 0) -> None:
        self.file_name = file_name
        self.fid = fid
        self.is_dir = is_dir
        self.category = category
        self.size = size


class _FakeQuarkService:
    def __init__(self, cookie: str) -> None:
        self.cookie = cookie
        self.files_by_parent: dict[str, list[_FakeFileModel]] = {}
        self.calls: list[str] = []
        self.transcoding_link = SimpleNamespace(url="https://direct.example/transcode")
        self.download_link = SimpleNamespace(url="https://direct.example/download")

    async def get_files(self, parent: str, only_video: bool = False):
        self.calls.append(parent)
        return self.files_by_parent.get(parent, [])

    async def get_transcoding_link(self, _fid: str):
        return self.transcoding_link

    async def get_download_link(self, _fid: str):
        return self.download_link

    async def close(self):
        return None


class _FakeMediaMappingService:
    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    def get_or_create(self, *, provider_file_id: str, source_path: str, display_name: str):
        self.calls.append(
            {
                "provider_file_id": provider_file_id,
                "source_path": source_path,
                "display_name": display_name,
            }
        )
        return SimpleNamespace(media_id=f"mid-{provider_file_id}", display_name=display_name)


@pytest.fixture
def fake_env(monkeypatch: pytest.MonkeyPatch):
    service_box: dict[str, _FakeQuarkService] = {}
    mapping_box: dict[str, _FakeMediaMappingService] = {}

    def make_quark(cookie: str):
        service = _FakeQuarkService(cookie)
        service_box["service"] = service
        return service

    def make_mapping():
        mapping = _FakeMediaMappingService()
        mapping_box["mapping"] = mapping
        return mapping

    monkeypatch.setattr(sg, "QuarkService", make_quark)
    monkeypatch.setattr(sg, "MediaMappingService", make_mapping)
    return service_box, mapping_box


def _build_generator(tmp_path: Path, fake_env, **kwargs) -> sg.STRMGenerator:
    generator = sg.STRMGenerator(
        cookie="cookie",
        output_dir=str(tmp_path),
        base_url=kwargs.pop("base_url", "http://localhost:8000"),
        strm_url_mode=kwargs.pop("strm_url_mode", "redirect"),
        overwrite_existing=kwargs.pop("overwrite_existing", False),
        use_transcoding=kwargs.pop("use_transcoding", True),
        **kwargs,
    )
    service_box, mapping_box = fake_env
    generator.service = service_box["service"]
    generator.media_mapping_service = mapping_box["mapping"]
    return generator


@pytest.mark.asyncio
async def test_init_fixes_base_url_and_unknown_mode_raises(tmp_path: Path, fake_env) -> None:
    generator = _build_generator(tmp_path, fake_env, base_url="https:/example.com/")
    try:
        assert generator.base_url == "https://example.com"
        generator.strm_url_mode = "unknown"  # type: ignore[assignment]
        with pytest.raises(ValueError, match="Unknown strm_url_mode"):
            await generator._generate_video_url("fid-1", "a/b.mp4")
    finally:
        await generator.close()


@pytest.mark.asyncio
async def test_get_all_files_recursive_and_filters_video(tmp_path: Path, fake_env) -> None:
    generator = _build_generator(tmp_path, fake_env)
    service = generator.service
    service.files_by_parent = {
        "root": [
            _FakeFileModel(file_name="sub", fid="dir-1", is_dir=True, category=0),
            _FakeFileModel(file_name="readme.txt", fid="f-1", is_dir=False, category=2, size=1),
            _FakeFileModel(file_name="movie.mkv", fid="f-2", is_dir=False, category=1, size=2),
        ],
        "dir-1": [
            _FakeFileModel(file_name="ep1.mp4", fid="f-3", is_dir=False, category=1, size=3),
        ],
    }

    try:
        recursive_files = await generator._get_all_files("root", "", only_video=True, recursive=True)
        non_recursive_files = await generator._get_all_files("root", "", only_video=True, recursive=False)
    finally:
        await generator.close()

    assert [item["remote_path"] for item in recursive_files] == ["sub/ep1.mp4", "movie.mkv"]
    assert [item["id"] for item in non_recursive_files] == ["f-2"]


@pytest.mark.asyncio
async def test_get_all_files_handles_service_error(tmp_path: Path, fake_env, monkeypatch: pytest.MonkeyPatch) -> None:
    generator = _build_generator(tmp_path, fake_env)
    errors: list[str] = []
    monkeypatch.setattr(sg.logger, "error", lambda message: errors.append(message))

    async def broken_get_files(parent: str, only_video: bool = False):
        raise RuntimeError("fetch failed")

    generator.service.get_files = broken_get_files  # type: ignore[method-assign]

    try:
        files = await generator._get_all_files("root", "", only_video=True, recursive=True)
    finally:
        await generator.close()

    assert files == []
    assert any("Failed to get files from root" in message for message in errors)


@pytest.mark.asyncio
async def test_generate_video_url_modes(tmp_path: Path, fake_env, monkeypatch: pytest.MonkeyPatch) -> None:
    generator = _build_generator(tmp_path, fake_env, base_url="http://proxy.example:9000")

    cfg = SimpleNamespace(get_webdav_config=lambda: {"mount_path": "/dav", "username": "u", "password": "p@ss"})
    monkeypatch.setattr(sg, "get_config", lambda: cfg)

    try:
        redirect_url = await generator._generate_video_url("fid-r", "dir/file.mkv")
        generator.strm_url_mode = "stream"
        stream_url = await generator._generate_video_url("fid-s", "dir/file.mkv")
        generator.strm_url_mode = "direct"
        generator.use_transcoding = True
        direct_transcoding = await generator._generate_video_url("fid-d1", "dir/file.mkv")
        generator.use_transcoding = False
        direct_download = await generator._generate_video_url("fid-d2", "dir/file.mkv")
        generator.strm_url_mode = "webdav"
        webdav_url = await generator._generate_video_url("fid-w", "dir/file name.mkv")
    finally:
        await generator.close()

    assert redirect_url == "http://proxy.example:9000/strm/v1/m/mid-fid-r/file.mkv"
    assert stream_url == "http://proxy.example:9000/api/proxy/stream/fid-s"
    assert direct_transcoding == "https://direct.example/transcode"
    assert direct_download == "https://direct.example/download"
    assert webdav_url.startswith("http://u:p%40ss@proxy.example:9000/dav/")
    assert webdav_url.endswith("/dir/file%20name.mkv")


@pytest.mark.asyncio
async def test_generate_single_strm_paths_and_overwrite(tmp_path: Path, fake_env) -> None:
    generator = _build_generator(tmp_path, fake_env, overwrite_existing=False)

    try:
        rel = await generator._generate_single_strm(
            {"id": "fid-1", "name": "movie.mkv", "remote_path": "A/movie.mkv", "size": 1, "category": 1}
        )
        assert rel == "A/movie.mkv.strm"
        created_path = tmp_path / "A" / "movie.mkv.strm"
        assert created_path.exists()

        skipped = await generator._generate_single_strm(
            {"id": "fid-1", "name": "movie.mkv", "remote_path": "A/movie.mkv", "size": 1, "category": 1}
        )
        assert skipped is None

        generator.overwrite_existing = True
        overwritten = await generator._generate_single_strm(
            {"id": "fid-1", "name": "movie.mkv", "remote_path": "A/movie.mkv", "size": 1, "category": 1}
        )
        assert overwritten == "A/movie.mkv.strm"
    finally:
        await generator.close()


@pytest.mark.asyncio
async def test_generate_single_strm_raises_on_url_error(
    tmp_path: Path, fake_env, monkeypatch: pytest.MonkeyPatch
) -> None:
    generator = _build_generator(tmp_path, fake_env, overwrite_existing=True)
    monkeypatch.setattr(
        generator, "_generate_video_url", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("url fail"))
    )

    try:
        with pytest.raises(RuntimeError, match="url fail"):
            await generator._generate_single_strm(
                {"id": "fid-1", "name": "movie.mkv", "remote_path": "A/movie.mkv", "size": 1, "category": 1}
            )
    finally:
        await generator.close()


@pytest.mark.asyncio
async def test_generate_strm_files_success_and_limits(
    tmp_path: Path, fake_env, monkeypatch: pytest.MonkeyPatch
) -> None:
    generator = _build_generator(tmp_path, fake_env, overwrite_existing=True)

    fake_files = [
        {"id": "1", "name": "a.mkv", "remote_path": "a.mkv", "size": 1, "category": 1},
        {"id": "2", "name": "b.mkv", "remote_path": "b.mkv", "size": 1, "category": 1},
        {"id": "3", "name": "c.mkv", "remote_path": "c.mkv", "size": 1, "category": 1},
    ]

    async def fake_get_all(*_args, **_kwargs):
        return list(fake_files)

    async def fake_generate_single(file_info: dict):
        if file_info["id"] == "2":
            return None
        return f"{file_info['remote_path']}.strm"

    monkeypatch.setattr(generator, "_get_all_files", fake_get_all)
    monkeypatch.setattr(generator, "_generate_single_strm", fake_generate_single)

    try:
        stats = await generator.generate_strm_files(root_id="root", max_files=2, concurrent_limit=0)
    finally:
        await generator.close()

    assert stats["total_files"] == 3
    assert stats["generated_files"] == 1
    assert stats["skipped_files"] == 1
    assert stats["failed_files"] == 0
    assert stats["files"] == ["a.mkv.strm"]


@pytest.mark.asyncio
async def test_generate_strm_files_collects_exceptions(
    tmp_path: Path, fake_env, monkeypatch: pytest.MonkeyPatch
) -> None:
    generator = _build_generator(tmp_path, fake_env, overwrite_existing=True)

    async def fake_get_all(*_args, **_kwargs):
        return [{"id": "1", "name": "a.mkv", "remote_path": "a.mkv", "size": 1, "category": 1}]

    async def broken_single(_file_info: dict):
        raise RuntimeError("single fail")

    monkeypatch.setattr(generator, "_get_all_files", fake_get_all)
    monkeypatch.setattr(generator, "_generate_single_strm", broken_single)

    try:
        stats = await generator.generate_strm_files(root_id="root")
    finally:
        await generator.close()

    assert stats["generated_files"] == 0
    assert stats["failed_files"] == 1
    assert any("single fail" in err for err in stats["errors"])


@pytest.mark.asyncio
async def test_generate_strm_files_top_level_exception(
    tmp_path: Path, fake_env, monkeypatch: pytest.MonkeyPatch
) -> None:
    generator = _build_generator(tmp_path, fake_env)

    async def broken_get_all(*_args, **_kwargs):
        raise RuntimeError("all fail")

    monkeypatch.setattr(generator, "_get_all_files", broken_get_all)

    try:
        stats = await generator.generate_strm_files(root_id="root")
    finally:
        await generator.close()

    assert stats["generated_files"] == 0
    assert any("all fail" in err for err in stats["errors"])


@pytest.mark.asyncio
async def test_generate_strm_from_quark_uses_config_and_closes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    config = SimpleNamespace(
        get_quark_cookie=lambda: "cfg-cookie",
        get_quark_root_id=lambda: "cfg-root",
        get_quark_only_video=lambda: True,
    )
    monkeypatch.setattr(sg, "get_config", lambda: config)

    created: dict[str, Any] = {}

    class DummyGenerator:
        def __init__(self, **kwargs) -> None:
            created["kwargs"] = kwargs
            self.closed = False

        async def generate_strm_files(self, **kwargs):
            created["generate_args"] = kwargs
            return {"ok": True}

        async def close(self):
            created["closed"] = True

    monkeypatch.setattr(sg, "STRMGenerator", DummyGenerator)

    result = await sg.generate_strm_from_quark(
        cookie=None,
        output_dir=str(tmp_path),
        root_id=None,
        only_video=None,
        max_files=7,
        base_url="http://x",
        strm_url_mode="stream",
    )

    assert result == {"ok": True}
    assert created["kwargs"]["cookie"] == "cfg-cookie"
    assert created["kwargs"]["output_dir"] == str(tmp_path)
    assert created["kwargs"]["base_url"] == "http://x"
    assert created["kwargs"]["strm_url_mode"] == "stream"
    assert created["generate_args"] == {"root_id": "cfg-root", "only_video": True, "max_files": 7}
    assert created["closed"] is True


@pytest.mark.asyncio
async def test_generate_strm_from_quark_requires_cookie(monkeypatch: pytest.MonkeyPatch) -> None:
    config = SimpleNamespace(
        get_quark_cookie=lambda: "",
        get_quark_root_id=lambda: "cfg-root",
        get_quark_only_video=lambda: True,
    )
    monkeypatch.setattr(sg, "get_config", lambda: config)

    with pytest.raises(ValueError, match="Cookie is required"):
        await sg.generate_strm_from_quark(cookie=None)
