import pytest

from app.services.storage import quark as quark_storage


def test_quark_storage_provider_uses_runtime_cookie(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, str] = {}

    class _FakeQuarkService:
        def __init__(self, cookie: str):
            captured["cookie"] = cookie

    monkeypatch.setattr(quark_storage, "get_quark_cookie", lambda: "runtime-cookie")
    monkeypatch.setattr(quark_storage, "QuarkService", _FakeQuarkService)

    provider = quark_storage.QuarkStorageProvider()

    assert captured == {"cookie": "runtime-cookie"}
    assert isinstance(provider.service, _FakeQuarkService)


def test_quark_storage_provider_keeps_explicit_service(monkeypatch: pytest.MonkeyPatch) -> None:
    explicit_service = object()

    monkeypatch.setattr(
        quark_storage,
        "get_quark_cookie",
        lambda: (_ for _ in ()).throw(AssertionError("runtime cookie helper should not be used")),
    )

    provider = quark_storage.QuarkStorageProvider(service=explicit_service)

    assert provider.service is explicit_service
