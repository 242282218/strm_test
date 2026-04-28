from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services import notification_service as ns


class FakeQuery:
    def __init__(self, all_provider, first_provider=lambda: None) -> None:
        self._all_provider = all_provider
        self._first_provider = first_provider

    def filter(self, *_args, **_kwargs) -> FakeQuery:
        return self

    def all(self):
        return self._all_provider()

    def first(self):
        return self._first_provider()


class FakeInitSession:
    def __init__(
        self,
        *,
        channels: list[SimpleNamespace],
        loaded_rules: list[SimpleNamespace],
        existing_rule_results: list[object | None],
    ) -> None:
        self._channels = channels
        self._loaded_rules = loaded_rules
        self._existing_rule_results = existing_rule_results
        self.added: list[object] = []
        self.commits = 0
        self.closed = False
        self.next_channel_id = 100

    def _next_existing_rule(self):
        if self._existing_rule_results:
            return self._existing_rule_results.pop(0)
        return None

    def query(self, model):
        if model is ns.NotificationChannel:
            return FakeQuery(lambda: self._channels)
        if model is ns.NotificationRule:
            return FakeQuery(lambda: self._loaded_rules, self._next_existing_rule)
        raise AssertionError(f"unexpected model: {model}")

    def add(self, obj) -> None:
        self.added.append(obj)

    def commit(self) -> None:
        self.commits += 1

    def refresh(self, obj) -> None:
        if getattr(obj, "id", None) is None:
            obj.id = self.next_channel_id
            self.next_channel_id += 1

    def close(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_initialize_auto_creates_telegram_channel_and_rules(monkeypatch: pytest.MonkeyPatch) -> None:
    channel = SimpleNamespace(
        id=1,
        channel_type="serverchan",
        channel_name="Main WeChat",
        config={"send_key": "SCT123"},
    )
    rules = [
        SimpleNamespace(event_type="sync_finish", channel_id=1, keywords=None),
        SimpleNamespace(event_type="sync_error", channel_id=100, keywords=None),
    ]
    db = FakeInitSession(channels=[channel], loaded_rules=rules, existing_rule_results=[None, object()])

    config = SimpleNamespace(
        telegram=SimpleNamespace(
            enabled=True,
            bot_token="bot-token",
            chat_id="chat-id",
            proxy="http://proxy.local",
            events=["sync_finish", "sync_error"],
        )
    )

    service = ns.NotificationService()
    monkeypatch.setattr(ns, "SessionLocal", lambda: db)
    monkeypatch.setattr(ns, "get_config_service", lambda: SimpleNamespace(get_config=lambda: config))
    monkeypatch.setattr(service, "_create_handler", lambda _channel: object())

    await service.initialize()

    assert service._initialized is True
    assert set(service.channels.keys()) == {1, 100}
    assert db.commits == 2
    assert db.closed is True

    added_channels = [item for item in db.added if isinstance(item, ns.NotificationChannel)]
    added_rules = [item for item in db.added if isinstance(item, ns.NotificationRule)]
    assert len(added_channels) == 1
    assert len(added_rules) == 1
    assert added_rules[0].event_type == "sync_finish"
    assert set(service.rules.keys()) == {"sync_finish", "sync_error"}


@pytest.mark.asyncio
async def test_initialize_continues_when_config_lookup_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    db = FakeInitSession(
        channels=[
            SimpleNamespace(
                id=2,
                channel_type="telegram",
                channel_name="Telegram",
                config={"bot_token": "x", "chat_id": "y"},
            )
        ],
        loaded_rules=[SimpleNamespace(event_type="task_failed", channel_id=2, keywords=None)],
        existing_rule_results=[],
    )
    warnings: list[str] = []

    def _raise_config_error():
        raise RuntimeError("config read failed")

    service = ns.NotificationService()
    monkeypatch.setattr(ns, "SessionLocal", lambda: db)
    monkeypatch.setattr(ns, "get_config_service", _raise_config_error)
    monkeypatch.setattr(service, "_create_handler", lambda _channel: None)
    monkeypatch.setattr(ns.logger, "warning", lambda message: warnings.append(message))

    await service.initialize()

    assert service._initialized is True
    assert service.channels == {}
    assert "task_failed" in service.rules
    assert any("读取 Telegram 配置失败" in message for message in warnings)
    assert db.closed is True


@pytest.mark.asyncio
async def test_initialize_logs_error_when_db_query_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    class BrokenSession:
        def __init__(self) -> None:
            self.closed = False

        def query(self, _model):
            raise RuntimeError("db unavailable")

        def close(self) -> None:
            self.closed = True

    db = BrokenSession()
    errors: list[str] = []
    service = ns.NotificationService()

    monkeypatch.setattr(ns, "SessionLocal", lambda: db)
    monkeypatch.setattr(ns.logger, "error", lambda message: errors.append(message))

    await service.initialize()

    assert service._initialized is False
    assert db.closed is True
    assert any("initialization failed" in message for message in errors)


@pytest.mark.asyncio
async def test_send_notification_filters_rules_and_deduplicates_channels() -> None:
    service = ns.NotificationService()
    service._initialized = True
    service.channels = {
        1: (object(), "channel-a"),
        2: (object(), "channel-b"),
    }
    service.rules = {
        ns.NotificationType.SYNC_FINISHED: [
            SimpleNamespace(channel_id=1, keywords="must-hit"),
            SimpleNamespace(channel_id=1, keywords=None),
            SimpleNamespace(channel_id=2, keywords="missing"),
        ]
    }
    send_and_log = AsyncMock()
    service._send_and_log = send_and_log  # type: ignore[method-assign]

    await service.send_notification(
        type=ns.NotificationType.SYNC_FINISHED,
        title="must-hit title",
        content="plain body",
    )

    send_and_log.assert_awaited_once()
    args = send_and_log.await_args.args
    assert args[0] == 1
    assert args[1] == "channel-a"
    assert isinstance(args[3], ns.NotificationMessage)
    assert args[3].title == "must-hit title"


@pytest.mark.asyncio
async def test_send_notification_initializes_and_returns_when_no_rules(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = ns.NotificationService()
    service._initialized = False
    service.rules = {}
    service.channels = {}
    initialize = AsyncMock()
    send_and_log = AsyncMock()
    debug_messages: list[str] = []

    service.initialize = initialize  # type: ignore[method-assign]
    service._send_and_log = send_and_log  # type: ignore[method-assign]
    monkeypatch.setattr(ns.logger, "debug", lambda message: debug_messages.append(message))

    await service.send_notification(ns.NotificationType.SYSTEM_ALERT, "title", "content")

    initialize.assert_awaited_once()
    send_and_log.assert_not_awaited()
    assert any("No rules found for event" in message for message in debug_messages)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("send_result", "send_exception", "expected_status", "expected_error"),
    [
        (True, None, "success", None),
        (False, None, "failed", "Handler returned False"),
        (None, TimeoutError(), "failed", "Timeout"),
        (None, RuntimeError("send failed"), "failed", "send failed"),
    ],
)
async def test_send_and_log_persists_expected_status(
    monkeypatch: pytest.MonkeyPatch,
    send_result: bool | None,
    send_exception: Exception | None,
    expected_status: str,
    expected_error: str | None,
) -> None:
    db = MagicMock()
    service = ns.NotificationService()

    send = AsyncMock(return_value=send_result)
    if send_exception is not None:
        send.side_effect = send_exception
    handler = SimpleNamespace(send=send)
    message = ns.NotificationMessage(ns.NotificationType.SYNC_FINISHED, "title", "body")

    monkeypatch.setattr(ns, "SessionLocal", lambda: db)

    await service._send_and_log(9, "chan", handler, message)

    log_record = db.add.call_args.args[0]
    assert isinstance(log_record, ns.NotificationLog)
    assert log_record.channel_id == 9
    assert log_record.channel_name == "chan"
    assert log_record.status == expected_status
    assert log_record.error_message == expected_error
    db.commit.assert_called_once()
    db.close.assert_called_once()


@pytest.mark.asyncio
async def test_send_and_log_catches_log_persistence_error(monkeypatch: pytest.MonkeyPatch) -> None:
    errors: list[str] = []
    service = ns.NotificationService()
    handler = SimpleNamespace(send=AsyncMock(return_value=True))
    message = ns.NotificationMessage(ns.NotificationType.SYSTEM_ALERT, "alert", "body")

    def _raise_db_error():
        raise RuntimeError("db write failed")

    monkeypatch.setattr(ns, "SessionLocal", _raise_db_error)
    monkeypatch.setattr(ns.logger, "error", lambda message: errors.append(message))

    await service._send_and_log(1, "broken", handler, message)

    assert any("Failed to save notification log" in message for message in errors)


@pytest.mark.asyncio
async def test_channel_handler_adapter_delegates_to_notifier() -> None:
    captured = {}

    class FakeNotifier:
        name = "fake-notifier"

        async def send(self, message) -> bool:
            captured["message"] = message
            return True

        async def is_healthy(self) -> bool:
            return False

        def validate_config(self) -> bool:
            return True

    adapter = ns.ChannelHandlerAdapter(FakeNotifier(), "channel")
    old_message = ns.NotificationMessage(ns.NotificationType.SYSTEM_ALERT, "hello", "world")

    assert await adapter.send(old_message) is True
    assert captured["message"].title == "hello"
    assert adapter.get_channel_type() == "fake-notifier"
    assert await adapter.is_healthy() is False
    assert adapter.validate_config() is True


@pytest.mark.asyncio
async def test_channel_handlers_wrap_underlying_notifiers(monkeypatch: pytest.MonkeyPatch) -> None:
    created = {}

    class FakeTelegramNotifier:
        def __init__(self, token: str, chat_id: str, proxy_url: str | None = None) -> None:
            created["telegram"] = {"token": token, "chat_id": chat_id, "proxy_url": proxy_url}

        async def send(self, message) -> bool:
            created["telegram_message"] = message
            return True

        async def is_healthy(self) -> bool:
            return True

    class FakeWeChatNotifier:
        def __init__(self, send_key: str) -> None:
            created["serverchan"] = send_key

        async def send(self, message) -> bool:
            created["serverchan_message"] = message
            return False

    monkeypatch.setattr(ns, "TelegramNotifier", FakeTelegramNotifier)
    monkeypatch.setattr(ns, "WeChatNotifier", FakeWeChatNotifier)

    telegram = ns.TelegramHandler(bot_token="token", chat_id="chat", proxy="http://proxy")
    message = ns.NotificationMessage(ns.NotificationType.SYNC_FINISHED, "title", "content")

    assert await telegram.send(message) is True
    assert telegram.get_channel_type() == "telegram"
    assert await telegram.is_healthy() is True
    assert created["telegram"]["proxy_url"] == "http://proxy"
    assert ns.TelegramHandler.validate_config({"bot_token": "t", "chat_id": "c"}) is True
    assert ns.TelegramHandler.validate_config({"bot_token": "t"}) is False

    serverchan = ns.ServerChanHandler(send_key="SCT123")
    assert await serverchan.send(message) is False
    assert serverchan.get_channel_type() == "serverchan"
    assert await serverchan.is_healthy() is True
    assert created["serverchan"] == "SCT123"
    assert ns.ServerChanHandler.validate_config({"send_key": "x"}) is True
    assert ns.ServerChanHandler.validate_config({}) is False


def test_notification_service_singleton_accessor() -> None:
    ns.NotificationService._instance = None

    first = ns.NotificationService.get_instance()
    second = ns.get_notification_service()

    assert first is second


@pytest.mark.asyncio
async def test_reload_clears_cache_and_reinitializes() -> None:
    service = ns.NotificationService()
    service.channels = {1: (object(), "name")}
    service.rules = {"sync_finish": [SimpleNamespace(channel_id=1, keywords=None)]}
    service._initialized = True
    initialize = AsyncMock()
    service.initialize = initialize  # type: ignore[method-assign]

    await service.reload()

    assert service.channels == {}
    assert service.rules == {}
    assert service._initialized is False
    initialize.assert_awaited_once()


@pytest.mark.asyncio
async def test_initialize_returns_early_when_already_initialized(monkeypatch: pytest.MonkeyPatch) -> None:
    service = ns.NotificationService()
    service._initialized = True
    called = {"count": 0}

    def _session_local():
        called["count"] += 1
        raise AssertionError("SessionLocal should not be called")

    monkeypatch.setattr(ns, "SessionLocal", _session_local)

    await service.initialize()

    assert called["count"] == 0


@pytest.mark.asyncio
async def test_initialize_skips_telegram_auto_create_when_channel_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = FakeInitSession(
        channels=[
            SimpleNamespace(
                id=7,
                channel_type="telegram",
                channel_name="Telegram Existing",
                config={"bot_token": "x", "chat_id": "y"},
            )
        ],
        loaded_rules=[],
        existing_rule_results=[],
    )
    config = SimpleNamespace(
        telegram=SimpleNamespace(
            enabled=True,
            bot_token="token",
            chat_id="chat",
            proxy=None,
            events=["sync_finish"],
        )
    )
    service = ns.NotificationService()

    monkeypatch.setattr(ns, "SessionLocal", lambda: db)
    monkeypatch.setattr(ns, "get_config_service", lambda: SimpleNamespace(get_config=lambda: config))
    monkeypatch.setattr(service, "_create_handler", lambda _channel: object())

    await service.initialize()

    assert set(service.channels.keys()) == {7}
    assert db.commits == 0
    assert all(not isinstance(item, ns.NotificationChannel) for item in db.added)


@pytest.mark.asyncio
async def test_initialize_auto_create_skips_channel_registration_when_handler_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = FakeInitSession(
        channels=[],
        loaded_rules=[SimpleNamespace(event_type="sync_finish", channel_id=100, keywords=None)],
        existing_rule_results=[None],
    )
    config = SimpleNamespace(
        telegram=SimpleNamespace(
            enabled=True,
            bot_token="token",
            chat_id="chat",
            proxy=None,
            events=["sync_finish"],
        )
    )
    service = ns.NotificationService()

    monkeypatch.setattr(ns, "SessionLocal", lambda: db)
    monkeypatch.setattr(ns, "get_config_service", lambda: SimpleNamespace(get_config=lambda: config))
    monkeypatch.setattr(service, "_create_handler", lambda _channel: None)

    await service.initialize()

    assert service._initialized is True
    assert service.channels == {}
    assert db.commits == 2
    assert any(isinstance(item, ns.NotificationChannel) for item in db.added)


def test_create_handler_returns_none_for_unknown_or_constructor_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = ns.NotificationService()
    unknown_channel = SimpleNamespace(channel_type="unknown", channel_name="unknown", config={})

    assert service._create_handler(unknown_channel) is None

    class BrokenHandler:
        def __init__(self, **_kwargs) -> None:
            raise RuntimeError("broken init")

    errors: list[str] = []
    monkeypatch.setattr(ns.NotificationService, "_handlers_cls", {"broken": BrokenHandler})
    monkeypatch.setattr(ns.logger, "error", lambda message: errors.append(message))

    broken_channel = SimpleNamespace(channel_type="broken", channel_name="broken", config={"k": "v"})

    assert service._create_handler(broken_channel) is None
    assert any("创建渠道处理程序失败" in message for message in errors)


@pytest.mark.asyncio
async def test_send_notification_ignores_rules_for_missing_channels() -> None:
    service = ns.NotificationService()
    service._initialized = True
    service.rules = {
        ns.NotificationType.SYSTEM_ALERT: [SimpleNamespace(channel_id=999, keywords=None)],
    }
    service.channels = {}
    send_and_log = AsyncMock()
    service._send_and_log = send_and_log  # type: ignore[method-assign]

    await service.send_notification(ns.NotificationType.SYSTEM_ALERT, "alert", "content")

    send_and_log.assert_not_awaited()


@pytest.mark.asyncio
async def test_notification_shortcuts_forward_to_send_notification() -> None:
    service = ns.NotificationService()
    send = AsyncMock()
    service.send_notification = send  # type: ignore[method-assign]

    await service.notify_sync_finished("job", {"new": 1, "updated": 2})
    await service.notify_sync_error("job", "boom")
    await service.notify_media_added("Movie", "film")
    await service.notify_media_removed("Movie")

    assert send.await_count == 4
    first_kwargs = send.await_args_list[0].kwargs
    assert first_kwargs["type"] == ns.NotificationType.SYNC_FINISHED
    assert first_kwargs["metadata"] == {"new": 1, "updated": 2}
