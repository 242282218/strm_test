from __future__ import annotations

from sqlalchemy import Engine, text


UP_SQL = [
    """
    CREATE TABLE IF NOT EXISTS emby_event_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id VARCHAR(50) NOT NULL UNIQUE,
        event_type VARCHAR(50) NOT NULL,
        item_id VARCHAR(100),
        item_name VARCHAR(300),
        item_type VARCHAR(50),
        aggregated_count INTEGER NOT NULL DEFAULT 1,
        payload JSON,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_emby_event_logs_event_type ON emby_event_logs(event_type)",
    "CREATE INDEX IF NOT EXISTS idx_emby_event_logs_item_type ON emby_event_logs(item_type)",
    "CREATE INDEX IF NOT EXISTS idx_emby_event_logs_item_id ON emby_event_logs(item_id)",
    """
    CREATE TABLE IF NOT EXISTS emby_delete_plans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        plan_id VARCHAR(50) NOT NULL UNIQUE,
        source VARCHAR(50) NOT NULL DEFAULT 'manual',
        dry_run BOOLEAN NOT NULL DEFAULT 1,
        executed BOOLEAN NOT NULL DEFAULT 0,
        status VARCHAR(30) NOT NULL DEFAULT 'planned',
        request_payload JSON,
        plan_items JSON,
        executed_by VARCHAR(100),
        executed_at DATETIME,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_emby_delete_plans_status ON emby_delete_plans(status)",
]


DOWN_SQL = [
    "DROP TABLE IF EXISTS emby_event_logs",
    "DROP TABLE IF EXISTS emby_delete_plans",
]


def apply_emby_event_logs_migration(engine: Engine) -> None:
    with engine.begin() as conn:
        for statement in UP_SQL:
            conn.execute(text(statement))


def rollback_emby_event_logs_migration(engine: Engine) -> None:
    with engine.begin() as conn:
        for statement in DOWN_SQL:
            conn.execute(text(statement))

