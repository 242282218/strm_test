from collections.abc import Iterator
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOCS_INDEX_PATH = PROJECT_ROOT / "docs" / "README.md"
CURRENT_STATE_DOC_PATH = PROJECT_ROOT / "docs" / "architecture" / "current-state.md"
COMPATIBILITY_DOC_PATH = PROJECT_ROOT / "docs" / "development" / "compatibility-inventory.md"
CODEX_WORKING_AGREEMENT_PATH = PROJECT_ROOT / "docs" / "development" / "codex-working-agreement.md"
DEVELOPMENT_README_PATH = PROJECT_ROOT / "docs" / "development" / "README.md"
WEB_README_PATH = PROJECT_ROOT / "web" / "README.md"


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
        "web/package-lock.json",
        "web/playwright.config.ts",
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


def test_docs_index_points_to_current_execution_entry_docs() -> None:
    document = DOCS_INDEX_PATH.read_text(encoding="utf-8")

    assert "**最后同步**: 2026-04-20" in document

    for path_hint in (
        "architecture/current-state.md",
        "development/codex-working-agreement.md",
        "development/compatibility-inventory.md",
        "plans/2026-04-20-codex-project-audit-optimization-plan.md",
    ):
        assert path_hint in document


def test_compatibility_inventory_lists_all_current_feature_wrappers() -> None:
    document = COMPATIBILITY_DOC_PATH.read_text(encoding="utf-8")

    for status_hint in ("wrapper-active", "wrapper-deprecated", "remove-after:"):
        assert status_hint in document

    for path in _iter_feature_wrappers():
        assert path in document

    assert "web/src/api/fileManager.ts" in document
    assert "camelCase 导入全部删除" in document
    assert "module-aliases.spec.ts" in document


def test_codex_working_agreement_points_to_current_truth_sources() -> None:
    document = CODEX_WORKING_AGREEMENT_PATH.read_text(encoding="utf-8")

    for path_hint in (
        "current-state.md",
        "compatibility-inventory.md",
        "docs/api/README.md",
        "docs/operations/README.md",
        "app/api/v1/*",
        "web/src/features/<domain>/",
        "web/src/features/config/*",
        "docs/architecture/README.md",
    ):
        assert path_hint in document

    for command_hint in (
        ".venv\\\\Scripts\\\\python.exe -m pytest tests/test_baseline_docs_contract.py tests/test_file_index_contract.py -q",
        ".venv\\\\Scripts\\\\python.exe -m pytest tests/test_ci_workflow.py tests/test_pytest_workflow_coverage_gate.py tests/test_deployment_contract.py -q",
        ".venv\\\\Scripts\\\\python.exe -m pytest tests/test_api_docs_contract.py tests/test_api_v1_routes.py tests/test_main_entrypoint.py -q",
        "pnpm run lint --fix",
        "pnpm run type-check",
        "pnpm exec vitest run",
    ):
        assert command_hint in document


def test_development_and_web_readmes_match_current_command_contract() -> None:
    development_document = DEVELOPMENT_README_PATH.read_text(encoding="utf-8")
    web_document = WEB_README_PATH.read_text(encoding="utf-8")

    assert "**最后同步**: 2026-04-20" in development_document
    assert "npm ci" in development_document
    assert "pnpm install" in development_document
    assert "pnpm run dev" in development_document
    assert "pnpm run lint --fix" in development_document
    assert "pnpm run test:run" in development_document
    assert "pnpm run test:e2e" in development_document
    assert "vars.QUARK_STRM_COVERAGE_FAIL_UNDER" in development_document
    assert "回退 `66`" in development_document
    assert "npm run format" not in development_document

    assert "文档最后同步日期：`2026-04-20`" in web_document
    assert "npm ci" in web_document
    assert "pnpm install" in web_document
    assert "pnpm run dev" in web_document
    assert "pnpm run lint --fix" in web_document
    assert "pnpm run test:smoke" in web_document
    assert "pnpm run test:e2e" in web_document
    assert "web/package-lock.json" in web_document
    assert "npm run dev -- --host ... --port ..." in web_document
