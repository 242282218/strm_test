from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, text

from app.migrations.scrape_paths_migration import (
    apply_scrape_paths_migration,
    rollback_scrape_paths_migration,
)


def _table_exists(engine, table_name: str) -> bool:
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=:name"
            ),
            {"name": table_name},
        ).fetchall()
    return len(rows) > 0


def test_scrape_paths_migration_up_and_down(tmp_path: Path):
    db_path = tmp_path / "migration.db"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )

    assert _table_exists(engine, "scrape_paths") is False

    apply_scrape_paths_migration(engine)
    assert _table_exists(engine, "scrape_paths") is True

    rollback_scrape_paths_migration(engine)
    assert _table_exists(engine, "scrape_paths") is False

