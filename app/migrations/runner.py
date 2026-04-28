from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.pool import NullPool

from app.core.db import Base, get_engine


CURRENT_SCHEMA_VERSION = 2

MODEL_MODULES = (
    "app.models.cloud_drive",
    "app.models.emby",
    "app.models.media_mapping",
    "app.models.notification",
    "app.models.scrape",
    "app.models.security_event",
    "app.models.strm_record",
    "app.models.task",
    "app.models.user",
)


class MigrationError(RuntimeError):
    """Raised when schema migration cannot safely complete."""


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    apply: Callable[[Connection], None]


@dataclass(frozen=True)
class MigrationResult:
    previous_version: int
    current_version: int
    target_version: int
    applied_versions: tuple[int, ...]

    @property
    def changed(self) -> bool:
        return bool(self.applied_versions)


def import_model_metadata() -> None:
    """Import ORM models so SQLAlchemy metadata reflects the full app schema."""
    for module_name in MODEL_MODULES:
        import_module(module_name)


def get_schema_version(connection: Connection) -> int:
    value = connection.execute(text("PRAGMA user_version")).scalar()
    return int(value or 0)


def set_schema_version(connection: Connection, version: int) -> None:
    if version < 0:
        raise ValueError("schema version must be non-negative")
    connection.exec_driver_sql(f"PRAGMA user_version = {version}")


def apply_baseline_schema(connection: Connection) -> None:
    import_model_metadata()
    Base.metadata.create_all(bind=connection)


def _sqlite_table_columns(connection: Connection, table_name: str) -> set[str]:
    rows = connection.exec_driver_sql(f"PRAGMA table_info({table_name})").fetchall()
    return {str(row[1]) for row in rows}


def _add_sqlite_column_if_missing(connection: Connection, table_name: str, column_name: str, definition: str) -> None:
    if column_name in _sqlite_table_columns(connection, table_name):
        return
    connection.exec_driver_sql(f"ALTER TABLE {table_name} ADD COLUMN {definition}")


def apply_task_runtime_schema(connection: Connection) -> None:
    _add_sqlite_column_if_missing(connection, "tasks", "resume_cursor", "resume_cursor JSON DEFAULT '{}'")
    _add_sqlite_column_if_missing(connection, "tasks", "lease_owner", "lease_owner VARCHAR")
    _add_sqlite_column_if_missing(connection, "tasks", "lease_until", "lease_until DATETIME")
    _add_sqlite_column_if_missing(connection, "tasks", "heartbeat_at", "heartbeat_at DATETIME")
    _add_sqlite_column_if_missing(connection, "tasks", "attempt", "attempt INTEGER NOT NULL DEFAULT 0")
    _add_sqlite_column_if_missing(connection, "tasks", "max_attempts", "max_attempts INTEGER NOT NULL DEFAULT 3")
    _add_sqlite_column_if_missing(connection, "tasks", "idempotency_key", "idempotency_key VARCHAR")
    _add_sqlite_column_if_missing(connection, "tasks", "next_run_at", "next_run_at DATETIME")
    connection.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_tasks_lease_owner ON tasks (lease_owner)")
    connection.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_tasks_lease_until ON tasks (lease_until)")
    connection.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_tasks_idempotency_key ON tasks (idempotency_key)")
    connection.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_tasks_next_run_at ON tasks (next_run_at)")


DEFAULT_MIGRATIONS: tuple[Migration, ...] = (
    Migration(version=1, name="baseline_sqlalchemy_schema", apply=apply_baseline_schema),
    Migration(version=2, name="task_runtime_lease_fields", apply=apply_task_runtime_schema),
)


def _normalize_migrations(migrations: Sequence[Migration]) -> tuple[Migration, ...]:
    ordered = tuple(sorted(migrations, key=lambda item: item.version))
    seen: set[int] = set()
    for migration in ordered:
        if migration.version <= 0:
            raise ValueError("migration versions must be positive")
        if migration.version in seen:
            raise ValueError(f"duplicate migration version: {migration.version}")
        seen.add(migration.version)
    return ordered


def run_migrations(
    engine: Engine | None = None,
    migrations: Sequence[Migration] = DEFAULT_MIGRATIONS,
) -> MigrationResult:
    active_engine = engine or get_engine()
    ordered_migrations = _normalize_migrations(migrations)
    target_version = ordered_migrations[-1].version if ordered_migrations else 0

    with active_engine.connect() as connection:
        previous_version = get_schema_version(connection)

    if previous_version > target_version:
        raise MigrationError(
            f"database schema version {previous_version} is newer than supported version {target_version}"
        )

    current_version = previous_version
    applied_versions: list[int] = []
    for migration in ordered_migrations:
        if migration.version <= current_version:
            continue
        try:
            with active_engine.begin() as connection:
                live_version = get_schema_version(connection)
                if live_version != current_version:
                    current_version = live_version
                    if migration.version <= current_version:
                        continue
                migration.apply(connection)
                set_schema_version(connection, migration.version)
        except Exception as exc:
            raise MigrationError(f"apply migration {migration.version} {migration.name}: {exc}") from exc

        current_version = migration.version
        applied_versions.append(migration.version)

    return MigrationResult(
        previous_version=previous_version,
        current_version=current_version,
        target_version=target_version,
        applied_versions=tuple(applied_versions),
    )


def _create_file_engine(db_path: str) -> Engine:
    path = Path(db_path).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = str(path).replace("\\", "/")
    return create_engine(
        f"sqlite:///{normalized}",
        connect_args={"check_same_thread": False, "timeout": 30},
        poolclass=NullPool,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Smart Media database migrations.")
    parser.add_argument("--db", help="SQLite database path. Defaults to configured application database.")
    args = parser.parse_args(argv)

    engine = _create_file_engine(args.db) if args.db else None
    try:
        result = run_migrations(engine)
    finally:
        if engine is not None:
            engine.dispose()

    applied = ",".join(str(version) for version in result.applied_versions) or "none"
    print(
        "schema_version="
        f"{result.current_version} target={result.target_version} previous={result.previous_version} applied={applied}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
