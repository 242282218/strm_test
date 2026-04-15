from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from app.services import token_monitor


class FakeConfig:
    def __init__(self, cookie: str | None) -> None:
        self._cookie = cookie

    def get_quark_cookie(self) -> str | None:
        return self._cookie


class FakeNotifier:
    def __init__(self) -> None:
        self.send_notification = AsyncMock()


class FakeQuarkService:
    def __init__(self, cookie: str, should_fail: bool = False) -> None:
        self.cookie = cookie
        self.should_fail = should_fail
        self.list_files_calls: list[tuple[str, int, int]] = []
        self.closed = False

    async def list_files(self, pdir_fid: str, page: int, size: int) -> None:
        self.list_files_calls.append((pdir_fid, page, size))
        if self.should_fail:
            raise RuntimeError("list failed")

    async def close(self) -> None:
        self.closed = True


def _build_monitor_with_cookie(
    monkeypatch: pytest.MonkeyPatch, cookie: str | None, notifier: FakeNotifier
) -> token_monitor.TokenMonitor:
    monkeypatch.setattr(token_monitor, "get_config", lambda: FakeConfig(cookie))
    monkeypatch.setattr(token_monitor, "get_notification_service", lambda: notifier)
    return token_monitor.TokenMonitor()


@pytest.mark.asyncio
async def test_check_token_returns_false_when_cookie_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    notifier = FakeNotifier()
    monitor = _build_monitor_with_cookie(monkeypatch, cookie=None, notifier=notifier)

    warnings: list[str] = []
    monkeypatch.setattr(token_monitor.logger, "warning", lambda message: warnings.append(message))

    result = await monitor.check_token()

    assert result is False
    assert warnings == ["TokenMonitor: No cookie configured"]
    notifier.send_notification.assert_not_awaited()


@pytest.mark.asyncio
async def test_check_token_returns_true_when_quark_cookie_valid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    notifier = FakeNotifier()
    monitor = _build_monitor_with_cookie(monkeypatch, cookie="cookie-value", notifier=notifier)
    service = FakeQuarkService(cookie="cookie-value")

    monkeypatch.setattr(token_monitor, "QuarkService", lambda cookie: service)

    result = await monitor.check_token()

    assert result is True
    assert service.list_files_calls == [("0", 1, 1)]
    assert service.closed is True
    notifier.send_notification.assert_not_awaited()


@pytest.mark.asyncio
async def test_check_token_sends_notification_when_quark_check_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    notifier = FakeNotifier()
    monitor = _build_monitor_with_cookie(monkeypatch, cookie="cookie-value", notifier=notifier)
    service = FakeQuarkService(cookie="cookie-value", should_fail=True)

    monkeypatch.setattr(token_monitor, "QuarkService", lambda cookie: service)

    result = await monitor.check_token()

    assert result is False
    assert service.closed is True
    notifier.send_notification.assert_awaited_once()
    kwargs = notifier.send_notification.await_args.kwargs
    assert kwargs["type"] == token_monitor.NotificationType.SYSTEM_ALERT
    assert kwargs["priority"] == token_monitor.NotificationPriority.HIGH
    assert "夸克 Token 失效" in kwargs["title"]
    assert "Cookie 可能已失效" in kwargs["content"]


@pytest.mark.asyncio
async def test_check_token_logs_notification_error_without_raising(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    notifier = FakeNotifier()
    notifier.send_notification.side_effect = RuntimeError("notify failed")
    monitor = _build_monitor_with_cookie(monkeypatch, cookie="cookie-value", notifier=notifier)
    service = FakeQuarkService(cookie="cookie-value", should_fail=True)
    errors: list[str] = []

    monkeypatch.setattr(token_monitor, "QuarkService", lambda cookie: service)
    monkeypatch.setattr(token_monitor.logger, "error", lambda message: errors.append(message))

    result = await monitor.check_token()

    assert result is False
    assert any("Failed to send token expiration notification" in message for message in errors)


@pytest.mark.asyncio
async def test_start_monitor_loop_runs_once_then_stops(monkeypatch: pytest.MonkeyPatch) -> None:
    notifier = FakeNotifier()
    monitor = _build_monitor_with_cookie(monkeypatch, cookie="cookie-value", notifier=notifier)

    check_calls = {"count": 0}

    async def fake_check_token() -> bool:
        check_calls["count"] += 1
        return True

    async def fake_sleep(_seconds: int) -> None:
        raise RuntimeError("stop-loop")

    monkeypatch.setattr(monitor, "check_token", fake_check_token)
    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    with pytest.raises(RuntimeError, match="stop-loop"):
        await monitor.start_monitor_loop(interval_seconds=10)

    assert check_calls["count"] == 1
