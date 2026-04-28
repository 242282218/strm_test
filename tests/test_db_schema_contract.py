from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, inspect
from sqlalchemy.pool import NullPool

from app.migrations.runner import CURRENT_SCHEMA_VERSION, MODEL_MODULES, get_schema_version, run_migrations


def _engine(path: Path):
    return create_engine(
        f"sqlite:///{path.as_posix()}",
        connect_args={"check_same_thread": False},
        poolclass=NullPool,
    )


def test_schema_baseline_contains_key_runtime_tables(tmp_path: Path) -> None:
    engine = _engine(tmp_path / "schema.db")
    try:
        run_migrations(engine)
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())

        expected_tables = {
            "users",
            "login_attempts",
            "strm_records",
            "scan_records",
            "media_mappings",
            "scrape_paths",
            "scrape_records",
            "tasks",
            "emby_event_logs",
            "emby_delete_plans",
            "security_events",
            "ip_access_records",
            "notification_channels",
            "cloud_drives",
        }
        assert expected_tables.issubset(tables)

        with engine.connect() as connection:
            assert get_schema_version(connection) == CURRENT_SCHEMA_VERSION
    finally:
        engine.dispose()


def test_schema_baseline_keeps_key_columns_and_indexes(tmp_path: Path) -> None:
    engine = _engine(tmp_path / "indexes.db")
    try:
        run_migrations(engine)
        inspector = inspect(engine)

        users_columns = {column["name"] for column in inspector.get_columns("users")}
        assert {"username", "password_hash", "role", "is_active"}.issubset(users_columns)

        strm_columns = {column["name"] for column in inspector.get_columns("strm_records")}
        assert {"file_id", "file_name", "remote_dir", "raw_url"}.issubset(strm_columns)

        strm_indexes = {index["name"] for index in inspector.get_indexes("strm_records")}
        assert "idx_strm_records_file_id" in strm_indexes
        assert "idx_strm_records_remote_dir" in strm_indexes

        task_columns = {column["name"] for column in inspector.get_columns("tasks")}
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

        scan_unique_constraints = {
            tuple(constraint["column_names"]) for constraint in inspector.get_unique_constraints("scan_records")
        }
        assert ("remote_dir",) in scan_unique_constraints
    finally:
        engine.dispose()


def test_migration_runner_imports_model_metadata_without_router_side_effects() -> None:
    assert "app.models.cloud_drive" in MODEL_MODULES
    assert "app.models.emby" in MODEL_MODULES
    assert "app.models.scrape" in MODEL_MODULES
    assert "app.models.user" in MODEL_MODULES
    assert all(not module_name.startswith("app.api.") for module_name in MODEL_MODULES)
