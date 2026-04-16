from __future__ import annotations

from typing import Any

import pytest
from fastapi import BackgroundTasks, HTTPException

from app.api import strm_validator as strm_validator_api
from app.api import transfer as transfer_api


@pytest.mark.asyncio
async def test_validate_strm_files_quick_mode_uses_default_validate_signature(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    class FakeResult:
        @staticmethod
        def to_dict() -> dict[str, Any]:
            return {"ok": True, "mode": "quick"}

    class FakeValidator:
        def __init__(
            self,
            target_directory: str,
            remote_base: str,
            video_formats: set[str],
            size_threshold_mb: int,
            cache_file: str | None,
        ) -> None:
            captured["init"] = {
                "target_directory": target_directory,
                "remote_base": remote_base,
                "video_formats": video_formats,
                "size_threshold_mb": size_threshold_mb,
                "cache_file": cache_file,
            }

        async def validate(self, scan_mode, concurrent_limit=None):
            captured["validate"] = {"scan_mode": scan_mode, "concurrent_limit": concurrent_limit}
            return FakeResult()

    monkeypatch.setattr(strm_validator_api, "StrmValidator", FakeValidator)

    payload = await strm_validator_api.validate_strm_files(
        target_directory="/tmp/media",
        remote_base="/remote",
        video_formats="mkv, mp4,AVI",
        mode="quick",
        size_threshold_mb=256,
        cache_file="/tmp/cache.json",
        concurrent_limit=99,
    )

    assert payload == {"ok": True, "mode": "quick"}
    assert captured["init"] == {
        "target_directory": "/tmp/media",
        "remote_base": "/remote",
        "video_formats": {"mkv", "mp4", "avi"},
        "size_threshold_mb": 256,
        "cache_file": "/tmp/cache.json",
    }
    assert captured["validate"] == {
        "scan_mode": strm_validator_api.ScanMode.QUICK,
        "concurrent_limit": None,
    }


@pytest.mark.asyncio
async def test_validate_strm_files_slow_mode_passes_concurrent_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    class FakeResult:
        @staticmethod
        def to_dict() -> dict[str, Any]:
            return {"ok": True, "mode": "slow"}

    class FakeValidator:
        async def validate(self, scan_mode, concurrent_limit=None):
            captured["scan_mode"] = scan_mode
            captured["concurrent_limit"] = concurrent_limit
            return FakeResult()

        def __init__(self, **kwargs: Any) -> None:
            pass

    monkeypatch.setattr(strm_validator_api, "StrmValidator", FakeValidator)

    payload = await strm_validator_api.validate_strm_files(
        target_directory="/tmp/media",
        remote_base="/remote",
        video_formats="mkv",
        mode="slow",
        concurrent_limit=7,
    )

    assert payload == {"ok": True, "mode": "slow"}
    assert captured == {
        "scan_mode": strm_validator_api.ScanMode.SLOW,
        "concurrent_limit": 7,
    }


@pytest.mark.asyncio
async def test_validate_strm_files_rejects_invalid_mode() -> None:
    with pytest.raises(HTTPException) as exc_info:
        await strm_validator_api.validate_strm_files(
            target_directory="/tmp/media",
            remote_base="/remote",
            video_formats="mkv",
            mode="invalid-mode",
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Invalid scan mode: invalid-mode"


@pytest.mark.asyncio
async def test_validate_strm_files_maps_unexpected_error_to_http_500(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class BrokenValidator:
        def __init__(self, **kwargs: Any) -> None:
            pass

        @staticmethod
        async def validate(*args: Any, **kwargs: Any) -> Any:
            raise RuntimeError("validator failed")

    monkeypatch.setattr(strm_validator_api, "StrmValidator", BrokenValidator)

    with pytest.raises(HTTPException) as exc_info:
        await strm_validator_api.validate_strm_files(
            target_directory="/tmp/media",
            remote_base="/remote",
            video_formats="mkv",
        )

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "validator failed"


@pytest.mark.asyncio
async def test_get_validation_status_returns_ready_payload() -> None:
    assert await strm_validator_api.get_validation_status() == {
        "status": "ready",
        "message": "STRM validation service is ready",
    }


@pytest.mark.asyncio
async def test_transfer_resource_success_and_auto_organize_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []

    class FakeTransferService:
        def __init__(self, db: Any) -> None:
            self.db = db

        async def transfer_share(
            self,
            drive_id: int | None,
            share_url: str,
            target_dir: str,
            password: str,
            auto_organize: bool,
            background_tasks: BackgroundTasks,
        ) -> None:
            calls.append(
                {
                    "drive_id": drive_id,
                    "share_url": share_url,
                    "target_dir": target_dir,
                    "password": password,
                    "auto_organize": auto_organize,
                    "background_tasks": background_tasks,
                }
            )

    monkeypatch.setattr(transfer_api, "TransferService", FakeTransferService)

    bg1 = BackgroundTasks()
    normal = await transfer_api.transfer_resource(
        transfer_api.TransferRequest(drive_id=1, share_url="https://share/1", target_dir="/library"),
        background_tasks=bg1,
        _auth=None,
        db=object(),
    )
    assert normal == {"message": "Transfer successful"}

    bg2 = BackgroundTasks()
    organized = await transfer_api.transfer_resource(
        transfer_api.TransferRequest(
            drive_id=2,
            share_url="https://share/2",
            target_dir="/library/organized",
            auto_organize=True,
        ),
        background_tasks=bg2,
        _auth=None,
        db=object(),
    )
    assert organized == {"message": "Transfer successful and organization started"}

    assert len(calls) == 2
    assert calls[0]["drive_id"] == 1
    assert calls[0]["auto_organize"] is False
    assert calls[1]["drive_id"] == 2
    assert calls[1]["auto_organize"] is True
    assert calls[0]["background_tasks"] is bg1
    assert calls[1]["background_tasks"] is bg2


@pytest.mark.asyncio
async def test_transfer_resource_maps_value_error_to_http_400(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class ValueErrorTransferService:
        def __init__(self, db: Any) -> None:
            pass

        @staticmethod
        async def transfer_share(*args: Any, **kwargs: Any) -> None:
            raise ValueError("invalid share url")

    monkeypatch.setattr(transfer_api, "TransferService", ValueErrorTransferService)

    with pytest.raises(HTTPException) as exc_info:
        await transfer_api.transfer_resource(
            transfer_api.TransferRequest(drive_id=1, share_url="bad-url", target_dir="/library"),
            background_tasks=BackgroundTasks(),
            _auth=None,
            db=object(),
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "invalid share url"


@pytest.mark.asyncio
async def test_transfer_resource_maps_generic_error_to_http_500(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class BrokenTransferService:
        def __init__(self, db: Any) -> None:
            pass

        @staticmethod
        async def transfer_share(*args: Any, **kwargs: Any) -> None:
            raise RuntimeError("transfer crashed")

    monkeypatch.setattr(transfer_api, "TransferService", BrokenTransferService)

    with pytest.raises(HTTPException) as exc_info:
        await transfer_api.transfer_resource(
            transfer_api.TransferRequest(drive_id=1, share_url="https://share/1", target_dir="/library"),
            background_tasks=BackgroundTasks(),
            _auth=None,
            db=object(),
        )

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "transfer crashed"
