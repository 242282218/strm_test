from __future__ import annotations

import argparse
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Sequence

from app.migrations.runner import CURRENT_SCHEMA_VERSION


class BackupError(RuntimeError):
    """Raised when a database backup or restore cannot safely complete."""


@dataclass(frozen=True)
class BackupValidation:
    path: Path
    schema_version: int
    tables: tuple[str, ...]


def _connect(path: Path, *, read_only: bool) -> sqlite3.Connection:
    if read_only:
        return sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    return sqlite3.connect(str(path))


def _default_backup_path(source_path: Path, backup_dir: Path) -> Path:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return backup_dir / f"{source_path.stem}.{timestamp}.db"


def validate_sqlite_backup(
    path: str | Path,
    *,
    expected_schema_version: int | None = CURRENT_SCHEMA_VERSION,
) -> BackupValidation:
    backup_path = Path(path).expanduser().resolve()
    if not backup_path.exists():
        raise BackupError(f"backup file does not exist: {backup_path}")

    try:
        with closing(_connect(backup_path, read_only=True)) as connection:
            integrity = connection.execute("PRAGMA integrity_check").fetchone()
            if not integrity or integrity[0] != "ok":
                raise BackupError(f"backup integrity check failed: {integrity[0] if integrity else 'unknown'}")

            schema_version = int(connection.execute("PRAGMA user_version").fetchone()[0] or 0)
            if expected_schema_version is not None and schema_version != expected_schema_version:
                raise BackupError(
                    f"backup schema version {schema_version} does not match expected {expected_schema_version}"
                )

            rows = connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
    except sqlite3.DatabaseError as exc:
        raise BackupError(f"backup is not a valid SQLite database: {exc}") from exc

    return BackupValidation(
        path=backup_path,
        schema_version=schema_version,
        tables=tuple(str(row[0]) for row in rows),
    )


def create_sqlite_backup(
    source_path: str | Path,
    *,
    backup_dir: str | Path | None = None,
    backup_path: str | Path | None = None,
) -> Path:
    source = Path(source_path).expanduser().resolve()
    if not source.exists():
        raise BackupError(f"source database does not exist: {source}")

    if backup_path is None:
        target_dir = Path(backup_dir).expanduser().resolve() if backup_dir else source.parent / "backups"
        target_dir.mkdir(parents=True, exist_ok=True)
        target = _default_backup_path(source, target_dir)
    else:
        target = Path(backup_path).expanduser().resolve()
        target.parent.mkdir(parents=True, exist_ok=True)

    if target.exists():
        raise BackupError(f"backup target already exists: {target}")

    try:
        with closing(_connect(source, read_only=True)) as source_connection:
            with closing(sqlite3.connect(str(target))) as target_connection:
                source_connection.backup(target_connection)
    except sqlite3.DatabaseError as exc:
        if target.exists():
            target.unlink(missing_ok=True)
        raise BackupError(f"create backup: {exc}") from exc

    return target


def restore_sqlite_backup(
    backup_path: str | Path,
    target_path: str | Path,
    *,
    overwrite: bool = False,
    expected_schema_version: int | None = CURRENT_SCHEMA_VERSION,
) -> Path:
    source = validate_sqlite_backup(backup_path, expected_schema_version=expected_schema_version).path
    target = Path(target_path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)

    if target.exists() and not overwrite:
        raise BackupError(f"restore target already exists: {target}")

    temp_target = target.with_name(f"{target.name}.restore.tmp")
    if temp_target.exists():
        raise BackupError(f"temporary restore target already exists: {temp_target}")

    try:
        with closing(_connect(source, read_only=True)) as source_connection:
            with closing(sqlite3.connect(str(temp_target))) as target_connection:
                source_connection.backup(target_connection)
        validate_sqlite_backup(temp_target, expected_schema_version=expected_schema_version)
        temp_target.replace(target)
    except Exception as exc:
        temp_target.unlink(missing_ok=True)
        if isinstance(exc, BackupError):
            raise
        raise BackupError(f"restore backup: {exc}") from exc

    return target


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Backup or restore Smart Media SQLite databases.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    backup_parser = subparsers.add_parser("backup", help="Create a SQLite online backup.")
    backup_parser.add_argument("--db", required=True, help="Source SQLite database path.")
    backup_parser.add_argument("--out-dir", help="Backup output directory.")
    backup_parser.add_argument("--out", help="Exact backup file path. Must not already exist.")

    restore_parser = subparsers.add_parser("restore", help="Restore a SQLite backup.")
    restore_parser.add_argument("--backup", required=True, help="Backup file to restore.")
    restore_parser.add_argument("--db", required=True, help="Restore target database path.")
    restore_parser.add_argument("--overwrite", action="store_true", help="Atomically replace target database.")

    args = parser.parse_args(argv)
    if args.command == "backup":
        path = create_sqlite_backup(args.db, backup_dir=args.out_dir, backup_path=args.out)
        print(path)
        return 0

    path = restore_sqlite_backup(args.backup, args.db, overwrite=args.overwrite)
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
