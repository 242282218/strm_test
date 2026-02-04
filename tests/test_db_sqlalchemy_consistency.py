from pathlib import Path

from sqlalchemy import text

from app.core.database import Database, resolve_db_path
from app.core.db import engine


def test_sqlalchemy_and_sqlite_db_path_consistency():
    resolved_path = Path(resolve_db_path())
    assert resolved_path.is_absolute()

    Database(str(resolved_path))

    engine_path = Path(engine.url.database)
    assert engine_path.is_absolute()
    assert engine_path == resolved_path

    with engine.connect() as conn:
        result = conn.execute(
            text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='strm'"
            )
        ).fetchone()

    assert result is not None
