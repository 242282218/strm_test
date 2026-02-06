import types

import pytest

from app.services import transfer_service as transfer_module
from app.services.transfer_service import TransferService


class _DummyConfigService:
    def get_config(self):
        return types.SimpleNamespace(quark=types.SimpleNamespace(cookie="fake-cookie"))


class _FakeClient:
    def __init__(self):
        self.saved = None

    async def get_share_token(self, pwd_id, password):
        return "fake_stoken"

    async def get_share_files(self, pwd_id, stoken):
        return [{"fid": "f1"}]

    async def save_share(self, pwd_id, stoken, fid_list, target_fid):
        self.saved = (pwd_id, stoken, fid_list, target_fid)


@pytest.mark.asyncio
async def test_transfer_share_retries_target_dir_lookup(monkeypatch):
    instances = []
    sleep_calls = []

    class FakeQuarkService:
        def __init__(self, cookie):
            self.cookie = cookie
            self.client = _FakeClient()
            self.lookup_calls = 0
            instances.append(self)

        async def get_file_by_path(self, target_dir):
            self.lookup_calls += 1
            if self.lookup_calls < 3:
                return None
            return types.SimpleNamespace(fid="target_fid", is_dir=True)

        async def close(self):
            return None

    async def fake_sleep(seconds):
        sleep_calls.append(seconds)

    monkeypatch.setattr(transfer_module, "QuarkService", FakeQuarkService)
    monkeypatch.setattr(transfer_module, "get_config_service", lambda: _DummyConfigService())
    monkeypatch.setattr(transfer_module.asyncio, "sleep", fake_sleep)

    service = TransferService(db_session=None)
    await service.transfer_share(
        drive_id=None,
        share_url="https://pan.quark.cn/s/abcdef123456",
        target_dir="/target",
    )

    assert len(instances) == 1
    instance = instances[0]
    assert instance.lookup_calls == 3
    assert sleep_calls == [0.5, 0.5]
    assert instance.client.saved[3] == "target_fid"


@pytest.mark.asyncio
async def test_transfer_share_raises_when_target_dir_missing(monkeypatch):
    instances = []

    class FakeQuarkService:
        def __init__(self, cookie):
            self.cookie = cookie
            self.client = _FakeClient()
            self.lookup_calls = 0
            instances.append(self)

        async def get_file_by_path(self, target_dir):
            self.lookup_calls += 1
            return None

        async def close(self):
            return None

    async def fake_sleep(_seconds):
        return None

    monkeypatch.setattr(transfer_module, "QuarkService", FakeQuarkService)
    monkeypatch.setattr(transfer_module, "get_config_service", lambda: _DummyConfigService())
    monkeypatch.setattr(transfer_module.asyncio, "sleep", fake_sleep)

    service = TransferService(db_session=None)
    with pytest.raises(ValueError, match="Target directory /target not found"):
        await service.transfer_share(
            drive_id=None,
            share_url="https://pan.quark.cn/s/abcdef123456",
            target_dir="/target",
        )

    assert len(instances) == 1
    assert instances[0].lookup_calls == 6
