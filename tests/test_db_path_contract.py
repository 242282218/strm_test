import re
from pathlib import Path

from app.core.db import resolve_db_path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_COMPAT_PATH = PROJECT_ROOT / "app" / "core" / "database.py"
STABLE_STREAM_API_PATH = PROJECT_ROOT / "app" / "api" / "stable_stream.py"
DATABASE_COMPAT_IMPORT_PATTERN = re.compile(r"^\s*(?:from\s+app\.core\.database\s+import|import\s+app\.core\.database\b)", re.MULTILINE)
CONFIG_MANAGER_IMPORT_PATTERN = re.compile(
    r"^\s*from\s+app\.core\.config_manager\s+import\s+.*\bConfigManager\b",
    re.MULTILINE,
)
CONFIG_MANAGER_GETTER_IMPORT_PATTERN = re.compile(
    r"^\s*from\s+app\.core\.config_manager\s+import\s+.*\bget_config\b",
    re.MULTILINE,
)


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


def test_app_code_avoids_database_compatibility_imports() -> None:
    offenders: list[str] = []

    for path in (PROJECT_ROOT / "app").rglob("*.py"):
        if path == DATABASE_COMPAT_PATH:
            continue

        document = path.read_text(encoding="utf-8")
        if DATABASE_COMPAT_IMPORT_PATTERN.search(document):
            offenders.append(path.relative_to(PROJECT_ROOT).as_posix())

    assert offenders == []


def test_api_code_avoids_direct_config_manager_imports() -> None:
    offenders: list[str] = []

    for path in (PROJECT_ROOT / "app" / "api").rglob("*.py"):
        document = path.read_text(encoding="utf-8")
        if CONFIG_MANAGER_IMPORT_PATTERN.search(document):
            offenders.append(path.relative_to(PROJECT_ROOT).as_posix())

    assert offenders == []


def test_stable_stream_api_avoids_config_manager_getter_import() -> None:
    document = STABLE_STREAM_API_PATH.read_text(encoding="utf-8")

    assert CONFIG_MANAGER_GETTER_IMPORT_PATTERN.search(document) is None
