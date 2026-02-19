"""Database path helpers."""

import os
from pathlib import Path
from typing import Optional

from app.services.config_service import get_config_service


def resolve_db_path(db_path: Optional[str] = None) -> str:
    """
    Resolve the SQLite database file path.

    If no explicit path is provided, the value is read from runtime config.
    Relative paths are resolved under the local `data/` directory.
    """
    if not db_path:
        cfg = get_config_service().get_config()
        db_path = cfg.database

    if os.path.isabs(db_path):
        return str(Path(db_path).resolve())

    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)
    return str((data_dir / db_path).resolve())
