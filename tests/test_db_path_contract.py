from pathlib import Path

from app.core.db import resolve_db_path


def test_resolve_db_path_uses_current_working_directory_for_relative_paths(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)

    result = resolve_db_path("relative/test.db")

    assert result == str((tmp_path / "relative" / "test.db").resolve())


def test_resolve_db_path_keeps_absolute_paths_absolute(tmp_path: Path) -> None:
    absolute_path = tmp_path / "absolute.db"

    result = resolve_db_path(str(absolute_path))

    assert result == str(absolute_path.resolve())
