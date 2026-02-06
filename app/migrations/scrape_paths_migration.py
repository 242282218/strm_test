from __future__ import annotations

from sqlalchemy import Engine, text


UP_SQL = [
    """
    CREATE TABLE IF NOT EXISTS scrape_paths (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        path_id VARCHAR(50) NOT NULL UNIQUE,
        source_path VARCHAR(500) NOT NULL,
        dest_path VARCHAR(500) NOT NULL,
        media_type VARCHAR(20) NOT NULL DEFAULT 'auto',
        scrape_mode VARCHAR(30) NOT NULL DEFAULT 'scrape_and_rename',
        rename_mode VARCHAR(20) NOT NULL DEFAULT 'move',
        max_threads INTEGER NOT NULL DEFAULT 1,
        cron VARCHAR(120),
        enabled BOOLEAN NOT NULL DEFAULT 1,
        cron_enabled BOOLEAN NOT NULL DEFAULT 0,
        enable_secondary_category BOOLEAN NOT NULL DEFAULT 1,
        status VARCHAR(20) NOT NULL DEFAULT 'idle',
        last_job_id VARCHAR(50),
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_scrape_paths_source_path ON scrape_paths(source_path)",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_scrape_paths_path_id ON scrape_paths(path_id)",
]


DOWN_SQL = [
    "DROP TABLE IF EXISTS scrape_paths",
]


def apply_scrape_paths_migration(engine: Engine) -> None:
    with engine.begin() as conn:
        for statement in UP_SQL:
            conn.execute(text(statement))


def rollback_scrape_paths_migration(engine: Engine) -> None:
    with engine.begin() as conn:
        for statement in DOWN_SQL:
            conn.execute(text(statement))

