from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Connection
from sqlalchemy.pool import NullPool

from app.migrations.runner import (
    CURRENT_SCHEMA_VERSION,
    Migration,
    MigrationError,
    get_schema_version,
    run_migrations,
)


def _engine(path: Path):
    return create_engine(
        f"sqlite:///{path.as_posix()}",
        connect_args={"check_same_thread": False},
        poolclass=NullPool,
    )


def test_empty_database_migrates_to_current_schema_version(tmp_path: Path) -> None:
    engine = _engine(tmp_path / "empty.db")
    try:
        result = run_migrations(engine)

        assert result.previous_version == 0
        assert result.current_version == CURRENT_SCHEMA_VERSION
        assert result.target_version == CURRENT_SCHEMA_VERSION
        assert result.applied_versions == tuple(range(1, CURRENT_SCHEMA_VERSION + 1))

        with engine.connect() as connection:
            assert get_schema_version(connection) == CURRENT_SCHEMA_VERSION

        tables = set(inspect(engine).get_table_names())
        assert {"users", "strm_records", "scan_records", "tasks"}.issubset(tables)
    finally:
        engine.dispose()


def test_migrations_are_idempotent_and_preserve_existing_data(tmp_path: Path) -> None:
    engine = _engine(tmp_path / "idempotent.db")
    try:
        run_migrations(engine)
        with engine.begin() as connection:
            connection.execute(
                text("INSERT INTO scan_records (remote_dir, last_scan) VALUES ('/movies', '2026-04-27 00:00:00')")
            )

        result = run_migrations(engine)

        assert result.applied_versions == ()
        with engine.connect() as connection:
            row = connection.execute(text("SELECT remote_dir FROM scan_records")).fetchone()
            assert row is not None
            assert row[0] == "/movies"
            assert get_schema_version(connection) == CURRENT_SCHEMA_VERSION
    finally:
        engine.dispose()


def test_version_two_adds_task_runtime_columns_to_existing_schema(tmp_path: Path) -> None:
    engine = _engine(tmp_path / "task-runtime.db")
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql(
                """
                CREATE TABLE tasks (
                    id INTEGER PRIMARY KEY,
                    task_type VARCHAR NOT NULL,
                    status VARCHAR,
                    priority VARCHAR,
                    progress INTEGER,
                    total_items INTEGER,
                    processed_items INTEGER,
                    error_message TEXT,
                    logs JSON,
                    params JSON,
                    created_at DATETIME,
                    started_at DATETIME,
                    completed_at DATETIME
                )
                """
            )
            connection.exec_driver_sql("PRAGMA user_version = 1")

        result = run_migrations(engine)

        assert result.previous_version == 1
        assert result.current_version == CURRENT_SCHEMA_VERSION
        assert result.applied_versions == (2,)
        task_columns = {column["name"] for column in inspect(engine).get_columns("tasks")}
        assert {
            "lease_owner",
            "lease_until",
            "heartbeat_at",
            "attempt",
            "max_attempts",
            "idempotency_key",
            "resume_cursor",
            "next_run_at",
        }.issubset(task_columns)
    finally:
        engine.dispose()


def test_old_version_applies_pending_migrations_in_order(tmp_path: Path) -> None:
    engine = _engine(tmp_path / "ordered.db")

    def first(connection: Connection) -> None:
        connection.execute(text("CREATE TABLE migration_order (value INTEGER NOT NULL)"))
        connection.execute(text("INSERT INTO migration_order (value) VALUES (1)"))

    def second(connection: Connection) -> None:
        connection.execute(text("INSERT INTO migration_order (value) VALUES (2)"))

    try:
        result = run_migrations(
            engine,
            migrations=(
                Migration(version=1, name="first", apply=first),
                Migration(version=2, name="second", apply=second),
            ),
        )

        assert result.previous_version == 0
        assert result.current_version == 2
        assert result.applied_versions == (1, 2)
        with engine.connect() as connection:
            values = [row[0] for row in connection.execute(text("SELECT value FROM migration_order ORDER BY value"))]
            assert values == [1, 2]
    finally:
        engine.dispose()


def test_failed_migration_does_not_advance_schema_version(tmp_path: Path) -> None:
    engine = _engine(tmp_path / "failed.db")

    def ok(connection: Connection) -> None:
        connection.execute(text("CREATE TABLE kept_table (id INTEGER PRIMARY KEY)"))

    def fail(connection: Connection) -> None:
        connection.execute(text("CREATE TABLE failed_table (id INTEGER PRIMARY KEY)"))
        raise RuntimeError("boom")

    try:
        with pytest.raises(MigrationError, match="apply migration 2 fail"):
            run_migrations(
                engine,
                migrations=(
                    Migration(version=1, name="ok", apply=ok),
                    Migration(version=2, name="fail", apply=fail),
                ),
            )

        with engine.connect() as connection:
            assert get_schema_version(connection) == 1

        tables = set(inspect(engine).get_table_names())
        assert "kept_table" in tables
    finally:
        engine.dispose()


def test_newer_database_version_is_rejected(tmp_path: Path) -> None:
    engine = _engine(tmp_path / "newer.db")
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql("PRAGMA user_version = 999")

        with pytest.raises(MigrationError, match="newer than supported"):
            run_migrations(engine)
    finally:
        engine.dispose()
