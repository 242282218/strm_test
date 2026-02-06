from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi import BackgroundTasks, HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api import emby as emby_api
from app.api.emby import (
    EmbyDeleteExecuteRequest,
    EmbyDeletePlanRequest,
    EmbyWebhookEvent,
    create_delete_plan,
    emby_webhook,
    execute_delete_plan,
    list_emby_events,
)
from app.core.db import Base
from app.core.metrics_collector import get_metrics_collector
from app.models.emby import EmbyMediaItem


def _build_session(tmp_path: Path):
    db_file = tmp_path / "emby_events_api.db"
    engine = create_engine(
        f"sqlite:///{db_file}",
        connect_args={"check_same_thread": False},
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    return SessionLocal


@pytest.mark.asyncio
async def test_webhook_episode_aggregation_and_events_query(tmp_path: Path, monkeypatch):
    SessionLocal = _build_session(tmp_path)
    db = SessionLocal()

    class _Refresh:
        episode_aggregate_window_seconds = 10

    class _Emby:
        refresh = _Refresh()
        delete_execute_enabled = False

    class _Cfg:
        emby = _Emby()

    monkeypatch.setattr(emby_api.config_service, "get_config", lambda: _Cfg())

    try:
        payload_1 = EmbyWebhookEvent(
            Event="library.new",
            Item={
                "Id": "episode-1",
                "Type": "Episode",
                "Name": "Pilot",
                "SeriesName": "My Show",
                "SeasonNumber": 1,
            },
            Date=datetime.now(timezone.utc).isoformat(),
        )
        first = await emby_webhook(
            event=payload_1,
            background_tasks=BackgroundTasks(),
            db=db,
            collector=get_metrics_collector(),
        )
        assert first["status"] == "processed"
        assert first["aggregated"] is False
        assert first["aggregated_count"] == 1

        payload_2 = EmbyWebhookEvent(
            Event="library.new",
            Item={
                "Id": "episode-2",
                "Type": "Episode",
                "Name": "Episode 2",
                "SeriesName": "My Show",
                "SeasonNumber": 1,
            },
            Date=datetime.now(timezone.utc).isoformat(),
        )
        second = await emby_webhook(
            event=payload_2,
            background_tasks=BackgroundTasks(),
            db=db,
            collector=get_metrics_collector(),
        )
        assert second["aggregated"] is True
        assert second["aggregated_count"] == 2

        events = await list_emby_events(
            event_type="library.new",
            item_type="Episode",
            keyword="My Show",
            page=1,
            size=20,
            db=db,
        )
        assert events.total == 1
        assert len(events.items) == 1
        assert events.items[0].aggregated_count == 2
    finally:
        db.close()


@pytest.mark.asyncio
async def test_delete_plan_and_execute_feature_flag(tmp_path: Path, monkeypatch):
    SessionLocal = _build_session(tmp_path)
    db = SessionLocal()

    class _Refresh:
        episode_aggregate_window_seconds = 10

    class _EmbyDisabled:
        refresh = _Refresh()
        delete_execute_enabled = False

    class _EmbyEnabled:
        refresh = _Refresh()
        delete_execute_enabled = True

    class _CfgDisabled:
        emby = _EmbyDisabled()

    class _CfgEnabled:
        emby = _EmbyEnabled()

    try:
        media = EmbyMediaItem(
            emby_id="movie-1",
            library_id=None,
            name="Movie One",
            type="Movie",
            path="/media/movie-one.strm",
            pickcode="pickcode-1",
            is_strm=True,
            sync_status="synced",
        )
        db.add(media)
        db.commit()

        plan = await create_delete_plan(
            body=EmbyDeletePlanRequest(
                source="manual",
                item_ids=["movie-1"],
                reason="test dry-run",
            ),
            _auth=None,
            db=db,
        )
        assert plan["success"] is True
        assert plan["dry_run"] is True
        assert plan["total_items"] == 1
        assert plan["executable_items"] == 1
        plan_id = plan["plan_id"]

        monkeypatch.setattr(emby_api.config_service, "get_config", lambda: _CfgDisabled())
        with pytest.raises(HTTPException) as exc:
            await execute_delete_plan(
                body=EmbyDeleteExecuteRequest(plan_id=plan_id, executed_by="qa"),
                _auth=None,
                db=db,
                collector=get_metrics_collector(),
            )
        assert exc.value.status_code == 403

        monkeypatch.setattr(emby_api.config_service, "get_config", lambda: _CfgEnabled())
        executed = await execute_delete_plan(
            body=EmbyDeleteExecuteRequest(plan_id=plan_id, executed_by="qa"),
            _auth=None,
            db=db,
            collector=get_metrics_collector(),
        )
        assert executed["success"] is True
        assert executed["executed_items"] == 1
        assert executed["skipped_items"] == 0
        assert db.query(EmbyMediaItem).filter(EmbyMediaItem.emby_id == "movie-1").first() is None

        idempotent = await execute_delete_plan(
            body=EmbyDeleteExecuteRequest(plan_id=plan_id, executed_by="qa"),
            _auth=None,
            db=db,
            collector=get_metrics_collector(),
        )
        assert idempotent["success"] is True
        assert idempotent["idempotent"] is True
    finally:
        db.close()
