from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, inspect

from app.migrations.emby_event_logs_migration import (
    apply_emby_event_logs_migration,
    rollback_emby_event_logs_migration,
)


def test_emby_event_logs_and_delete_plans_migration_roundtrip(tmp_path: Path):
    db_file = tmp_path / "emby_migration.db"
    engine = create_engine(
        f"sqlite:///{db_file}",
        connect_args={"check_same_thread": False},
    )

    apply_emby_event_logs_migration(engine)
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    assert "emby_event_logs" in tables
    assert "emby_delete_plans" in tables

    rollback_emby_event_logs_migration(engine)
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    assert "emby_event_logs" not in tables
    assert "emby_delete_plans" not in tables
