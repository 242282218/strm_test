from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest

from app.services import webdav as webdav_pkg
from app.services.webdav import provider as provider_mod
from app.services.webdav import service as service_mod
from app.services.webdav.provider import QuarkDAVProvider
from app.services.webdav.resource import DAVError, QuarkFileResource, QuarkFolderResource


class AsyncCache:
    def __init__(self, get_value: Any = None) -> None:
        self.get_value = get_value
        self.last_get_key: str | None = None
        self.set_calls: list[tuple[str, Any, int]] = []

    async def get(self, key: str) -> Any:
        self.last_get_key = key
        return self.get_value

    async def set(self, key: str, value: Any, ttl: int) -> None:
        self.set_calls.append((key, value, ttl))


class AsyncPathResolver:
    def __init__(self, result: Any = None, error: Exception | None = None) -> None:
        self.result = result
        self.error = error
        self.paths: list[str] = []

    async def get_file_by_path(self, path: str) -> Any:
        self.paths.append(path)
        if self.error is not None:
            raise self.error
        return self.result


def _make_lookup_provider(cache: AsyncCache, resolver: AsyncPathResolver) -> QuarkDAVProvider:
    provider = QuarkDAVProvider.__new__(QuarkDAVProvider)
    provider.cache_service = cache
    provider.quark_service = resolver
    provider.sync_call = lambda coro: asyncio.run(coro)  # type: ignore[method-assign]
    return provider


def _make_environ(provider: Any) -> dict[str, Any]:
    return {"wsgidav.provider": provider}


def _make_file_info(*, fid: str, name: str, is_dir: bool, size: int = 0) -> SimpleNamespace:
    return SimpleNamespace(
        fid=fid,
        file_name=name,
        is_dir=is_dir,
        size=size,
        created_at=1_700_000_000,
        updated_at=1_700_000_000,
    )


def test_webdav_init_exports_get_webdav_app() -> None:
    assert "get_webdav_app" in webdav_pkg.__all__
    assert webdav_pkg.get_webdav_app is service_mod.get_webdav_app


def test_provider_sync_call_executes_coroutine(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = QuarkDAVProvider.__new__(QuarkDAVProvider)
    sentinel = object()
    captured: dict[str, Any] = {}

    def fake_async_to_sync(factory):
        captured["payload"] = factory()
        return lambda: "done"

    monkeypatch.setattr(provider_mod, "async_to_sync", fake_async_to_sync)

    assert QuarkDAVProvider.sync_call(provider, sentinel) == "done"
    assert captured["payload"] is sentinel


def test_provider_init_warns_when_cookie_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    warnings: list[str] = []
    fake_cache = object()

    monkeypatch.setattr(
        provider_mod,
        "get_config_service",
        lambda: SimpleNamespace(get_config=lambda: SimpleNamespace(quark=SimpleNamespace(cookie=""))),
    )
    monkeypatch.setattr(provider_mod, "get_cache_service", lambda: fake_cache)
    monkeypatch.setattr(provider_mod.logger, "warning", lambda message: warnings.append(message))

    class FakeQuarkService:
        def __init__(self, cookie: str) -> None:
            self.cookie = cookie

    monkeypatch.setattr(provider_mod, "QuarkService", FakeQuarkService)

    provider = QuarkDAVProvider()

    assert provider.cache_service is fake_cache
    assert provider.quark_service.cookie == ""
    assert any("Quark cookie not found" in message for message in warnings)


def test_get_resource_inst_root_returns_folder_resource() -> None:
    cache = AsyncCache()
    resolver = AsyncPathResolver()
    provider = _make_lookup_provider(cache, resolver)

    resource = QuarkDAVProvider.get_resource_inst(provider, "/", _make_environ(provider))

    assert isinstance(resource, QuarkFolderResource)
    assert resource.path == "/"


def test_get_resource_inst_uses_cached_file_info() -> None:
    file_info = _make_file_info(fid="file-1", name="movie.mkv", is_dir=False, size=123)
    cache = AsyncCache(get_value=file_info)
    resolver = AsyncPathResolver(result=None)
    provider = _make_lookup_provider(cache, resolver)

    resource = QuarkDAVProvider.get_resource_inst(provider, "/movie.mkv", _make_environ(provider))

    assert isinstance(resource, QuarkFileResource)
    assert cache.last_get_key == "webdav:path:movie.mkv"
    assert resolver.paths == []


def test_get_resource_inst_fetches_remote_and_writes_cache_on_miss() -> None:
    dir_info = _make_file_info(fid="dir-1", name="Movies", is_dir=True)
    cache = AsyncCache(get_value=None)
    resolver = AsyncPathResolver(result=dir_info)
    provider = _make_lookup_provider(cache, resolver)

    resource = QuarkDAVProvider.get_resource_inst(provider, "/Movies", _make_environ(provider))

    assert isinstance(resource, QuarkFolderResource)
    assert resolver.paths == ["Movies"]
    assert cache.set_calls == [("webdav:path:Movies", dir_info, 300)]


def test_get_resource_inst_returns_none_for_missing_path() -> None:
    cache = AsyncCache(get_value=None)
    resolver = AsyncPathResolver(result=None)
    provider = _make_lookup_provider(cache, resolver)

    resource = QuarkDAVProvider.get_resource_inst(provider, "/missing", _make_environ(provider))

    assert resource is None


def test_get_resource_inst_handles_not_found_error_as_none() -> None:
    cache = AsyncCache(get_value=None)
    resolver = AsyncPathResolver(error=RuntimeError("Path not found"))
    provider = _make_lookup_provider(cache, resolver)

    resource = QuarkDAVProvider.get_resource_inst(provider, "/missing", _make_environ(provider))

    assert resource is None


def test_get_resource_inst_wraps_unexpected_error_as_daverror() -> None:
    cache = AsyncCache(get_value=None)
    resolver = AsyncPathResolver(error=RuntimeError("unexpected boom"))
    provider = _make_lookup_provider(cache, resolver)

    with pytest.raises(DAVError) as exc_info:
        QuarkDAVProvider.get_resource_inst(provider, "/broken", _make_environ(provider))

    assert exc_info.value.value == 500


def _build_resource_provider(
    *,
    children: list[SimpleNamespace] | None = None,
    get_files_error: Exception | None = None,
    transcoding_link: Any = None,
    download_link: Any = None,
    transcode_error: Exception | None = None,
) -> Any:
    children = children or []

    class FakeQuarkService:
        def get_files(self, parent: str):
            if get_files_error is not None:
                raise get_files_error
            return children

        def get_transcoding_link(self, _fid: str):
            if transcode_error is not None:
                raise transcode_error
            return transcoding_link

        def get_download_link(self, _fid: str):
            return download_link

    provider = SimpleNamespace()
    provider.quark_service = FakeQuarkService()
    provider.sync_call = lambda value: value
    return provider


def test_folder_resource_lists_members_and_resolves_child_type() -> None:
    children = [
        _make_file_info(fid="d1", name="Season01", is_dir=True),
        _make_file_info(fid="f1", name="episode.mkv", is_dir=False, size=10),
    ]
    provider = _build_resource_provider(children=children)
    folder = QuarkFolderResource(
        "/Shows",
        _make_environ(provider),
        _make_file_info(fid="root", name="Shows", is_dir=True),
        provider,
    )

    assert folder.get_member_names() == ["Season01", "episode.mkv"]
    assert isinstance(folder.get_member("Season01"), QuarkFolderResource)
    assert isinstance(folder.get_member("episode.mkv"), QuarkFileResource)
    assert folder.get_member("missing") is None


def test_folder_resource_uses_root_fid_when_file_info_missing() -> None:
    captured_parents: list[str] = []

    class FakeQuarkService:
        def get_files(self, parent: str):
            captured_parents.append(parent)
            return []

    provider = SimpleNamespace(quark_service=FakeQuarkService(), sync_call=lambda value: value)
    folder = QuarkFolderResource("/", _make_environ(provider), None, provider)

    assert folder.get_member_names() == []
    assert captured_parents == ["0"]


def test_folder_resource_wraps_children_error_as_daverror() -> None:
    provider = _build_resource_provider(get_files_error=RuntimeError("children failed"))
    folder = QuarkFolderResource(
        "/Shows",
        _make_environ(provider),
        _make_file_info(fid="root", name="Shows", is_dir=True),
        provider,
    )

    with pytest.raises(DAVError) as exc_info:
        folder.get_member_names()

    assert exc_info.value.value == 500


def test_file_resource_metadata_and_timestamp_conversion() -> None:
    provider = _build_resource_provider()
    file_info = _make_file_info(fid="f1", name="movie.mkv", is_dir=False, size=321)
    file_info.created_at = 32_503_680_001_000  # milliseconds
    file_info.updated_at = "1700000000"
    resource = QuarkFileResource("/movie.mkv", _make_environ(provider), file_info, provider)

    assert resource.get_content_length() == 321
    assert resource.get_content_type() is not None
    assert resource.get_creation_date() == 32_503_680_001.0
    assert resource.get_last_modified() == 1_700_000_000.0
    assert resource._safe_timestamp(None) is None
    assert resource._safe_timestamp("bad-ts") is None


def test_file_resource_get_content_prefers_transcoding_link() -> None:
    link = SimpleNamespace(url="https://media.example/transcode")
    provider = _build_resource_provider(transcoding_link=link, download_link=SimpleNamespace(url="unused"))
    resource = QuarkFileResource(
        "/movie.mkv",
        _make_environ(provider),
        _make_file_info(fid="f1", name="movie.mkv", is_dir=False, size=10),
        provider,
    )

    with pytest.raises(DAVError) as exc_info:
        resource.get_content()

    assert exc_info.value.value == 307
    assert ("Location", "https://media.example/transcode") in exc_info.value.add_headers


def test_file_resource_get_content_falls_back_to_download_link() -> None:
    provider = _build_resource_provider(
        transcoding_link=SimpleNamespace(url=""),
        download_link=SimpleNamespace(url="https://media.example/download"),
    )
    resource = QuarkFileResource(
        "/movie.mkv",
        _make_environ(provider),
        _make_file_info(fid="f2", name="movie.mkv", is_dir=False, size=10),
        provider,
    )

    with pytest.raises(DAVError) as exc_info:
        resource.get_content()

    assert exc_info.value.value == 307
    assert ("Location", "https://media.example/download") in exc_info.value.add_headers


def test_file_resource_get_content_wraps_unexpected_error() -> None:
    provider = _build_resource_provider(transcode_error=RuntimeError("link unavailable"))
    resource = QuarkFileResource(
        "/movie.mkv",
        _make_environ(provider),
        _make_file_info(fid="f3", name="movie.mkv", is_dir=False, size=10),
        provider,
    )

    with pytest.raises(DAVError) as exc_info:
        resource.get_content()

    assert exc_info.value.value == 500


def test_file_resource_etag_contract() -> None:
    provider = _build_resource_provider()
    resource = QuarkFileResource(
        "/movie.mkv",
        _make_environ(provider),
        _make_file_info(fid="f4", name="movie.mkv", is_dir=False, size=10),
        provider,
    )

    assert resource.support_etag() is False
    assert resource.get_etag() is None


def test_get_webdav_app_returns_none_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    config = SimpleNamespace(
        webdav=SimpleNamespace(enabled=False, mount_path="/dav", username="admin", password="secret")
    )
    monkeypatch.setattr(service_mod, "get_config_service", lambda: SimpleNamespace(get_config=lambda: config))

    assert service_mod.get_webdav_app() is None


def test_get_webdav_app_returns_none_when_credentials_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    errors: list[str] = []
    config = SimpleNamespace(webdav=SimpleNamespace(enabled=True, mount_path="/dav", username=" ", password=""))
    monkeypatch.setattr(service_mod, "get_config_service", lambda: SimpleNamespace(get_config=lambda: config))
    monkeypatch.setattr(service_mod.logger, "error", lambda message: errors.append(message))

    assert service_mod.get_webdav_app() is None
    assert any("credentials are required" in message for message in errors)


def test_get_webdav_app_builds_wsgi_app_config(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}
    provider_obj = object()
    config = SimpleNamespace(
        webdav=SimpleNamespace(enabled=True, mount_path="/dav", username="admin", password="secret")
    )

    monkeypatch.setattr(service_mod, "get_config_service", lambda: SimpleNamespace(get_config=lambda: config))
    monkeypatch.setattr(service_mod, "QuarkDAVProvider", lambda: provider_obj)
    monkeypatch.setattr(
        service_mod,
        "WsgiDAVApp",
        lambda app_config: captured.setdefault("app", SimpleNamespace(config=app_config)),
    )

    app = service_mod.get_webdav_app()

    assert app is not None
    assert captured["app"].config["mount_path"] == "/dav"
    assert captured["app"].config["provider_mapping"] == {"/": provider_obj}
    assert captured["app"].config["simple_dc"]["user_mapping"]["*"]["admin"]["password"] == "secret"
