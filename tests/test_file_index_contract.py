from pathlib import Path


FILE_INDEX_PATH = Path(__file__).resolve().parents[1] / "docs" / "FILE_INDEX.md"


def test_file_index_tracks_current_core_and_runtime_structure() -> None:
    document = FILE_INDEX_PATH.read_text(encoding="utf-8")

    assert document.count("**最后更新**: 2026-04-20") >= 2

    for path_hint in (
        "cache/",
        "output/",
        "target/",
        "tmp_wheel/",
        "current-state.md",
        "codex-working-agreement.md",
        "compatibility-inventory.md",
        "2026-04-20-codex-project-audit-optimization-plan.md",
        "app/api/v1/__init__.py",
        "config_manager.py",
        "cache_manager.py",
        "metrics_collector.py",
        "websocket_manager.py",
        "url_validator.py",
    ):
        assert path_hint in document
