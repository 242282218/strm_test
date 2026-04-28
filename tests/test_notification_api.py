from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.api.notification import (
    ChannelCreate,
    ChannelUpdate,
    RuleCreate,
    create_channel,
    create_rule,
    delete_channel,
    delete_rule,
    get_logs,
    list_channels,
    list_rules,
    update_channel,
)
from app.api.notification import (
    test_channel as send_test_channel,
)


def test_channel_create_accepts_supported_channel_types() -> None:
    channel = ChannelCreate(
        channel_type="serverchan",
        channel_name="ServerChan",
        config={"send_key": "SCT123"},
    )

    assert channel.channel_type == "serverchan"


def test_channel_create_rejects_unsupported_channel_types() -> None:
    with pytest.raises(ValidationError):
        ChannelCreate(
            channel_type="webhook",
            channel_name="Webhook",
            config={"webhook_url": "https://example.com"},
        )


def test_create_channel_masks_sensitive_config() -> None:
    db = MagicMock()
    db.refresh.side_effect = lambda channel: (
        setattr(channel, "id", 3),
        setattr(channel, "is_enabled", True),
    )

    response = create_channel(
        ChannelCreate(
            channel_type="telegram",
            channel_name="Telegram",
            config={"bot_token": "abcdef", "chat_id": "chat123"},
        ),
        db=db,
    )

    assert response.id == 3
    assert response.channel_type == "telegram"
    assert response.config["bot_token"] != "abcdef"
    db.add.assert_called_once()
    db.commit.assert_called_once()


def test_list_channels_masks_config_for_all_items() -> None:
    db = MagicMock()
    db.query.return_value.all.return_value = [
        SimpleNamespace(
            id=1,
            channel_type="telegram",
            channel_name="Telegram",
            is_enabled=True,
            config={"bot_token": "token-1", "chat_id": "chat"},
        ),
        SimpleNamespace(
            id=2,
            channel_type="serverchan",
            channel_name="ServerChan",
            is_enabled=False,
            config={"send_key": "SCT123"},
        ),
    ]

    channels = list_channels(db=db)

    assert len(channels) == 2
    assert channels[0].config["bot_token"] != "token-1"
    assert channels[1].config["send_key"] != "SCT123"


@pytest.mark.asyncio
async def test_update_channel_updates_fields_and_reloads_service() -> None:
    db = MagicMock()
    db_channel = SimpleNamespace(
        id=9,
        channel_type="telegram",
        channel_name="old",
        is_enabled=True,
        config={"bot_token": "old-token", "chat_id": "old-chat"},
    )
    db.query.return_value.filter.return_value.first.return_value = db_channel
    service = SimpleNamespace(reload=AsyncMock())

    response = await update_channel(
        9,
        ChannelUpdate(channel_name="new-name", is_enabled=False, config={"bot_token": "new-token", "chat_id": "new"}),
        db=db,
        service=service,
    )

    assert response.channel_name == "new-name"
    assert response.is_enabled is False
    assert response.config["bot_token"] != "new-token"
    service.reload.assert_awaited_once()
    db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_update_channel_raises_404_when_missing() -> None:
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    service = SimpleNamespace(reload=AsyncMock())

    with pytest.raises(HTTPException, match="Channel not found"):
        await update_channel(99, ChannelUpdate(channel_name="x"), db=db, service=service)


@pytest.mark.asyncio
async def test_delete_channel_and_test_channel_paths() -> None:
    db = MagicMock()
    db_channel = SimpleNamespace(id=1, channel_type="telegram", channel_name="t", config={})
    db.query.return_value.filter.return_value.first.return_value = db_channel
    send = AsyncMock(return_value=True)
    service = SimpleNamespace(
        reload=AsyncMock(),
        _create_handler=lambda _channel: SimpleNamespace(send=send),
    )

    delete_result = await delete_channel(1, db=db, service=service)
    test_result = await send_test_channel(1, db=db, service=service)

    assert delete_result == {"status": "ok"}
    assert test_result == {"status": "success"}
    service.reload.assert_awaited_once()
    send.assert_awaited_once()


@pytest.mark.asyncio
async def test_test_channel_raises_when_handler_fails() -> None:
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
        id=1,
        channel_type="telegram",
        channel_name="t",
        config={},
    )
    service = SimpleNamespace(_create_handler=lambda _channel: None)

    with pytest.raises(HTTPException, match="Failed to instantiate handler"):
        await send_test_channel(1, db=db, service=service)


@pytest.mark.asyncio
async def test_rule_crud_and_logs_query() -> None:
    db = MagicMock()
    service = SimpleNamespace(reload=AsyncMock())
    db_rule = SimpleNamespace(id=7, channel_id=1, event_type="sync_finish", keywords="k", is_enabled=True)
    db.query.return_value.filter.return_value.first.return_value = db_rule
    db.query.return_value.all.return_value = [db_rule]
    db.query.return_value.order_by.return_value.limit.return_value.all.return_value = [
        SimpleNamespace(
            id=1,
            channel_id=1,
            channel_name="chan",
            event_type="sync_finish",
            title="t",
            status="success",
            error_message=None,
            created_at=datetime.now(),
        )
    ]
    db.refresh.side_effect = lambda rule: setattr(rule, "id", 7)

    created_rule = await create_rule(
        RuleCreate(channel_id=1, event_type="sync_finish", keywords="k"),
        db=db,
        service=service,
    )
    listed_rules = list_rules(db=db)
    deleted = await delete_rule(7, db=db, service=service)
    logs = get_logs(limit=10, db=db)

    assert created_rule.id == 7
    assert listed_rules == [db_rule]
    assert deleted == {"status": "ok"}
    assert logs[0].status == "success"
    assert service.reload.await_count == 2


@pytest.mark.asyncio
async def test_delete_rule_raises_404_when_missing() -> None:
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    service = SimpleNamespace(reload=AsyncMock())

    with pytest.raises(HTTPException, match="Rule not found"):
        await delete_rule(999, db=db, service=service)
