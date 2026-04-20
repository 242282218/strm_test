from collections.abc import Iterator
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CURRENT_STATE_DOC_PATH = PROJECT_ROOT / "docs" / "architecture" / "current-state.md"
COMPATIBILITY_DOC_PATH = PROJECT_ROOT / "docs" / "development" / "compatibility-inventory.md"


def _iter_feature_wrappers() -> Iterator[str]:
    wrapper_dirs = (
        PROJECT_ROOT / "web" / "src" / "views",
        PROJECT_ROOT / "web" / "src" / "api",
        PROJECT_ROOT / "web" / "src" / "components",
        PROJECT_ROOT / "web" / "src" / "stores",
    )
    feature_markers = ("@/features/", "../features/", "./features/")

    for wrapper_dir in wrapper_dirs:
        for path in sorted(wrapper_dir.iterdir()):
            if not path.is_file() or ".spec." in path.name:
                continue
            content = path.read_text(encoding="utf-8")
            if any(marker in content for marker in feature_markers):
                yield path.relative_to(PROJECT_ROOT).as_posix()


def test_current_state_doc_tracks_entrypoints_and_hotspots() -> None:
    document = CURRENT_STATE_DOC_PATH.read_text(encoding="utf-8")

    for path_hint in (
        "app/config/application.py",
        "app/api/v1/__init__.py",
        "web/src/router/index.ts",
        "vars.QUARK_STRM_COVERAGE_FAIL_UNDER",
        "docs/development/compatibility-inventory.md",
        "app/config/settings.py",
        "web/src/features/rename/views/RenameView.vue",
        "web/src/features/config/views/ConfigView.vue",
        "web/src/features/proxy/views/ProxyServiceView.vue",
    ):
        assert path_hint in document

    for count_hint in (
        "视图包装：19",
        "API 包装：15",
        "组件包装：3",
        "Store 包装：2",
    ):
        assert count_hint in document


def test_compatibility_inventory_lists_all_current_feature_wrappers() -> None:
    document = COMPATIBILITY_DOC_PATH.read_text(encoding="utf-8")

    for status_hint in ("wrapper-active", "wrapper-deprecated", "remove-after:"):
        assert status_hint in document

    for path in _iter_feature_wrappers():
        assert path in document

    assert "web/src/api/fileManager.ts" in document
    assert "camelCase 导入全部删除" in document
    assert "module-aliases.spec.ts" in document
