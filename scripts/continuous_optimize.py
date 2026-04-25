#!/usr/bin/env python3
"""Continuously test quark_strm modules and dispatch Codex optimization lanes."""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import textwrap
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_AGENT_MODEL = "gpt-5.5"
DEFAULT_INTERVAL_SECONDS = 120
DEFAULT_MAX_PARALLEL_AGENTS = 3
DEFAULT_REPORT_DIR = Path("target/continuous")
STOP_FILE_NAME = "STOP_CONTINUOUS_LOOP"


@dataclass(frozen=True)
class CommandPlan:
    name: str
    runner: str
    cwd: str = "."
    command: tuple[str, ...] = ()
    script: str = ""
    base_args: tuple[str, ...] = ()
    target_patterns: tuple[str, ...] = ()
    target_root: str = "."
    timeout_seconds: int = 900
    env_overrides: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class MaterializedCommand:
    name: str
    cwd: Path
    command: tuple[str, ...]
    timeout_seconds: int
    env_overrides: dict[str, str]
    skipped_reason: str | None = None


@dataclass(frozen=True)
class ModuleSpec:
    name: str
    category: str
    description: str
    risk: str
    optimization_lane: str
    ownership_paths: tuple[str, ...]
    command_plans: tuple[CommandPlan, ...]


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def iso_utc(timestamp: dt.datetime) -> str:
    return timestamp.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, payload: Any) -> None:
    ensure_directory(path.parent)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    ensure_directory(path.parent)
    path.write_text(content, encoding="utf-8")


def slugify(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in ("-", "_") else "-" for ch in value).strip("-") or "item"


def quote_command(command: tuple[str, ...] | list[str]) -> str:
    rendered: list[str] = []
    for part in command:
        if any(ch.isspace() for ch in part):
            rendered.append(f'"{part}"')
        else:
            rendered.append(part)
    return " ".join(rendered)


def resolve_repo_root(path: Path) -> Path:
    repo_root = path.resolve()
    if not repo_root.exists():
        raise FileNotFoundError(f"--repo-root does not exist: {repo_root}")
    if not repo_root.is_dir():
        raise NotADirectoryError(f"--repo-root is not a directory: {repo_root}")
    return repo_root


def resolve_report_dir(repo_root: Path, path: Path) -> Path:
    return path.resolve() if path.is_absolute() else (repo_root / path).resolve()


def resolve_stop_file(repo_root: Path, report_dir: Path, path: Path | None) -> Path:
    stop_file = report_dir / STOP_FILE_NAME if path is None else path
    return stop_file.resolve() if stop_file.is_absolute() else (repo_root / stop_file).resolve()


def resolve_python_command(repo_root: Path) -> Path:
    venv_python = repo_root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if venv_python.exists():
        return venv_python
    return Path(sys.executable)


def resolve_runtime_executable(name: str) -> str:
    if os.name != "nt":
        return name
    for candidate in (f"{name}.cmd", f"{name}.exe", name):
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    return name


def resolve_runtime_command(command: tuple[str, ...]) -> list[str]:
    if not command:
        return []
    executable = command[0]
    if any(token in executable for token in ("\\", "/")):
        return list(command)
    return [resolve_runtime_executable(executable), *command[1:]]


def resolve_glob_targets(base_dir: Path, patterns: list[str] | tuple[str, ...]) -> list[str]:
    resolved: list[str] = []
    seen: set[str] = set()
    for pattern in patterns:
        matches = sorted(base_dir.glob(pattern))
        if not matches and not any(token in pattern for token in ("*", "?", "[")):
            candidate = base_dir / pattern
            if candidate.exists():
                matches = [candidate]
        for match in matches:
            if not match.is_file():
                continue
            relative = match.relative_to(base_dir).as_posix()
            if relative in seen:
                continue
            seen.add(relative)
            resolved.append(relative)
    return resolved


def command_plan(
    name: str,
    command: list[str],
    *,
    cwd: str = ".",
    timeout_seconds: int = 900,
    env_overrides: dict[str, str] | None = None,
) -> CommandPlan:
    env_items = tuple(sorted((env_overrides or {}).items()))
    return CommandPlan(
        name=name,
        runner="command",
        cwd=cwd,
        command=tuple(command),
        timeout_seconds=timeout_seconds,
        env_overrides=env_items,
    )


def pytest_plan(name: str, patterns: list[str], *, timeout_seconds: int = 900) -> CommandPlan:
    return CommandPlan(
        name=name,
        runner="pytest",
        target_patterns=tuple(patterns),
        timeout_seconds=timeout_seconds,
        base_args=("-q",),
    )


def pnpm_files_plan(
    name: str,
    script: str,
    patterns: list[str],
    *,
    base_args: list[str] | None = None,
    cwd: str = "web",
    target_root: str = "web",
    timeout_seconds: int = 900,
    env_overrides: dict[str, str] | None = None,
) -> CommandPlan:
    env_items = tuple(sorted((env_overrides or {}).items()))
    return CommandPlan(
        name=name,
        runner="pnpm-files",
        script=script,
        cwd=cwd,
        target_root=target_root,
        target_patterns=tuple(patterns),
        base_args=tuple(base_args or []),
        timeout_seconds=timeout_seconds,
        env_overrides=env_items,
    )


def vitest_files_plan(
    name: str,
    patterns: list[str],
    *,
    base_args: list[str] | None = None,
    cwd: str = "web",
    target_root: str = "web",
    timeout_seconds: int = 900,
    env_overrides: dict[str, str] | None = None,
) -> CommandPlan:
    env_items = tuple(sorted((env_overrides or {}).items()))
    return CommandPlan(
        name=name,
        runner="vitest-files",
        cwd=cwd,
        target_root=target_root,
        target_patterns=tuple(patterns),
        base_args=tuple(base_args or []),
        timeout_seconds=timeout_seconds,
        env_overrides=env_items,
    )


def build_default_modules(_repo_root: Path) -> list[ModuleSpec]:
    frontend_ci_env = {"CI": "1"}
    frontend_e2e_env = {"CI": "1", "PLAYWRIGHT_WORKERS": "1"}

    return [
        ModuleSpec(
            name="backend-emby-gateway-playback",
            category="backend",
            description="Emby gateway, playback hook, proxy routing, and stable stream contracts.",
            risk="high",
            optimization_lane="backend-runtime",
            ownership_paths=(
                "app/api/emby.py",
                "app/api/emby_gateway.py",
                "app/api/stable_stream.py",
                "app/services/playbackinfo_hook.py",
                "app/services/emby_proxy_service.py",
                "app/services/playback_decision_service.py",
                "tests/",
            ),
            command_plans=(
                pytest_plan(
                    "backend-emby-gateway-playback",
                    [
                        "tests/test_emby_gateway.py",
                        "tests/test_emby_invalid_host_port_contract.py",
                        "tests/test_emby_proxy_routing.py",
                        "tests/test_emby_proxy_service.py",
                        "tests/test_emby_api_client.py",
                        "tests/test_playback_decision_service.py",
                        "tests/test_stable_playback_hook.py",
                        "tests/test_stable_stream_route.py",
                        "tests/test_main_entrypoint.py",
                    ],
                    timeout_seconds=1800,
                ),
            ),
        ),
        ModuleSpec(
            name="backend-strm-pipeline",
            category="backend",
            description="STRM API, generation, validation, and media pipeline contracts.",
            risk="high",
            optimization_lane="backend-runtime",
            ownership_paths=(
                "app/api/strm.py",
                "app/api/strm_validator.py",
                "app/services/strm_service.py",
                "app/services/strm_generator.py",
                "app/services/strm_validator.py",
                "app/utils/strm_url.py",
                "tests/",
            ),
            command_plans=(
                pytest_plan(
                    "backend-strm-pipeline",
                    [
                        "tests/test_strm_api.py",
                        "tests/test_strm_service.py",
                        "tests/test_strm_generator.py",
                        "tests/test_strm_validator_service.py",
                        "tests/test_strm_validator_transfer_api.py",
                        "tests/test_media_strm_generator_extra.py",
                        "tests/test_media_files.py",
                    ],
                    timeout_seconds=1800,
                ),
            ),
        ),
        ModuleSpec(
            name="backend-auth-security-observability",
            category="backend",
            description="Auth, security headers, monitoring, metrics, and exception boundaries.",
            risk="high",
            optimization_lane="backend-runtime",
            ownership_paths=(
                "app/api/auth.py",
                "app/api/security.py",
                "app/api/monitoring.py",
                "app/api/prometheus.py",
                "app/core/",
                "tests/",
            ),
            command_plans=(
                pytest_plan(
                    "backend-auth-security-observability",
                    [
                        "tests/test_auth.py",
                        "tests/test_auth_api_endpoints.py",
                        "tests/test_auth_middleware.py",
                        "tests/test_csrf_middleware.py",
                        "tests/test_monitoring_api.py",
                        "tests/test_prometheus_api.py",
                        "tests/test_security_api.py",
                        "tests/test_security_api_filtering.py",
                        "tests/test_security_headers_middleware.py",
                        "tests/test_exception_handler.py",
                        "tests/test_error_handler_compat.py",
                        "tests/test_response.py",
                    ],
                    timeout_seconds=1800,
                ),
            ),
        ),
        ModuleSpec(
            name="backend-quark-storage-transfer",
            category="backend",
            description="Quark, cloud-drive, transfer, file-manager, and WebDAV integrations.",
            risk="high",
            optimization_lane="backend-runtime",
            ownership_paths=(
                "app/api/quark.py",
                "app/api/quark_sdk.py",
                "app/api/cloud_drive.py",
                "app/api/file_manager.py",
                "app/api/transfer.py",
                "app/services/",
                "tests/",
            ),
            command_plans=(
                pytest_plan(
                    "backend-quark-storage-transfer",
                    [
                        "tests/test_quark_api.py",
                        "tests/test_quark_api_client.py",
                        "tests/test_quark_sdk_api.py",
                        "tests/test_integrations_quark.py",
                        "tests/test_cloud_drive_api.py",
                        "tests/test_cloud_drive_service.py",
                        "tests/test_file_manager_api.py",
                        "tests/test_file_manager_service.py",
                        "tests/test_transfer_service.py",
                        "tests/test_webdav_modules.py",
                        "tests/test_webdav_fallback.py",
                        "tests/test_proxy_service.py",
                    ],
                    timeout_seconds=1800,
                ),
            ),
        ),
        ModuleSpec(
            name="backend-search-scrape-rename",
            category="backend",
            description="Search, scrape, rename, metadata scoring, and NFO generation.",
            risk="medium-high",
            optimization_lane="backend-runtime",
            ownership_paths=(
                "app/api/search.py",
                "app/api/scrape.py",
                "app/api/rename.py",
                "app/api/smart_rename.py",
                "app/services/media/",
                "app/services/scoring/",
                "tests/",
            ),
            command_plans=(
                pytest_plan(
                    "backend-search-scrape-rename",
                    [
                        "tests/test_search_api.py",
                        "tests/test_search_service.py",
                        "tests/test_scrape_api.py",
                        "tests/test_scoring_confidence.py",
                        "tests/test_scoring_engine.py",
                        "tests/test_scoring_freshness.py",
                        "tests/test_scoring_popularity.py",
                        "tests/test_scoring_quality.py",
                        "tests/test_scoring_tags.py",
                        "tests/test_nfo_generator.py",
                    ],
                    timeout_seconds=1800,
                ),
            ),
        ),
        ModuleSpec(
            name="backend-task-dashboard-config",
            category="backend",
            description="Dashboard, tasks, notifications, config, and runtime orchestration surfaces.",
            risk="medium-high",
            optimization_lane="backend-runtime",
            ownership_paths=(
                "app/api/dashboard.py",
                "app/api/tasks.py",
                "app/api/system_config.py",
                "app/services/platform/",
                "tests/",
            ),
            command_plans=(
                pytest_plan(
                    "backend-task-dashboard-config",
                    [
                        "tests/test_dashboard_api.py",
                        "tests/test_system_config_api.py",
                        "tests/test_cloud_drive_tasks_websocket.py",
                        "tests/test_task_queue_platform.py",
                        "tests/test_task_runner_platform.py",
                        "tests/test_task_scheduler_platform.py",
                        "tests/test_notification_api.py",
                        "tests/test_notification_service.py",
                        "tests/test_token_monitor.py",
                    ],
                    timeout_seconds=1800,
                ),
            ),
        ),
        ModuleSpec(
            name="frontend-shell-auth-startup",
            category="frontend",
            description="App-shell, auth, router, and startup contracts.",
            risk="high",
            optimization_lane="frontend-web",
            ownership_paths=(
                "web/src/features/app-shell/",
                "web/src/features/auth/",
                "web/src/router/",
                "web/src/stores/",
                "web/src/smoke.spec.ts",
            ),
            command_plans=(
                vitest_files_plan(
                    "frontend-shell-auth-unit",
                    [
                        "src/router/index.spec.ts",
                        "src/stores/auth.spec.ts",
                        "src/features/app-shell/views/LayoutView.spec.ts",
                        "src/features/auth/views/LoginView.spec.ts",
                    ],
                    base_args=["--reporter=dot"],
                    timeout_seconds=1200,
                    env_overrides=frontend_ci_env,
                ),
                command_plan(
                    "frontend-shell-auth-smoke",
                    ["pnpm", "run", "test:smoke", "--", "--reporter=dot"],
                    cwd="web",
                    timeout_seconds=1200,
                    env_overrides=frontend_ci_env,
                ),
            ),
        ),
        ModuleSpec(
            name="frontend-dashboard-tasks",
            category="frontend",
            description="Dashboard CTA flows and tasks workbench continuity.",
            risk="high",
            optimization_lane="frontend-web",
            ownership_paths=(
                "web/src/features/dashboard/",
                "web/src/features/tasks/",
                "web/e2e/dashboard.spec.ts",
                "web/e2e/tasks.spec.ts",
            ),
            command_plans=(
                pnpm_files_plan(
                    "frontend-dashboard-tasks",
                    "test:e2e",
                    [
                        "e2e/dashboard.spec.ts",
                        "e2e/tasks.spec.ts",
                    ],
                    base_args=["--project", "chromium"],
                    timeout_seconds=1800,
                    env_overrides=frontend_e2e_env,
                ),
            ),
        ),
        ModuleSpec(
            name="frontend-search-rename-scrape",
            category="frontend",
            description="Search, rename, smart-rename, and scrape workflows.",
            risk="high",
            optimization_lane="frontend-web",
            ownership_paths=(
                "web/src/features/search/",
                "web/src/features/rename/",
                "web/src/features/smart-rename/",
                "web/src/features/scrape/",
                "web/e2e/",
            ),
            command_plans=(
                pnpm_files_plan(
                    "frontend-search-rename-scrape",
                    "test:e2e",
                    [
                        "e2e/search.spec.ts",
                        "e2e/rename.spec.ts",
                        "e2e/smart-rename.spec.ts",
                        "e2e/scrape-paths.spec.ts",
                        "e2e/scrape-records.spec.ts",
                    ],
                    base_args=["--project", "chromium"],
                    timeout_seconds=2400,
                    env_overrides=frontend_e2e_env,
                ),
            ),
        ),
        ModuleSpec(
            name="frontend-config-admin-surfaces",
            category="frontend",
            description="Config, notifications, proxy, Emby, WebDAV, and file-manager views.",
            risk="medium-high",
            optimization_lane="frontend-web",
            ownership_paths=(
                "web/src/features/config/",
                "web/src/features/notifications/",
                "web/src/features/proxy/",
                "web/src/features/emby/",
                "web/src/features/webdav/",
                "web/src/features/file-manager/",
            ),
            command_plans=(
                vitest_files_plan(
                    "frontend-config-admin-surfaces",
                    [
                        "src/features/config/views/ConfigView.spec.ts",
                        "src/features/notifications/views/NotificationsView.spec.ts",
                        "src/features/notifications/views/NotificationHistoryView.spec.ts",
                        "src/features/proxy/views/ProxyServiceView.spec.ts",
                        "src/features/emby/views/EmbyMonitorView.spec.ts",
                        "src/features/webdav/views/WebDAVView.spec.ts",
                        "src/features/file-manager/components/FileGrid.spec.ts",
                        "src/features/category-strategy/views/CategoryStrategyView.spec.ts",
                    ],
                    base_args=["--reporter=dot"],
                    timeout_seconds=1800,
                    env_overrides=frontend_ci_env,
                ),
            ),
        ),
        ModuleSpec(
            name="contracts-runtime-probes-docs",
            category="contracts",
            description="Runtime entrypoint, probes, lifecycle, and API docs alignment.",
            risk="high",
            optimization_lane="repo-contracts",
            ownership_paths=(
                "app/main.py",
                "app/config/",
                "docs/",
                "tests/",
            ),
            command_plans=(
                pytest_plan(
                    "contracts-runtime-probes-docs",
                    [
                        "tests/test_main_entrypoint.py",
                        "tests/test_api_docs_contract.py",
                        "tests/test_lifecycle.py",
                        "tests/test_api_v1_routes.py",
                    ],
                    timeout_seconds=1800,
                ),
            ),
        ),
        ModuleSpec(
            name="contracts-docker-compose-ci",
            category="contracts",
            description="Docker, workflow, packaging, and test-runtime contracts.",
            risk="high",
            optimization_lane="repo-contracts",
            ownership_paths=(
                "Dockerfile",
                "docker-compose.yml",
                ".github/workflows/",
                "pyproject.toml",
                "README.md",
                "tests/",
            ),
            command_plans=(
                pytest_plan(
                    "contracts-docker-compose-ci",
                    [
                        "tests/test_deployment_contract.py",
                        "tests/test_ci_workflow.py",
                        "tests/test_pyproject_packaging_contract.py",
                        "tests/test_pytest_workflow_coverage_gate.py",
                        "tests/test_pytest_runtime_contract.py",
                    ],
                    timeout_seconds=1800,
                ),
            ),
        ),
        ModuleSpec(
            name="contracts-frontend-build-startup",
            category="contracts",
            description="Frontend lint, type-check, smoke, and build chain.",
            risk="high",
            optimization_lane="repo-contracts",
            ownership_paths=(
                "web/package.json",
                "web/src/smoke.spec.ts",
                "web/playwright.config.ts",
                "web/",
            ),
            command_plans=(
                command_plan(
                    "frontend-lint-fix",
                    ["pnpm", "run", "lint", "--fix"],
                    cwd="web",
                    timeout_seconds=1800,
                    env_overrides=frontend_ci_env,
                ),
                command_plan(
                    "frontend-type-check",
                    ["pnpm", "run", "type-check"],
                    cwd="web",
                    timeout_seconds=1800,
                    env_overrides=frontend_ci_env,
                ),
                command_plan(
                    "frontend-smoke",
                    ["pnpm", "run", "test:smoke", "--", "--reporter=dot"],
                    cwd="web",
                    timeout_seconds=1200,
                    env_overrides=frontend_ci_env,
                ),
                command_plan(
                    "frontend-build-only",
                    ["pnpm", "run", "build-only"],
                    cwd="web",
                    timeout_seconds=1800,
                    env_overrides=frontend_ci_env,
                ),
            ),
        ),
        ModuleSpec(
            name="contracts-frontend-e2e-startup",
            category="contracts",
            description="Playwright startup contract for backend/frontend auto-start and login flow.",
            risk="high",
            optimization_lane="frontend-web",
            ownership_paths=(
                "web/playwright.config.ts",
                "web/src/playwright.config.spec.ts",
                "web/e2e/login.spec.ts",
                "web/e2e/not-found.spec.ts",
            ),
            command_plans=(
                pnpm_files_plan(
                    "contracts-frontend-e2e-startup",
                    "test:e2e",
                    [
                        "e2e/login.spec.ts",
                        "e2e/not-found.spec.ts",
                    ],
                    base_args=["--project", "chromium"],
                    timeout_seconds=1800,
                    env_overrides=frontend_e2e_env,
                ),
            ),
        ),
    ]


def materialize_command(plan: CommandPlan, repo_root: Path) -> MaterializedCommand:
    env_overrides = dict(plan.env_overrides)
    cwd = (repo_root / plan.cwd).resolve()
    if plan.runner == "command":
        return MaterializedCommand(
            name=plan.name,
            cwd=cwd,
            command=plan.command,
            timeout_seconds=plan.timeout_seconds,
            env_overrides=env_overrides,
        )
    if plan.runner == "pytest":
        targets = resolve_glob_targets(repo_root / plan.target_root, plan.target_patterns)
        if not targets:
            return MaterializedCommand(
                name=plan.name,
                cwd=cwd,
                command=(),
                timeout_seconds=plan.timeout_seconds,
                env_overrides=env_overrides,
                skipped_reason="no matching pytest targets",
            )
        command = (str(resolve_python_command(repo_root)), "-m", "pytest", *targets, *plan.base_args)
        return MaterializedCommand(
            name=plan.name,
            cwd=cwd,
            command=command,
            timeout_seconds=plan.timeout_seconds,
            env_overrides=env_overrides,
        )
    if plan.runner == "pnpm-files":
        targets = resolve_glob_targets(repo_root / plan.target_root, plan.target_patterns)
        if not targets:
            return MaterializedCommand(
                name=plan.name,
                cwd=cwd,
                command=(),
                timeout_seconds=plan.timeout_seconds,
                env_overrides=env_overrides,
                skipped_reason="no matching frontend targets",
            )
        command = ("pnpm", "run", plan.script, "--", *plan.base_args, *targets)
        return MaterializedCommand(
            name=plan.name,
            cwd=cwd,
            command=command,
            timeout_seconds=plan.timeout_seconds,
            env_overrides=env_overrides,
        )
    if plan.runner == "vitest-files":
        targets = resolve_glob_targets(repo_root / plan.target_root, plan.target_patterns)
        if not targets:
            return MaterializedCommand(
                name=plan.name,
                cwd=cwd,
                command=(),
                timeout_seconds=plan.timeout_seconds,
                env_overrides=env_overrides,
                skipped_reason="no matching frontend targets",
            )
        command = ("pnpm", "exec", "vitest", "run", *plan.base_args, *targets)
        return MaterializedCommand(
            name=plan.name,
            cwd=cwd,
            command=command,
            timeout_seconds=plan.timeout_seconds,
            env_overrides=env_overrides,
        )
    raise ValueError(f"unsupported command runner: {plan.runner}")


def run_materialized_command(command: MaterializedCommand, log_path: Path) -> dict[str, Any]:
    if command.skipped_reason:
        return {
            "name": command.name,
            "status": "skipped",
            "command": [],
            "cwd": str(command.cwd),
            "timeout_seconds": command.timeout_seconds,
            "log_path": str(log_path),
            "log_tail": command.skipped_reason,
            "return_code": None,
            "duration_seconds": 0.0,
            "started_at": iso_utc(utc_now()),
            "ended_at": iso_utc(utc_now()),
            "error": None,
        }

    ensure_directory(log_path.parent)
    started = utc_now()
    timeout_hit = False
    error: str | None = None
    return_code = 0
    output = ""
    env = os.environ.copy()
    env.update(command.env_overrides)
    runtime_command = resolve_runtime_command(command.command)
    try:
        completed = subprocess.run(
            runtime_command,
            cwd=str(command.cwd),
            env=env,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=command.timeout_seconds,
            check=False,
        )
        return_code = completed.returncode
        output = f"{completed.stdout}\n{completed.stderr}".strip()
    except subprocess.TimeoutExpired as exc:
        timeout_hit = True
        return_code = 124
        output = f"{exc.stdout or ''}\n{exc.stderr or ''}\n[timeout] command exceeded {command.timeout_seconds}s".strip()
    except OSError as exc:
        return_code = 127
        error = f"{exc.__class__.__name__}: {exc}"
        output = f"[exec-error] {error}"

    ended = utc_now()
    write_text(log_path, f"$ {quote_command(runtime_command)}\n\n{output}\n")
    if error:
        status = "failed"
    elif timeout_hit:
        status = "failed"
    elif return_code == 0:
        status = "passed"
    else:
        status = "failed"
    return {
        "name": command.name,
        "status": status,
        "command": runtime_command,
        "cwd": str(command.cwd),
        "timeout_seconds": command.timeout_seconds,
        "log_path": str(log_path),
        "log_tail": "\n".join(output.splitlines()[-80:]),
        "return_code": return_code,
        "duration_seconds": round((ended - started).total_seconds(), 3),
        "started_at": iso_utc(started),
        "ended_at": iso_utc(ended),
        "error": error,
    }


def summarize_module_status(commands: list[dict[str, Any]]) -> str:
    active = [result for result in commands if result["status"] != "skipped"]
    if not active:
        return "skipped"
    if all(result["status"] == "passed" for result in active):
        return "passed"
    return "failed"


def run_module(
    module: ModuleSpec,
    repo_root: Path,
    iteration_dir: Path,
    phase: str,
    *,
    command_names: set[str] | None = None,
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for index, plan in enumerate(module.command_plans, start=1):
        if command_names is not None and plan.name not in command_names:
            continue
        materialized = materialize_command(plan, repo_root)
        log_path = iteration_dir / "logs" / f"{phase}-{slugify(module.name)}-{index:02d}-{slugify(plan.name)}.log"
        results.append(run_materialized_command(materialized, log_path))

    return {
        "name": module.name,
        "category": module.category,
        "description": module.description,
        "risk": module.risk,
        "optimization_lane": module.optimization_lane,
        "ownership_paths": list(module.ownership_paths),
        "status": summarize_module_status(results),
        "commands": results,
    }


def collect_git_state(repo_root: Path) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            ["git", "status", "--short"],
            cwd=str(repo_root),
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
        )
    except OSError as exc:
        return {"available": False, "error": f"{exc.__class__.__name__}: {exc}", "dirty_count": None, "sample": []}

    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    return {
        "available": completed.returncode == 0,
        "error": None if completed.returncode == 0 else completed.stderr.strip() or "git status failed",
        "dirty_count": len(lines) if completed.returncode == 0 else None,
        "sample": lines[:40],
    }


def build_codex_exec_command(
    *,
    repo_root: Path,
    model: str,
    prompt: str,
    output_message_path: Path,
    unsafe_bypass_sandbox: bool,
) -> list[str]:
    command = ["codex", "exec"]
    if unsafe_bypass_sandbox:
        command.append("--dangerously-bypass-approvals-and-sandbox")
    else:
        command.append("--full-auto")
    command.extend(
        [
            "-m",
            model,
            "-C",
            str(repo_root),
            "-o",
            str(output_message_path),
            prompt,
        ]
    )
    return command


def build_agent_prompt(repo_root: Path, lane_name: str, failures: list[dict[str, Any]]) -> str:
    lines = [
        "你是 quark_strm 的持续优化 worker。",
        f"仓库根目录: {repo_root}",
        f"优化 lane: {lane_name}",
        "要求：",
        "- 当前 git 工作树很脏，不要回退、覆盖或整理无关改动。",
        "- 只在本 lane 负责路径内做最小必要修改。",
        "- 先根据失败命令和日志定位根因，再做修复。",
        "- 修复后重新运行对应失败命令，确认通过。",
        "- 不要扩 scope，不要新增不必要配置。",
        "",
        "失败模块：",
    ]
    for failure in failures:
        lines.append(f"- 模块: {failure['name']} ({failure['risk']})")
        lines.append(f"  描述: {failure['description']}")
        lines.append(f"  负责路径: {', '.join(failure['ownership_paths'])}")
        for command in failure["commands"]:
            if command["status"] != "failed":
                continue
            lines.append(f"  失败命令: {quote_command(command['command'])}")
            if command["log_tail"]:
                lines.append("  日志尾部:")
                for line in command["log_tail"].splitlines()[-40:]:
                    lines.append(f"    {line}")
        lines.append("")
    return "\n".join(lines).strip()


def run_agent_lane(
    lane_name: str,
    failures: list[dict[str, Any]],
    repo_root: Path,
    iteration_dir: Path,
    *,
    model: str,
    unsafe_bypass_sandbox: bool,
    timeout_seconds: int,
) -> dict[str, Any]:
    prompt = build_agent_prompt(repo_root, lane_name, failures)
    prompt_path = iteration_dir / "prompts" / f"{slugify(lane_name)}.md"
    output_message_path = iteration_dir / "agents" / f"{slugify(lane_name)}-last-message.txt"
    log_path = iteration_dir / "logs" / f"agent-{slugify(lane_name)}.log"
    write_text(prompt_path, prompt)

    command = build_codex_exec_command(
        repo_root=repo_root,
        model=model,
        prompt=prompt,
        output_message_path=output_message_path,
        unsafe_bypass_sandbox=unsafe_bypass_sandbox,
    )
    result = run_materialized_command(
        MaterializedCommand(
            name=f"agent-{lane_name}",
            cwd=repo_root,
            command=tuple(command),
            timeout_seconds=timeout_seconds,
            env_overrides={},
        ),
        log_path,
    )
    last_message = ""
    if output_message_path.exists():
        last_message = output_message_path.read_text(encoding="utf-8", errors="replace").strip()
    return {
        "lane": lane_name,
        "status": result["status"],
        "failures": [failure["name"] for failure in failures],
        "prompt_path": str(prompt_path),
        "output_message_path": str(output_message_path),
        "summary": last_message,
        "execution": result,
    }


def build_failure_lanes(module_results: list[dict[str, Any]]) -> list[tuple[str, list[dict[str, Any]]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for result in module_results:
        if result["status"] != "failed":
            continue
        grouped.setdefault(result["optimization_lane"], []).append(result)
    return sorted(grouped.items(), key=lambda item: item[0])


def failed_command_names(module_result: dict[str, Any]) -> set[str]:
    return {command["name"] for command in module_result["commands"] if command["status"] == "failed"}


def merge_command_results(
    baseline_commands: list[dict[str, Any]],
    verification_commands: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    # Keep the baseline failure visible if a targeted verify rerun no longer has a runnable command.
    replacements = {
        command["name"]: command
        for command in verification_commands
        if command["status"] != "skipped"
    }
    baseline_names = {command["name"] for command in baseline_commands}
    merged = [replacements.get(command["name"], command) for command in baseline_commands]
    merged.extend(
        command
        for command in verification_commands
        if command["status"] != "skipped" and command["name"] not in baseline_names
    )
    return merged


def merge_module_results(
    baseline_results: list[dict[str, Any]],
    verification_results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    replacements = {result["name"]: result for result in verification_results}
    merged: list[dict[str, Any]] = []
    for result in baseline_results:
        verification = replacements.get(result["name"])
        if verification is None:
            merged.append(result)
            continue
        commands = merge_command_results(result["commands"], verification["commands"])
        merged.append({**result, "status": summarize_module_status(commands), "commands": commands})
    return merged


def build_module_inventory(modules: list[ModuleSpec], repo_root: Path) -> list[dict[str, Any]]:
    inventory: list[dict[str, Any]] = []
    for module in modules:
        commands: list[dict[str, Any]] = []
        for plan in module.command_plans:
            materialized = materialize_command(plan, repo_root)
            commands.append(
                {
                    "name": plan.name,
                    "runner": plan.runner,
                    "cwd": plan.cwd,
                    "target_patterns": list(plan.target_patterns),
                    "command_preview": list(materialized.command),
                    "skipped_reason": materialized.skipped_reason,
                }
            )
        inventory.append(
            {
                "name": module.name,
                "category": module.category,
                "description": module.description,
                "risk": module.risk,
                "optimization_lane": module.optimization_lane,
                "ownership_paths": list(module.ownership_paths),
                "commands": commands,
            }
        )
    return inventory


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# quark_strm Continuous Optimization Report",
        "",
        f"- Iteration: {report['iteration']}",
        f"- Started At: {report['started_at']}",
        f"- Ended At: {report['ended_at']}",
        f"- Agent Model: {report['agent_model']}",
        f"- Stop File: `{report['stop_file']}`",
        f"- Dirty Files: {report['git_state']['dirty_count']}",
        f"- Final Issue Count: {report['issue_count']}",
        "",
        "## Modules",
    ]
    for module in report["modules"]:
        lines.append(f"- `{module['name']}`: {module['status']} ({module['risk']})")
        for command in module["commands"]:
            status = command["status"]
            rendered = quote_command(command["command"]) if command["command"] else command["log_tail"]
            lines.append(f"  - `{command['name']}`: {status}")
            lines.append(f"    - `{rendered}`")
    lines.append("")
    lines.append("## Agents")
    if not report["agents"]:
        lines.append("- No agent optimization run in this iteration.")
    else:
        for agent in report["agents"]:
            lines.append(f"- `{agent['lane']}`: {agent['status']} ({', '.join(agent['failures'])})")
            if agent["summary"]:
                lines.append(f"  - Summary: {agent['summary']}")
    return "\n".join(lines) + "\n"


def write_report_files(report_dir: Path, iteration_slug: str, report: dict[str, Any]) -> None:
    latest_json = report_dir / "latest.json"
    latest_md = report_dir / "latest.md"
    iteration_json = report_dir / "iterations" / f"{iteration_slug}.json"
    iteration_md = report_dir / "iterations" / f"{iteration_slug}.md"
    write_json(latest_json, report)
    write_json(iteration_json, report)
    markdown = render_markdown(report)
    write_text(latest_md, markdown)
    write_text(iteration_md, markdown)


def select_modules(modules: list[ModuleSpec], selected_names: list[str] | None) -> list[ModuleSpec]:
    if not selected_names:
        return modules
    known = {module.name: module for module in modules}
    missing = [name for name in selected_names if name not in known]
    if missing:
        raise ValueError(f"--module contains unknown modules: {', '.join(missing)}")
    return [known[name] for name in selected_names]


def run_iteration(
    *,
    iteration: int,
    modules: list[ModuleSpec],
    repo_root: Path,
    report_dir: Path,
    stop_file: Path,
    model: str,
    skip_agent_optimize: bool,
    unsafe_bypass_sandbox: bool,
    max_parallel_agents: int,
    agent_timeout_seconds: int,
) -> dict[str, Any]:
    started = utc_now()
    iteration_slug = f"{started:%Y%m%dT%H%M%SZ}-iter-{iteration:04d}"
    iteration_dir = report_dir / "iterations" / iteration_slug
    ensure_directory(iteration_dir)

    baseline_results = [run_module(module, repo_root, iteration_dir, "baseline") for module in modules]
    agents: list[dict[str, Any]] = []
    verification_results: list[dict[str, Any]] = []
    failure_lanes = build_failure_lanes(baseline_results)

    if failure_lanes and not skip_agent_optimize:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_parallel_agents) as executor:
            futures = [
                executor.submit(
                    run_agent_lane,
                    lane_name,
                    failures,
                    repo_root,
                    iteration_dir,
                    model=model,
                    unsafe_bypass_sandbox=unsafe_bypass_sandbox,
                    timeout_seconds=agent_timeout_seconds,
                )
                for lane_name, failures in failure_lanes
            ]
            for future in concurrent.futures.as_completed(futures):
                agents.append(future.result())

        verification_targets = {
            failure["name"]: failed_command_names(failure)
            for _, failures in failure_lanes
            for failure in failures
        }
        verification_results = [
            run_module(module, repo_root, iteration_dir, "verify", command_names=verification_targets[module.name])
            for module in modules
            if module.name in verification_targets
        ]

    final_results = merge_module_results(baseline_results, verification_results)
    ended = utc_now()
    report = {
        "iteration": iteration,
        "started_at": iso_utc(started),
        "ended_at": iso_utc(ended),
        "duration_seconds": round((ended - started).total_seconds(), 3),
        "agent_model": model,
        "repo_root": str(repo_root),
        "report_dir": str(report_dir),
        "stop_file": str(stop_file),
        "git_state": collect_git_state(repo_root),
        "modules": final_results,
        "baseline_modules": baseline_results,
        "verification_modules": verification_results,
        "agents": sorted(agents, key=lambda item: item["lane"]),
        "issue_count": sum(1 for result in final_results if result["status"] == "failed"),
        "module_inventory": build_module_inventory(modules, repo_root),
    }
    write_report_files(report_dir, iteration_slug, report)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Continuously run quark_strm module tests and dispatch Codex optimization lanes in parallel."
        )
    )
    parser.add_argument("--repo-root", type=Path, default=Path.cwd(), help="quark_strm repository root")
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR, help="report output directory")
    parser.add_argument("--stop-file", type=Path, default=None, help="stop file path")
    parser.add_argument("--max-iterations", type=int, default=0, help="0 means run until stopped")
    parser.add_argument("--interval-seconds", type=int, default=DEFAULT_INTERVAL_SECONDS, help="sleep between iterations")
    parser.add_argument("--module", action="append", dest="modules", help="run only selected module (repeatable)")
    parser.add_argument("--model", default=DEFAULT_AGENT_MODEL, help="Codex model for optimization agents")
    parser.add_argument(
        "--max-parallel-agents",
        type=int,
        default=DEFAULT_MAX_PARALLEL_AGENTS,
        help="maximum optimization lanes to run in parallel",
    )
    parser.add_argument(
        "--agent-timeout-seconds",
        type=int,
        default=3600,
        help="timeout for a single codex optimization lane",
    )
    parser.add_argument("--skip-agent-optimize", action="store_true", help="observe-only loop without codex edits")
    parser.add_argument(
        "--unsafe-bypass-sandbox",
        action="store_true",
        help="pass --dangerously-bypass-approvals-and-sandbox to codex exec",
    )
    parser.add_argument("--list-modules", action="store_true", help="print module inventory and exit")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        repo_root = resolve_repo_root(args.repo_root)
        report_dir = resolve_report_dir(repo_root, args.report_dir)
        stop_file = resolve_stop_file(repo_root, report_dir, args.stop_file)
        modules = select_modules(build_default_modules(repo_root), args.modules)
    except (FileNotFoundError, NotADirectoryError, ValueError) as exc:
        print(f"[loop-error] {exc}", file=sys.stderr)
        return 2

    ensure_directory(report_dir)
    write_json(report_dir / "module-inventory.json", build_module_inventory(modules, repo_root))

    if args.list_modules:
        print(json.dumps(build_module_inventory(modules, repo_root), ensure_ascii=False, indent=2))
        return 0

    iteration = 0
    while True:
        if stop_file.exists():
            print(f"[loop] stop file detected before iteration start: {stop_file}")
            return 0

        iteration += 1
        report = run_iteration(
            iteration=iteration,
            modules=modules,
            repo_root=repo_root,
            report_dir=report_dir,
            stop_file=stop_file,
            model=args.model,
            skip_agent_optimize=args.skip_agent_optimize,
            unsafe_bypass_sandbox=args.unsafe_bypass_sandbox,
            max_parallel_agents=max(args.max_parallel_agents, 1),
            agent_timeout_seconds=max(args.agent_timeout_seconds, 60),
        )
        print(
            f"[loop] iteration={iteration} issues={report['issue_count']} "
            f"agents={len(report['agents'])} report={report_dir / 'latest.md'}"
        )

        if args.max_iterations and iteration >= args.max_iterations:
            return 0
        if stop_file.exists():
            print(f"[loop] stop file detected after iteration: {stop_file}")
            return 0
        if args.interval_seconds <= 0:
            continue
        time.sleep(args.interval_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
