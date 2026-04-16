import pytest

from app.services import webdav_fallback as webdav_fallback_mod


class FakeConfigManager:
    def __init__(self, config: dict):
        self._config = config

    def get_webdav_config(self) -> dict:
        return self._config


def build_service(monkeypatch, config: dict) -> webdav_fallback_mod.WebDAVFallback:
    monkeypatch.setattr(
        webdav_fallback_mod,
        "get_config",
        lambda: FakeConfigManager(config),
    )
    return webdav_fallback_mod.WebDAVFallback()


def test_get_fallback_url_returns_none_when_disabled(monkeypatch):
    disabled = build_service(
        monkeypatch,
        {"enabled": False, "fallback_enabled": True},
    )
    assert disabled.get_fallback_url("Movies/Avatar.mp4") is None

    fallback_disabled = build_service(
        monkeypatch,
        {"enabled": True, "fallback_enabled": False},
    )
    assert fallback_disabled.get_fallback_url("Movies/Avatar.mp4") is None


@pytest.mark.parametrize(
    ("base_url", "mount_path", "path", "expected"),
    [
        ("http://example.com/dav", "/", "Movies/A.mp4", "http://example.com/dav/Movies/A.mp4"),
        ("http://example.com", "/dav", "Movies/A.mp4", "http://example.com/dav/Movies/A.mp4"),
        ("http://example.com/dav", "/dav", "Movies/A.mp4", "http://example.com/dav/Movies/A.mp4"),
        ("http://example.com/dav", "/dav/media", "Movies/A.mp4", "http://example.com/dav/media/Movies/A.mp4"),
        ("http://example.com/dav/media", "/dav", "Movies/A.mp4", "http://example.com/dav/media/Movies/A.mp4"),
        ("http://example.com/root", "/dav", "Movies/A.mp4", "http://example.com/root/dav/Movies/A.mp4"),
    ],
)
def test_get_fallback_url_resolves_prefix_matrix(monkeypatch, base_url, mount_path, path, expected):
    service = build_service(
        monkeypatch,
        {
            "enabled": True,
            "fallback_enabled": True,
            "url": base_url,
            "mount_path": mount_path,
        },
    )
    assert service.get_fallback_url(path) == expected


def test_get_fallback_url_encodes_credentials_and_path(monkeypatch):
    service = build_service(
        monkeypatch,
        {
            "enabled": True,
            "fallback_enabled": True,
            "url": "http://example.com/dav",
            "mount_path": "/",
            "username": "user name",
            "password": "p@ss",
        },
    )

    url = service.get_fallback_url("/Movies/A B.mp4")
    assert url == "http://user%20name:p%40ss@example.com/dav/Movies/A%20B.mp4"


def test_get_fallback_url_keeps_existing_netloc_and_default_base(monkeypatch):
    service_with_netloc = build_service(
        monkeypatch,
        {
            "enabled": True,
            "fallback_enabled": True,
            "url": "http://existing@host",
            "mount_path": "/",
            "username": "admin",
            "password": "secret",
        },
    )
    assert service_with_netloc.get_fallback_url("") == "http://existing@host/"

    service_default_base = build_service(
        monkeypatch,
        {"enabled": True, "fallback_enabled": True, "mount_path": "/"},
    )
    assert service_default_base.get_fallback_url("demo.mp4") == "http://localhost:5244/dav/demo.mp4"
