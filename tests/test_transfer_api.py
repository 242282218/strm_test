"""
Transfer API route tests.
"""

from fastapi.testclient import TestClient

from app.main import app
from app.api import transfer as transfer_api


client = TestClient(app)


def test_transfer_accepts_missing_drive_id(monkeypatch):
    captured = {}

    async def fake_transfer_share(
        self,
        drive_id,
        share_url,
        target_dir,
        password="",
        auto_organize=False,
        background_tasks=None,
    ):
        captured["drive_id"] = drive_id
        captured["share_url"] = share_url
        captured["target_dir"] = target_dir

    monkeypatch.setattr(transfer_api.TransferService, "transfer_share", fake_transfer_share)

    response = client.post(
        "/api/transfer",
        json={
            "share_url": "https://pan.quark.cn/s/abcdef123456",
            "target_dir": "/",
            "password": "",
            "auto_organize": False,
        },
    )

    assert response.status_code == 200
    assert captured["drive_id"] is None
    assert captured["share_url"] == "https://pan.quark.cn/s/abcdef123456"
    assert captured["target_dir"] == "/"


def test_transfer_keeps_drive_id_when_provided(monkeypatch):
    captured = {}

    async def fake_transfer_share(
        self,
        drive_id,
        share_url,
        target_dir,
        password="",
        auto_organize=False,
        background_tasks=None,
    ):
        captured["drive_id"] = drive_id

    monkeypatch.setattr(transfer_api.TransferService, "transfer_share", fake_transfer_share)

    response = client.post(
        "/api/transfer",
        json={
            "drive_id": 7,
            "share_url": "https://pan.quark.cn/s/abcdef123456",
            "target_dir": "/",
        },
    )

    assert response.status_code == 200
    assert captured["drive_id"] == 7
