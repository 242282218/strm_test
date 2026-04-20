from collections.abc import Iterator
from pathlib import Path
import re


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOCS_INDEX_PATH = PROJECT_ROOT / "docs" / "README.md"
CURRENT_STATE_DOC_PATH = PROJECT_ROOT / "docs" / "architecture" / "current-state.md"
COMPATIBILITY_DOC_PATH = PROJECT_ROOT / "docs" / "development" / "compatibility-inventory.md"
CODEX_WORKING_AGREEMENT_PATH = PROJECT_ROOT / "docs" / "development" / "codex-working-agreement.md"
DEVELOPMENT_README_PATH = PROJECT_ROOT / "docs" / "development" / "README.md"
API_DOC_PATH = PROJECT_ROOT / "docs" / "api" / "README.md"
OPS_DOC_PATH = PROJECT_ROOT / "docs" / "operations" / "README.md"
MONITORING_DOC_PATH = PROJECT_ROOT / "docs" / "monitoring" / "README.md"
WEB_README_PATH = PROJECT_ROOT / "web" / "README.md"
PLAN_DOC_PATH = PROJECT_ROOT / "docs" / "plans" / "2026-04-20-codex-project-audit-optimization-plan.md"
CORE_BOUNDARIES_DOC_PATH = PROJECT_ROOT / "docs" / "architecture" / "core-truth-source-boundaries.md"
WRAPPER_DIRS = {
    "views": PROJECT_ROOT / "web" / "src" / "views",
    "api": PROJECT_ROOT / "web" / "src" / "api",
    "components": PROJECT_ROOT / "web" / "src" / "components",
    "stores": PROJECT_ROOT / "web" / "src" / "stores",
}
FEATURE_MARKERS = ("@/features/", "../features/", "./features/")
HOTSPOT_PATH_PATTERN = re.compile(r"^\|\s*`([^`]+)`\s*\|", re.MULTILINE)
HOTSPOT_ROW_PATTERN = re.compile(r"^\|\s*`([^`]+)`\s*\|\s*(\d+)\s*\|", re.MULTILINE)
MARKDOWN_LINK_PATTERN = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
HOTSPOT_TABLES = (
    ("后端热点（`app/`）", PROJECT_ROOT / "app", {".py"}, 10),
    ("前端热点（`web/src/`）", PROJECT_ROOT / "web" / "src", {".ts", ".vue"}, 10),
    ("测试热点（`tests/`）", PROJECT_ROOT / "tests", {".py"}, 10),
)
TOP_LEVEL_ENTRY_DOCS = (
    PROJECT_ROOT / "docs" / "architecture" / "current-state.md",
    PROJECT_ROOT / "docs" / "architecture" / "core-truth-source-boundaries.md",
    PROJECT_ROOT / "docs" / "api" / "README.md",
    PROJECT_ROOT / "docs" / "operations" / "README.md",
    PROJECT_ROOT / "docs" / "monitoring" / "README.md",
    PROJECT_ROOT / "docs" / "development" / "codex-working-agreement.md",
    PROJECT_ROOT / "docs" / "development" / "compatibility-inventory.md",
    PROJECT_ROOT / "docs" / "plans" / "2026-04-20-codex-project-audit-optimization-plan.md",
)
DOCS_INDEX_LINKS = (
    ("guides/README.md", "./guides/README.md"),
    ("architecture/README.md", "./architecture/README.md"),
    ("development/README.md", "./development/README.md"),
    ("operations/README.md", "./operations/README.md"),
    ("monitoring/README.md", "./monitoring/README.md"),
    ("api/README.md", "./api/README.md"),
    ("development_plan.md", "./development_plan.md"),
    ("test_report.md", "./test_report.md"),
    ("history.md", "./history.md"),
    ("architecture/current-state.md", "./architecture/current-state.md"),
    ("architecture/core-truth-source-boundaries.md", "./architecture/core-truth-source-boundaries.md"),
    ("development/codex-working-agreement.md", "./development/codex-working-agreement.md"),
    ("development/compatibility-inventory.md", "./development/compatibility-inventory.md"),
    ("plans/2026-04-20-codex-project-audit-optimization-plan.md", "./plans/2026-04-20-codex-project-audit-optimization-plan.md"),
)
DEVELOPMENT_ENTRY_DOCS = (
    PROJECT_ROOT / "docs" / "development" / "codex-working-agreement.md",
    PROJECT_ROOT / "docs" / "development" / "compatibility-inventory.md",
    PROJECT_ROOT / "docs" / "architecture" / "current-state.md",
    PROJECT_ROOT / "docs" / "architecture" / "core-truth-source-boundaries.md",
)
EXECUTION_ENTRY_DOCS_WITH_LINKS = (
    CURRENT_STATE_DOC_PATH,
    DEVELOPMENT_README_PATH,
    CODEX_WORKING_AGREEMENT_PATH,
    MONITORING_DOC_PATH,
    PLAN_DOC_PATH,
)


def _iter_feature_wrappers() -> Iterator[str]:
    for wrapper_dir in WRAPPER_DIRS.values():
        for path in sorted(wrapper_dir.iterdir()):
            if not path.is_file() or ".spec." in path.name:
                continue
            content = path.read_text(encoding="utf-8")
            if any(marker in content for marker in FEATURE_MARKERS):
                yield path.relative_to(PROJECT_ROOT).as_posix()


def _feature_wrapper_counts() -> dict[str, int]:
    counts: dict[str, int] = {}

    for category, wrapper_dir in WRAPPER_DIRS.items():
        count = 0
        for path in wrapper_dir.iterdir():
            if not path.is_file() or ".spec." in path.name:
                continue
            content = path.read_text(encoding="utf-8")
            if any(marker in content for marker in FEATURE_MARKERS):
                count += 1
        counts[category] = count

    return counts


def _iter_markdown_table_paths(document: str) -> Iterator[str]:
    for match in HOTSPOT_PATH_PATTERN.finditer(document):
        yield match.group(1)


def _count_lines(path: Path) -> int:
    with path.open(encoding="utf-8") as handle:
        return sum(1 for _ in handle)


def _collect_hotspots(root: Path, suffixes: set[str], limit: int) -> list[tuple[str, int]]:
    rows: list[tuple[str, int]] = []

    for path in root.rglob("*"):
        if not path.is_file() or path.suffix not in suffixes:
            continue
        rows.append((path.relative_to(PROJECT_ROOT).as_posix(), _count_lines(path)))

    rows.sort(key=lambda item: (-item[1], item[0]))
    return rows[:limit]


def _section_body(document: str, heading: str) -> str:
    pattern = rf"### {re.escape(heading)}\n\n(.*?)(?=\n### |\Z)"
    match = re.search(pattern, document, re.DOTALL)
    assert match is not None, f"Missing section: {heading}"
    return match.group(1)


def _iter_hotspot_rows(document: str, heading: str) -> Iterator[tuple[str, int]]:
    section = _section_body(document, heading)

    for path, line_count in HOTSPOT_ROW_PATTERN.findall(section):
        yield path, int(line_count)


def _iter_relative_markdown_links(document: str) -> Iterator[str]:
    for match in MARKDOWN_LINK_PATTERN.finditer(document):
        target = match.group(1)
        if target.startswith(("http://", "https://", "#")):
            continue
        yield target


def _assert_relative_links_resolve(path: Path) -> None:
    document = path.read_text(encoding="utf-8")

    for relative_target in _iter_relative_markdown_links(document):
        resolved_path = (path.parent / relative_target).resolve()
        assert resolved_path.exists(), f"{path.relative_to(PROJECT_ROOT).as_posix()} link target missing: {relative_target}"


def test_current_state_doc_tracks_entrypoints_and_hotspots() -> None:
    document = CURRENT_STATE_DOC_PATH.read_text(encoding="utf-8")
    wrapper_counts = _feature_wrapper_counts()

    for path_hint in (
        "app/config/application.py",
        "app/api/v1/__init__.py",
        "web/src/router/index.ts",
        "web/package-lock.json",
        "web/playwright.config.ts",
        "vars.QUARK_STRM_COVERAGE_FAIL_UNDER",
        "docs/development/compatibility-inventory.md",
        "core-truth-source-boundaries.md",
        "app/config/settings.py",
        "web/src/features/rename/views/RenameView.vue",
        "web/src/features/config/views/ConfigView.vue",
        "web/src/features/proxy/views/ProxyServiceView.vue",
    ):
        assert path_hint in document

    for count_hint in (
        f"视图包装：{wrapper_counts['views']}",
        f"API 包装：{wrapper_counts['api']}",
        f"组件包装：{wrapper_counts['components']}",
        f"Store 包装：{wrapper_counts['stores']}",
    ):
        assert count_hint in document


def test_current_state_hotspot_paths_exist_in_repo() -> None:
    document = CURRENT_STATE_DOC_PATH.read_text(encoding="utf-8")

    for relative_path in _iter_markdown_table_paths(document):
        resolved_path = PROJECT_ROOT / relative_path
        assert resolved_path.exists(), f"Hotspot path missing from repo: {relative_path}"


def test_current_state_hotspot_tables_match_live_top_files() -> None:
    document = CURRENT_STATE_DOC_PATH.read_text(encoding="utf-8")

    for heading, root, suffixes, limit in HOTSPOT_TABLES:
        assert list(_iter_hotspot_rows(document, heading)) == _collect_hotspots(root, suffixes, limit)


def test_docs_index_points_to_current_execution_entry_docs() -> None:
    document = DOCS_INDEX_PATH.read_text(encoding="utf-8")

    assert "**最后同步**: 2026-04-20" in document

    for label, relative_target in DOCS_INDEX_LINKS:
        assert f"[`{label}`]({relative_target})" in document

    for path in TOP_LEVEL_ENTRY_DOCS:
        assert path.exists(), f"Top-level execution entry doc missing: {path.relative_to(PROJECT_ROOT).as_posix()}"

    for entry_hint in (
        "[`api/README.md`](./api/README.md) - API 路径、认证和 canonical/compatibility 映射入口",
        "[`operations/README.md`](./operations/README.md) - 部署、运行目录边界和本地产物约定入口",
        "[`monitoring/README.md`](./monitoring/README.md) - Prometheus 指标、抓取配置示例和 Grafana 资产入口",
    ):
        assert entry_hint in document


def test_docs_index_relative_links_resolve_to_existing_files() -> None:
    _assert_relative_links_resolve(DOCS_INDEX_PATH)


def test_execution_entry_docs_relative_links_resolve_to_existing_files() -> None:
    for path in EXECUTION_ENTRY_DOCS_WITH_LINKS:
        _assert_relative_links_resolve(path)


def test_compatibility_inventory_lists_all_current_feature_wrappers() -> None:
    document = COMPATIBILITY_DOC_PATH.read_text(encoding="utf-8")
    wrapper_counts = _feature_wrapper_counts()

    for status_hint in ("wrapper-active", "wrapper-deprecated", "remove-after:"):
        assert status_hint in document

    for count_hint in (
        f"视图包装：{wrapper_counts['views']}",
        f"API 包装：{wrapper_counts['api']}",
        f"组件包装：{wrapper_counts['components']}",
        f"Store 包装：{wrapper_counts['stores']}",
    ):
        assert count_hint in document

    for path in _iter_feature_wrappers():
        assert path in document

    assert "web/src/api/fileManager.ts" in document
    assert "camelCase 导入全部删除" in document
    assert "module-aliases.spec.ts" in document


def test_codex_working_agreement_points_to_current_truth_sources() -> None:
    document = CODEX_WORKING_AGREEMENT_PATH.read_text(encoding="utf-8")

    for path_hint in (
        "current-state.md",
        "core-truth-source-boundaries.md",
        "compatibility-inventory.md",
        "docs/api/README.md",
        "docs/operations/README.md",
        "../monitoring/README.md",
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

    for script_hint in (
        "scripts/continuous_optimize.py",
        "--repo-root",
        "--report-dir",
        "--skip-agent-optimize",
        "--list-modules",
        "--unsafe-bypass-sandbox",
        "target/continuous/module-inventory.json",
        "target/continuous/latest.json",
        "target/continuous/latest.md",
        "target/continuous/iterations/<iteration-slug>.json",
        "target/continuous/iterations/<iteration-slug>.md",
        "target/continuous/logs/",
        "target/continuous/prompts/",
        "target/continuous/agents/",
        "no matching pytest targets",
        "no matching frontend targets",
        "target/continuous/STOP_CONTINUOUS_LOOP",
    ):
        assert script_hint in document


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
    assert "../architecture/core-truth-source-boundaries.md" in development_document
    assert "[`../api/README.md`](../api/README.md) - API 路径、认证与 canonical/compatibility 映射入口" in development_document
    assert "[`../operations/README.md`](../operations/README.md) - 部署命令、运行目录边界和本地产物约定入口" in development_document
    assert "npm run format" not in development_document

    for path in DEVELOPMENT_ENTRY_DOCS:
        assert path.exists(), f"Development execution entry doc missing: {path.relative_to(PROJECT_ROOT).as_posix()}"

    assert "文档最后同步日期：`2026-04-20`" in web_document
    assert "npm ci" in web_document
    assert "pnpm install" in web_document
    assert "pnpm run dev" in web_document
    assert "pnpm run lint --fix" in web_document
    assert "pnpm run test:smoke" in web_document
    assert "pnpm run test:e2e" in web_document
    assert "web/package-lock.json" in web_document
    assert "npm run dev -- --host ... --port ..." in web_document


def test_api_and_operations_entry_docs_have_sync_dates_and_resolvable_links() -> None:
    for path, path_hints in (
        (
            API_DOC_PATH,
            ("app/api/", "app/api/v1/", "app/config/application.py"),
        ),
        (
            OPS_DOC_PATH,
            (
                "Dockerfile",
                "docker-compose.yml",
                ".github/workflows/docker-deploy-test.yml",
                ".github/workflows/docker-publish.yml",
                "web/",
            ),
        ),
    ):
        document = path.read_text(encoding="utf-8")

        assert "**最后同步**: 2026-04-20" in document

        for hint in path_hints:
            assert hint in document

        _assert_relative_links_resolve(path)


def test_plan_doc_tracks_execution_progress_and_current_boundaries() -> None:
    document = PLAN_DOC_PATH.read_text(encoding="utf-8")

    for hint in (
        "执行进度快照（2026-04-20 更新）",
        "docs/architecture/current-state.md",
        "docs/architecture/core-truth-source-boundaries.md",
        "docs/api/README.md",
        "docs/operations/README.md",
        "docs/monitoring/README.md",
        "docs/development/compatibility-inventory.md",
        "docs/development/codex-working-agreement.md",
        "Phase / Iteration 状态总览",
        "Phase 0 | 已完成",
        "Phase 5 | 大部分完成",
        "Phase 6 | 已完成",
        "Iteration 1 | 已完成",
        "Iteration 6 | 已完成",
        "首批执行清单状态",
        "`[已完成]` 收敛 `.github/workflows/ci.yml`",
        "`[未开始]` 拆 `ConfigView.vue` 的状态/动作层。",
        "下文 Phase 与 Iteration 正文保留原始路线图",
        "../architecture/current-state.md",
        "../api/README.md",
        "../operations/README.md",
        "../monitoring/README.md",
        "../development/codex-working-agreement.md",
        "web/package-lock.json",
        "app/api/v1",
        "web/src/features/config/*",
        "npm run dev",
        "pnpm run ...",
        "scripts/continuous_optimize.py",
        "STOP_CONTINUOUS_LOOP",
        "tests/test_continuous_optimize_contract.py",
        "prometheus.yml",
        "grafana-dashboard.json",
    ):
        assert hint in document


def test_monitoring_doc_tracks_live_assets_and_links() -> None:
    document = MONITORING_DOC_PATH.read_text(encoding="utf-8")

    for hint in (
        "**最后同步**: 2026-04-20",
        "app/api/prometheus.py",
        "app/core/prometheus_metrics.py",
        "../../prometheus.yml",
        "./grafana-dashboard.json",
        "/metrics",
        "/metrics/health",
        "当前 `docs/monitoring/` 目录只落地了 `README.md` 与 `grafana-dashboard.json`。",
        "当前仓库尚未落地 `prometheus-rules.yml` 或 `alerting/alertmanager.yml`",
        "../operations/README.md",
        "../api/README.md",
        "../architecture/current-state.md",
    ):
        assert hint in document

    _assert_relative_links_resolve(MONITORING_DOC_PATH)


def test_core_truth_source_boundary_doc_tracks_phase3_entrypoints() -> None:
    document = CORE_BOUNDARIES_DOC_PATH.read_text(encoding="utf-8")

    for hint in (
        "**最后校验**: 2026-04-20",
        "app/core/db.py",
        "app/core/database.py",
        "app/core/db_utils.py",
        "app/core/error_codes.py",
        "app/core/exceptions.py",
        "app/core/exception_handler.py",
        "app/config/settings.py",
        "app/services/config_service.py",
        "tests/test_db.py",
        "tests/test_db_pool.py",
        "tests/test_system_config_api.py",
        "tests/test_encryption.py",
    ):
        assert hint in document
