from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "continuous_optimize.py"


def load_module():
    spec = importlib.util.spec_from_file_location("continuous_optimize", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_default_modules_cover_backend_frontend_and_contract_lanes() -> None:
    module = load_module()

    module_specs = module.build_default_modules(Path("D:/repo"))

    assert [spec.name for spec in module_specs] == [
        "backend-emby-gateway-playback",
        "backend-strm-pipeline",
        "backend-auth-security-observability",
        "backend-quark-storage-transfer",
        "backend-search-scrape-rename",
        "backend-task-dashboard-config",
        "frontend-shell-auth-startup",
        "frontend-dashboard-tasks",
        "frontend-search-rename-scrape",
        "frontend-config-admin-surfaces",
        "contracts-runtime-probes-docs",
        "contracts-docker-compose-ci",
        "contracts-frontend-build-startup",
        "contracts-frontend-e2e-startup",
    ]
    assert module_specs[0].optimization_lane == "backend-runtime"
    assert module_specs[6].optimization_lane == "frontend-web"
    assert module_specs[-1].optimization_lane == "frontend-web"
    assert module_specs[-3].optimization_lane == "repo-contracts"


def test_default_agent_model_matches_project_goal() -> None:
    module = load_module()

    assert module.DEFAULT_AGENT_MODEL == "gpt-5.5"


def test_resolve_glob_targets_deduplicates_in_order(tmp_path: Path) -> None:
    module = load_module()

    (tmp_path / "tests").mkdir()
    for name in ("test_alpha.py", "test_beta.py", "test_gamma.py"):
        (tmp_path / "tests" / name).write_text("# test\n", encoding="utf-8")

    resolved = module.resolve_glob_targets(
        tmp_path,
        [
            "tests/test_alpha.py",
            "tests/test_*.py",
            "tests/test_beta.py",
        ],
    )

    assert resolved == [
        "tests/test_alpha.py",
        "tests/test_beta.py",
        "tests/test_gamma.py",
    ]


def test_build_codex_exec_command_uses_requested_model_and_full_auto_by_default(tmp_path: Path) -> None:
    module = load_module()

    command = module.build_codex_exec_command(
        repo_root=tmp_path,
        model="gpt-5.5",
        prompt="fix failing module",
        output_message_path=tmp_path / "agent-last-message.txt",
        unsafe_bypass_sandbox=False,
    )

    assert command[:4] == ["codex", "exec", "--full-auto", "-m"]
    assert "gpt-5.5" in command
    assert "-C" in command
    assert str(tmp_path) in command
    assert "-o" in command
    assert str(tmp_path / "agent-last-message.txt") in command
    assert command[-1] == "fix failing module"


def test_resolve_runtime_executable_prefers_cmd_wrappers_on_windows(monkeypatch) -> None:
    module = load_module()

    monkeypatch.setattr(module.os, "name", "nt", raising=False)
    monkeypatch.setattr(
        module.shutil,
        "which",
        lambda name: {
            "pnpm.cmd": r"C:\Users\example\AppData\Roaming\npm\pnpm.cmd",
            "pnpm": r"C:\Users\example\AppData\Roaming\npm\pnpm",
        }.get(name),
    )

    assert module.resolve_runtime_executable("pnpm") == r"C:\Users\example\AppData\Roaming\npm\pnpm.cmd"


def test_parse_args_supports_observe_only_inventory_and_module_filter(monkeypatch) -> None:
    module = load_module()

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "continuous_optimize.py",
            "--repo-root",
            "D:/repo",
            "--report-dir",
            "target/custom",
            "--module",
            "contracts-runtime-probes-docs",
            "--module",
            "frontend-shell-auth-startup",
            "--max-iterations",
            "1",
            "--interval-seconds",
            "0",
            "--skip-agent-optimize",
            "--list-modules",
        ],
    )

    args = module.parse_args()

    assert args.repo_root == Path("D:/repo")
    assert args.report_dir == Path("target/custom")
    assert args.modules == ["contracts-runtime-probes-docs", "frontend-shell-auth-startup"]
    assert args.max_iterations == 1
    assert args.interval_seconds == 0
    assert args.model == module.DEFAULT_AGENT_MODEL
    assert args.skip_agent_optimize is True
    assert args.list_modules is True


def test_default_report_dir_and_stop_file_resolve_under_repo_root(tmp_path: Path) -> None:
    module = load_module()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    report_dir = module.resolve_report_dir(repo_root, module.DEFAULT_REPORT_DIR)

    assert report_dir == (repo_root / "target" / "continuous").resolve()
    assert module.resolve_stop_file(repo_root, report_dir, None) == (
        repo_root / "target" / "continuous" / module.STOP_FILE_NAME
    ).resolve()
    assert module.resolve_stop_file(repo_root, report_dir, Path("tmp/STOP")) == (repo_root / "tmp" / "STOP").resolve()


def test_materialize_command_marks_missing_targets_as_skipped(tmp_path: Path) -> None:
    module = load_module()
    repo_root = tmp_path / "repo"
    (repo_root / "web").mkdir(parents=True)

    pytest_command = module.materialize_command(
        module.pytest_plan("missing-pytest", ["tests/test_missing.py"]),
        repo_root,
    )
    frontend_command = module.materialize_command(
        module.pnpm_files_plan("missing-frontend", "test:run", ["src/missing.spec.ts"]),
        repo_root,
    )

    assert pytest_command.command == ()
    assert pytest_command.skipped_reason == "no matching pytest targets"
    assert frontend_command.command == ()
    assert frontend_command.skipped_reason == "no matching frontend targets"


def test_run_module_returns_skipped_when_every_command_is_skipped(tmp_path: Path) -> None:
    module = load_module()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    iteration_dir = tmp_path / "report"
    module_spec = module.ModuleSpec(
        name="skipped-contract-lane",
        category="contracts",
        description="skip propagation",
        risk="low",
        optimization_lane="repo-contracts",
        ownership_paths=("tests/",),
        command_plans=(module.pytest_plan("missing-pytest", ["tests/test_missing.py"]),),
    )

    result = module.run_module(module_spec, repo_root, iteration_dir, "baseline")

    assert result["status"] == "skipped"
    assert result["commands"][0]["status"] == "skipped"
    assert result["commands"][0]["log_tail"] == "no matching pytest targets"


def test_write_report_files_emits_latest_and_iteration_reports(tmp_path: Path) -> None:
    module = load_module()
    report = {
        "iteration": 1,
        "started_at": "2026-04-20T00:00:00Z",
        "ended_at": "2026-04-20T00:00:03Z",
        "agent_model": "gpt-5.5",
        "stop_file": "target/continuous/STOP_CONTINUOUS_LOOP",
        "git_state": {"dirty_count": 7},
        "issue_count": 1,
        "modules": [
            {
                "name": "contracts-runtime-probes-docs",
                "status": "failed",
                "risk": "high",
                "commands": [
                    {
                        "name": "contracts-runtime-probes-docs",
                        "status": "failed",
                        "command": ["python", "-m", "pytest", "tests/test_main_entrypoint.py"],
                        "log_tail": "failure tail",
                    }
                ],
            }
        ],
        "agents": [
            {
                "lane": "repo-contracts",
                "status": "passed",
                "failures": ["contracts-runtime-probes-docs"],
                "summary": "fixed the failing lane",
            }
        ],
    }

    module.write_report_files(tmp_path, "20260420T000000Z-iter-0001", report)

    latest_json = tmp_path / "latest.json"
    latest_md = tmp_path / "latest.md"
    iteration_json = tmp_path / "iterations" / "20260420T000000Z-iter-0001.json"
    iteration_md = tmp_path / "iterations" / "20260420T000000Z-iter-0001.md"

    assert latest_json.exists()
    assert latest_md.exists()
    assert iteration_json.exists()
    assert iteration_md.exists()
    assert json.loads(latest_json.read_text(encoding="utf-8")) == report
    assert json.loads(iteration_json.read_text(encoding="utf-8")) == report

    markdown = latest_md.read_text(encoding="utf-8")
    assert "# quark_strm Continuous Optimization Report" in markdown
    assert "- Final Issue Count: 1" in markdown
    assert "- `contracts-runtime-probes-docs`: failed (high)" in markdown
    assert "Summary: fixed the failing lane" in markdown
