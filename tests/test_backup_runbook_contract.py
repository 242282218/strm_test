from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OPS_DOC_PATH = PROJECT_ROOT / "docs" / "operations" / "README.md"


def test_operations_runbook_uses_online_sqlite_backup_and_explicit_migration() -> None:
    document = OPS_DOC_PATH.read_text(encoding="utf-8")

    assert "PRAGMA user_version" in document
    assert "python -m app.migrations.runner --db quark_strm.db" in document
    assert "python -m app.migrations.backup backup --db quark_strm.db --out-dir backups" in document
    assert "python -m app.migrations.backup restore --backup" in document
    assert "不要在 WAL 模式下裸复制 `quark_strm.db`" in document
    assert "cp quark_strm.db quark_strm.db.backup" not in document
    assert "cp quark_strm.db.backup.* quark_strm.db" not in document
