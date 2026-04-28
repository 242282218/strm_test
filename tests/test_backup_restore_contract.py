from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from app.migrations.backup import (
    BackupError,
    create_sqlite_backup,
    restore_sqlite_backup,
    validate_sqlite_backup,
)
from app.migrations.runner import CURRENT_SCHEMA_VERSION


def _create_source_database(path: Path) -> None:
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute(f"PRAGMA user_version = {CURRENT_SCHEMA_VERSION}")
        connection.execute("CREATE TABLE sample_data (id INTEGER PRIMARY KEY, value TEXT NOT NULL)")
        connection.execute("INSERT INTO sample_data (value) VALUES ('kept')")
        connection.commit()


def _read_value(path: Path) -> str:
    with closing(sqlite3.connect(path)) as connection:
        row = connection.execute("SELECT value FROM sample_data WHERE id = 1").fetchone()
    assert row is not None
    return str(row[0])


def test_online_backup_captures_wal_committed_data(tmp_path: Path) -> None:
    source = tmp_path / "source.db"
    _create_source_database(source)

    backup_path = create_sqlite_backup(source, backup_dir=tmp_path / "backups")

    assert backup_path.exists()
    assert _read_value(backup_path) == "kept"
    validation = validate_sqlite_backup(backup_path)
    assert validation.schema_version == CURRENT_SCHEMA_VERSION
    assert "sample_data" in validation.tables


def test_backup_refuses_to_overwrite_existing_file(tmp_path: Path) -> None:
    source = tmp_path / "source.db"
    target = tmp_path / "backup.db"
    _create_source_database(source)
    target.write_text("existing", encoding="utf-8")

    with pytest.raises(BackupError, match="already exists"):
        create_sqlite_backup(source, backup_path=target)

    assert target.read_text(encoding="utf-8") == "existing"


def test_restore_refuses_to_overwrite_without_explicit_flag(tmp_path: Path) -> None:
    source = tmp_path / "source.db"
    target = tmp_path / "target.db"
    _create_source_database(source)
    backup_path = create_sqlite_backup(source, backup_path=tmp_path / "backup.db")
    with closing(sqlite3.connect(target)) as connection:
        connection.execute(f"PRAGMA user_version = {CURRENT_SCHEMA_VERSION}")
        connection.execute("CREATE TABLE sample_data (id INTEGER PRIMARY KEY, value TEXT NOT NULL)")
        connection.execute("INSERT INTO sample_data (value) VALUES ('old')")
        connection.commit()

    with pytest.raises(BackupError, match="restore target already exists"):
        restore_sqlite_backup(backup_path, target)

    assert _read_value(target) == "old"


def test_restore_replaces_target_atomically_when_backup_is_valid(tmp_path: Path) -> None:
    source = tmp_path / "source.db"
    target = tmp_path / "target.db"
    _create_source_database(source)
    backup_path = create_sqlite_backup(source, backup_path=tmp_path / "backup.db")

    with closing(sqlite3.connect(target)) as connection:
        connection.execute(f"PRAGMA user_version = {CURRENT_SCHEMA_VERSION}")
        connection.execute("CREATE TABLE sample_data (id INTEGER PRIMARY KEY, value TEXT NOT NULL)")
        connection.execute("INSERT INTO sample_data (value) VALUES ('old')")
        connection.commit()

    restored = restore_sqlite_backup(backup_path, target, overwrite=True)

    assert restored == target.resolve()
    assert _read_value(target) == "kept"


def test_restore_failure_does_not_replace_existing_database(tmp_path: Path) -> None:
    invalid_backup = tmp_path / "invalid.db"
    target = tmp_path / "target.db"
    invalid_backup.write_text("not sqlite", encoding="utf-8")
    _create_source_database(target)

    with pytest.raises(BackupError):
        restore_sqlite_backup(invalid_backup, target, overwrite=True)

    assert _read_value(target) == "kept"
