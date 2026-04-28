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
    assert (
        module.resolve_stop_file(repo_root, report_dir, None)
        == (repo_root / "target" / "continuous" / module.STOP_FILE_NAME).resolve()
    )
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


def test_materialize_vitest_files_plan_uses_direct_vitest_without_separator(tmp_path: Path) -> None:
    module = load_module()
    repo_root = tmp_path / "repo"
    target = repo_root / "web" / "src" / "router" / "index.spec.ts"
    target.parent.mkdir(parents=True)
    target.write_text("test", encoding="utf-8")

    command = module.materialize_command(
        module.vitest_files_plan(
            "frontend-shell-auth-unit",
            ["src/router/index.spec.ts"],
            base_args=["--reporter=dot"],
        ),
        repo_root,
    )

    assert command.command == (
        "pnpm",
        "exec",
        "vitest",
        "run",
        "--reporter=dot",
        "src/router/index.spec.ts",
    )
    assert "--" not in command.command


def test_default_frontend_unit_lanes_use_direct_vitest_runner() -> None:
    module = load_module()

    module_specs = module.build_default_modules(Path("D:/repo"))

    shell_auth = next(spec for spec in module_specs if spec.name == "frontend-shell-auth-startup")
    config_admin = next(spec for spec in module_specs if spec.name == "frontend-config-admin-surfaces")

    assert shell_auth.command_plans[0].runner == "vitest-files"
    assert config_admin.command_plans[0].runner == "vitest-files"


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


def test_run_module_can_target_specific_commands(tmp_path: Path, monkeypatch) -> None:
    module = load_module()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    iteration_dir = tmp_path / "report"
    module_spec = module.ModuleSpec(
        name="targeted-verify-lane",
        category="contracts",
        description="target command filtering",
        risk="medium",
        optimization_lane="repo-contracts",
        ownership_paths=("tests/",),
        command_plans=(
            module.command_plan("baseline-pass", ["echo", "pass"]),
            module.command_plan("baseline-fail", ["echo", "fail"]),
        ),
    )
    executed: list[str] = []

    def fake_materialize(plan, _repo_root):
        return module.MaterializedCommand(
            name=plan.name,
            cwd=_repo_root,
            command=(plan.name,),
            timeout_seconds=plan.timeout_seconds,
            env_overrides={},
        )

    def fake_run(command, log_path):
        executed.append(command.name)
        return {
            "name": command.name,
            "status": "passed",
            "command": list(command.command),
            "cwd": str(command.cwd),
            "timeout_seconds": command.timeout_seconds,
            "log_path": str(log_path),
            "log_tail": "",
            "return_code": 0,
            "duration_seconds": 0.01,
            "started_at": "2026-04-25T00:00:00Z",
            "ended_at": "2026-04-25T00:00:00Z",
            "error": None,
        }

    monkeypatch.setattr(module, "materialize_command", fake_materialize)
    monkeypatch.setattr(module, "run_materialized_command", fake_run)

    result = module.run_module(
        module_spec,
        repo_root,
        iteration_dir,
        "verify",
        command_names={"baseline-fail"},
    )

    assert executed == ["baseline-fail"]
    assert result["status"] == "passed"
    assert [command["name"] for command in result["commands"]] == ["baseline-fail"]


def test_run_module_converts_orchestration_exception_into_failed_command_result(
    tmp_path: Path,
    monkeypatch,
) -> None:
    module = load_module()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    iteration_dir = tmp_path / "report"
    module_spec = module.ModuleSpec(
        name="orchestration-contract-lane",
        category="contracts",
        description="command orchestration failure",
        risk="medium",
        optimization_lane="repo-contracts",
        ownership_paths=("tests/",),
        command_plans=(
            module.command_plan("broken-command", ["echo", "broken"]),
            module.command_plan("healthy-command", ["echo", "healthy"]),
        ),
    )
    executed: list[str] = []

    def fake_materialize(plan, _repo_root):
        if plan.name == "broken-command":
            raise RuntimeError("materialize exploded")
        return module.MaterializedCommand(
            name=plan.name,
            cwd=_repo_root,
            command=(plan.name,),
            timeout_seconds=plan.timeout_seconds,
            env_overrides={},
        )

    def fake_run(command, log_path):
        executed.append(command.name)
        return {
            "name": command.name,
            "status": "passed",
            "command": list(command.command),
            "cwd": str(command.cwd),
            "timeout_seconds": command.timeout_seconds,
            "log_path": str(log_path),
            "log_tail": "",
            "return_code": 0,
            "duration_seconds": 0.01,
            "started_at": "2026-04-25T00:00:00Z",
            "ended_at": "2026-04-25T00:00:00Z",
            "error": None,
        }

    monkeypatch.setattr(module, "materialize_command", fake_materialize)
    monkeypatch.setattr(module, "run_materialized_command", fake_run)

    result = module.run_module(module_spec, repo_root, iteration_dir, "baseline")

    assert executed == ["healthy-command"]
    assert result["status"] == "failed"
    assert [command["status"] for command in result["commands"]] == ["failed", "passed"]
    assert result["commands"][0]["error"] == "command orchestration failed: RuntimeError: materialize exploded"
    assert "command orchestration failed: RuntimeError: materialize exploded" in result["commands"][0]["log_tail"]
    assert Path(result["commands"][0]["log_path"]).exists()


def test_build_failure_lanes_prioritizes_longer_higher_risk_lanes() -> None:
    module = load_module()
    module_results = [
        {
            "name": "repo-medium",
            "optimization_lane": "repo-contracts",
            "risk": "medium-high",
            "status": "failed",
            "commands": [
                {"name": "lint", "status": "failed", "timeout_seconds": 1800},
                {"name": "build", "status": "failed", "timeout_seconds": 1200},
            ],
        },
        {
            "name": "frontend-long",
            "optimization_lane": "frontend-web",
            "risk": "high",
            "status": "failed",
            "commands": [
                {"name": "e2e", "status": "failed", "timeout_seconds": 2400},
            ],
        },
        {
            "name": "backend-short",
            "optimization_lane": "backend-runtime",
            "risk": "high",
            "status": "failed",
            "commands": [
                {"name": "pytest", "status": "failed", "timeout_seconds": 1800},
            ],
        },
        {
            "name": "backend-heavy",
            "optimization_lane": "backend-runtime",
            "risk": "medium-high",
            "status": "failed",
            "commands": [
                {"name": "pytest-a", "status": "failed", "timeout_seconds": 1800},
                {"name": "pytest-b", "status": "failed", "timeout_seconds": 900},
            ],
        },
        {
            "name": "frontend-passed",
            "optimization_lane": "frontend-web",
            "risk": "high",
            "status": "passed",
            "commands": [
                {"name": "skip", "status": "passed", "timeout_seconds": 2400},
            ],
        },
    ]

    lanes = module.build_failure_lanes(module_results)

    assert [lane for lane, _ in lanes] == [
        "frontend-web",
        "backend-runtime",
        "repo-contracts",
    ]
    assert [failure["name"] for failure in lanes[1][1]] == [
        "backend-heavy",
        "backend-short",
    ]


def test_merge_module_results_keeps_baseline_failure_when_verify_is_skipped() -> None:
    module = load_module()
    baseline_results = [
        {
            "name": "contracts-frontend-build-startup",
            "category": "contracts",
            "description": "frontend startup contract",
            "risk": "high",
            "optimization_lane": "repo-contracts",
            "ownership_paths": ["web/"],
            "status": "failed",
            "commands": [
                {"name": "lint", "status": "passed", "command": ["pnpm", "lint"]},
                {"name": "build", "status": "failed", "command": ["pnpm", "build"]},
            ],
        }
    ]
    verification_results = [
        {
            "name": "contracts-frontend-build-startup",
            "category": "contracts",
            "description": "frontend startup contract",
            "risk": "high",
            "optimization_lane": "repo-contracts",
            "ownership_paths": ["web/"],
            "status": "skipped",
            "commands": [
                {"name": "build", "status": "skipped", "command": [], "log_tail": "no matching frontend targets"}
            ],
        }
    ]

    merged = module.merge_module_results(baseline_results, verification_results)

    assert merged[0]["status"] == "failed"
    assert [command["status"] for command in merged[0]["commands"]] == ["passed", "failed"]


def test_run_iteration_only_verifies_failed_commands_and_merges_results(tmp_path: Path, monkeypatch) -> None:
    module = load_module()
    repo_root = tmp_path / "repo"
    report_dir = tmp_path / "report"
    stop_file = report_dir / module.STOP_FILE_NAME
    repo_root.mkdir()
    module_spec = module.ModuleSpec(
        name="contracts-frontend-build-startup",
        category="contracts",
        description="frontend startup contract",
        risk="high",
        optimization_lane="repo-contracts",
        ownership_paths=("web/",),
        command_plans=(
            module.command_plan("lint", ["pnpm", "lint"]),
            module.command_plan("build", ["pnpm", "build"]),
        ),
    )
    verify_calls: list[set[str] | None] = []

    def fake_run_module(current_module, _repo_root, iteration_dir, phase, *, command_names=None):
        assert current_module.name == module_spec.name
        assert _repo_root == repo_root
        assert iteration_dir.name.startswith("2026")
        verify_calls.append(command_names)
        if phase == "baseline":
            return {
                "name": current_module.name,
                "category": current_module.category,
                "description": current_module.description,
                "risk": current_module.risk,
                "optimization_lane": current_module.optimization_lane,
                "ownership_paths": list(current_module.ownership_paths),
                "status": "failed",
                "commands": [
                    {"name": "lint", "status": "passed", "command": ["pnpm", "lint"]},
                    {"name": "build", "status": "failed", "command": ["pnpm", "build"]},
                ],
            }
        assert phase == "verify"
        assert command_names == {"build"}
        return {
            "name": current_module.name,
            "category": current_module.category,
            "description": current_module.description,
            "risk": current_module.risk,
            "optimization_lane": current_module.optimization_lane,
            "ownership_paths": list(current_module.ownership_paths),
            "status": "passed",
            "commands": [
                {"name": "build", "status": "passed", "command": ["pnpm", "build"]},
            ],
        }

    times = iter(
        [
            module.dt.datetime(2026, 4, 25, 0, 0, 0, tzinfo=module.dt.timezone.utc),
            module.dt.datetime(2026, 4, 25, 0, 0, 3, tzinfo=module.dt.timezone.utc),
        ]
    )

    monkeypatch.setattr(module, "run_module", fake_run_module)
    monkeypatch.setattr(
        module,
        "run_agent_lane",
        lambda *args, **kwargs: {
            "lane": "repo-contracts",
            "status": "passed",
            "failures": [module_spec.name],
            "prompt_path": "prompt.md",
            "output_message_path": "agent.txt",
            "summary": "fixed build",
            "execution": {"status": "passed"},
        },
    )
    monkeypatch.setattr(module, "utc_now", lambda: next(times))
    monkeypatch.setattr(module, "write_report_files", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "collect_git_state", lambda _repo_root: {"dirty_count": 1})
    monkeypatch.setattr(
        module, "build_module_inventory", lambda modules, _repo_root: [{"name": item.name} for item in modules]
    )

    report = module.run_iteration(
        iteration=1,
        modules=[module_spec],
        repo_root=repo_root,
        report_dir=report_dir,
        stop_file=stop_file,
        model=module.DEFAULT_AGENT_MODEL,
        skip_agent_optimize=False,
        unsafe_bypass_sandbox=False,
        max_parallel_agents=1,
        agent_timeout_seconds=60,
    )

    assert verify_calls == [None, {"build"}]
    assert report["issue_count"] == 0
    assert report["verification_modules"][0]["commands"] == [
        {"name": "build", "status": "passed", "command": ["pnpm", "build"]}
    ]
    assert [command["status"] for command in report["modules"][0]["commands"]] == ["passed", "passed"]


def test_run_iteration_records_agent_lane_exceptions_and_continues_verify(tmp_path: Path, monkeypatch) -> None:
    module = load_module()
    repo_root = tmp_path / "repo"
    report_dir = tmp_path / "report"
    stop_file = report_dir / module.STOP_FILE_NAME
    repo_root.mkdir()
    module_spec = module.ModuleSpec(
        name="contracts-frontend-build-startup",
        category="contracts",
        description="frontend startup contract",
        risk="high",
        optimization_lane="repo-contracts",
        ownership_paths=("web/",),
        command_plans=(
            module.command_plan("lint", ["pnpm", "lint"]),
            module.command_plan("build", ["pnpm", "build"]),
        ),
    )
    verify_calls: list[set[str] | None] = []

    def fake_run_module(current_module, _repo_root, iteration_dir, phase, *, command_names=None):
        assert current_module.name == module_spec.name
        assert _repo_root == repo_root
        assert iteration_dir.name.startswith("2026")
        verify_calls.append(command_names)
        if phase == "baseline":
            return {
                "name": current_module.name,
                "category": current_module.category,
                "description": current_module.description,
                "risk": current_module.risk,
                "optimization_lane": current_module.optimization_lane,
                "ownership_paths": list(current_module.ownership_paths),
                "status": "failed",
                "commands": [
                    {"name": "lint", "status": "passed", "command": ["pnpm", "lint"]},
                    {"name": "build", "status": "failed", "command": ["pnpm", "build"]},
                ],
            }
        assert phase == "verify"
        assert command_names == {"build"}
        return {
            "name": current_module.name,
            "category": current_module.category,
            "description": current_module.description,
            "risk": current_module.risk,
            "optimization_lane": current_module.optimization_lane,
            "ownership_paths": list(current_module.ownership_paths),
            "status": "passed",
            "commands": [
                {"name": "build", "status": "passed", "command": ["pnpm", "build"]},
            ],
        }

    times = iter(
        [
            module.dt.datetime(2026, 4, 25, 0, 0, 0, tzinfo=module.dt.timezone.utc),
            module.dt.datetime(2026, 4, 25, 0, 0, 1, tzinfo=module.dt.timezone.utc),
            module.dt.datetime(2026, 4, 25, 0, 0, 4, tzinfo=module.dt.timezone.utc),
            module.dt.datetime(2026, 4, 25, 0, 0, 5, tzinfo=module.dt.timezone.utc),
        ]
    )
    captured: dict[str, object] = {}

    monkeypatch.setattr(module, "run_module", fake_run_module)
    monkeypatch.setattr(
        module, "run_agent_lane", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("lane crash"))
    )
    monkeypatch.setattr(module, "utc_now", lambda: next(times))
    monkeypatch.setattr(
        module,
        "write_report_files",
        lambda _report_dir, _iteration_slug, report: captured.setdefault("report", report),
    )
    monkeypatch.setattr(module, "collect_git_state", lambda _repo_root: {"dirty_count": 1})
    monkeypatch.setattr(
        module, "build_module_inventory", lambda modules, _repo_root: [{"name": item.name} for item in modules]
    )

    report = module.run_iteration(
        iteration=1,
        modules=[module_spec],
        repo_root=repo_root,
        report_dir=report_dir,
        stop_file=stop_file,
        model=module.DEFAULT_AGENT_MODEL,
        skip_agent_optimize=False,
        unsafe_bypass_sandbox=False,
        max_parallel_agents=1,
        agent_timeout_seconds=60,
    )

    assert verify_calls == [None, {"build"}]
    assert report["issue_count"] == 0
    assert report["agents"][0]["status"] == "failed"
    assert report["agents"][0]["error"] == "agent lane crashed: RuntimeError: lane crash"
    assert "agent lane crashed: RuntimeError: lane crash" in report["agents"][0]["execution"]["log_tail"]
    assert Path(report["agents"][0]["execution"]["log_path"]).exists()
    assert captured["report"] == report
    assert [command["status"] for command in report["modules"][0]["commands"]] == ["passed", "passed"]


def test_run_iteration_returns_report_error_and_fallback_snapshot_when_report_write_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    module = load_module()
    repo_root = tmp_path / "repo"
    report_dir = tmp_path / "report"
    stop_file = report_dir / module.STOP_FILE_NAME
    repo_root.mkdir()
    module_spec = module.ModuleSpec(
        name="contracts-runtime-probes-docs",
        category="contracts",
        description="report persistence fallback",
        risk="medium",
        optimization_lane="repo-contracts",
        ownership_paths=("tests/",),
        command_plans=(),
    )
    times = iter(
        [
            module.dt.datetime(2026, 4, 25, 0, 0, 0, tzinfo=module.dt.timezone.utc),
            module.dt.datetime(2026, 4, 25, 0, 0, 3, tzinfo=module.dt.timezone.utc),
        ]
    )
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        module,
        "run_module",
        lambda *args, **kwargs: {
            "name": module_spec.name,
            "category": module_spec.category,
            "description": module_spec.description,
            "risk": module_spec.risk,
            "optimization_lane": module_spec.optimization_lane,
            "ownership_paths": list(module_spec.ownership_paths),
            "status": "passed",
            "commands": [],
        },
    )
    monkeypatch.setattr(module, "utc_now", lambda: next(times))
    monkeypatch.setattr(
        module,
        "write_report_files",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("disk full")),
    )
    monkeypatch.setattr(
        module,
        "write_iteration_report_files",
        lambda _report_dir, _iteration_slug, report, markdown=None: captured.setdefault("report", report),
    )
    monkeypatch.setattr(module, "collect_git_state", lambda _repo_root: {"dirty_count": 1})
    monkeypatch.setattr(
        module, "build_module_inventory", lambda modules, _repo_root: [{"name": item.name} for item in modules]
    )

    report = module.run_iteration(
        iteration=1,
        modules=[module_spec],
        repo_root=repo_root,
        report_dir=report_dir,
        stop_file=stop_file,
        model=module.DEFAULT_AGENT_MODEL,
        skip_agent_optimize=False,
        unsafe_bypass_sandbox=False,
        max_parallel_agents=1,
        agent_timeout_seconds=60,
    )

    assert report["report_error"] == "report persistence failed: OSError: disk full"
    assert Path(report["report_error_log_path"]).exists()
    assert "report persistence failed: OSError: disk full" in Path(report["report_error_log_path"]).read_text(
        encoding="utf-8"
    )
    assert captured["report"] == report


def test_write_report_files_emits_latest_and_iteration_reports(tmp_path: Path) -> None:
    module = load_module()
    report = {
        "iteration": 1,
        "started_at": "2026-04-20T00:00:00Z",
        "ended_at": "2026-04-20T00:00:03Z",
        "agent_model": "gpt-5.5",
        "stop_file": "target/continuous/STOP_CONTINUOUS_LOOP",
        "git_state": {"dirty_count": 7},
        "issue_count": 0,
        "modules": [
            {
                "name": "contracts-runtime-probes-docs",
                "status": "passed",
                "risk": "high",
                "commands": [
                    {
                        "name": "contracts-runtime-probes-docs",
                        "status": "passed",
                        "command": ["python", "-m", "pytest", "tests/test_main_entrypoint.py"],
                        "log_tail": "",
                        "log_path": "logs/verify-main.log",
                        "return_code": 0,
                        "duration_seconds": 7.25,
                    }
                ],
            }
        ],
        "baseline_modules": [
            {
                "name": "contracts-runtime-probes-docs",
                "status": "failed",
                "commands": [
                    {
                        "name": "contracts-runtime-probes-docs",
                        "status": "failed",
                        "command": ["python", "-m", "pytest", "tests/test_main_entrypoint.py"],
                        "log_tail": "failure tail",
                        "log_path": "logs/baseline-main.log",
                        "return_code": 1,
                        "duration_seconds": 11.5,
                    }
                ],
            }
        ],
        "verification_modules": [
            {
                "name": "contracts-runtime-probes-docs",
                "status": "passed",
                "commands": [
                    {
                        "name": "contracts-runtime-probes-docs",
                        "status": "passed",
                        "command": ["python", "-m", "pytest", "tests/test_main_entrypoint.py"],
                        "log_tail": "",
                        "log_path": "logs/verify-main.log",
                        "return_code": 0,
                        "duration_seconds": 7.25,
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
                "execution": {
                    "return_code": 0,
                    "duration_seconds": 15.0,
                    "log_path": "logs/agent-repo-contracts.log",
                },
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
    assert "- Baseline Issue Count: 1" in markdown
    assert "- Verification Issue Count: 0" in markdown
    assert "- Final Issue Count: 0" in markdown
    assert "- `contracts-runtime-probes-docs` (high): final=passed, baseline=failed, verify=passed" in markdown
    assert "`contracts-runtime-probes-docs`: failed -> passed" in markdown
    assert "source=verify, rc=0, duration=7.25s" in markdown
    assert "Baseline Log: `logs/baseline-main.log`" in markdown
    assert "Verify Log: `logs/verify-main.log`" in markdown
    assert "Execution: rc=0, duration=15.0s" in markdown
    assert "Log: `logs/agent-repo-contracts.log`" in markdown
    assert "Summary: fixed the failing lane" in markdown


def test_write_report_files_surfaces_explicit_command_and_agent_errors(tmp_path: Path) -> None:
    module = load_module()
    report = {
        "iteration": 1,
        "started_at": "2026-04-20T00:00:00Z",
        "ended_at": "2026-04-20T00:00:03Z",
        "agent_model": "gpt-5.5",
        "stop_file": "target/continuous/STOP_CONTINUOUS_LOOP",
        "git_state": {"dirty_count": 7},
        "issue_count": 1,
        "report_error": "report persistence failed: OSError: disk full",
        "report_error_log_path": "logs/report-write-error.log",
        "modules": [
            {
                "name": "contracts-runtime-probes-docs",
                "status": "failed",
                "risk": "high",
                "commands": [
                    {
                        "name": "contracts-runtime-probes-docs",
                        "status": "failed",
                        "command": [],
                        "log_tail": "command orchestration failed: RuntimeError: boom",
                        "log_path": "logs/baseline-main.log",
                        "return_code": None,
                        "duration_seconds": 0.0,
                        "error": "command orchestration failed: RuntimeError: boom",
                    }
                ],
            }
        ],
        "baseline_modules": [
            {
                "name": "contracts-runtime-probes-docs",
                "status": "failed",
                "commands": [
                    {
                        "name": "contracts-runtime-probes-docs",
                        "status": "failed",
                        "command": [],
                        "log_tail": "command orchestration failed: RuntimeError: boom",
                        "log_path": "logs/baseline-main.log",
                        "return_code": None,
                        "duration_seconds": 0.0,
                        "error": "command orchestration failed: RuntimeError: boom",
                    }
                ],
            }
        ],
        "verification_modules": [],
        "agents": [
            {
                "lane": "repo-contracts",
                "status": "failed",
                "failures": ["contracts-runtime-probes-docs"],
                "summary": "",
                "error": "agent lane crashed: RuntimeError: lane crash",
                "execution": {
                    "return_code": None,
                    "duration_seconds": 0.0,
                    "log_path": "logs/agent-repo-contracts.log",
                    "error": "agent lane crashed: RuntimeError: lane crash",
                },
            }
        ],
    }

    module.write_report_files(tmp_path, "20260420T000000Z-iter-0001", report)

    markdown = (tmp_path / "latest.md").read_text(encoding="utf-8")

    assert "Report Error: `report persistence failed: OSError: disk full`" in markdown
    assert "Report Error Log: `logs/report-write-error.log`" in markdown
    assert "Error: `command orchestration failed: RuntimeError: boom`" in markdown
    assert "Error: `agent lane crashed: RuntimeError: lane crash`" in markdown
