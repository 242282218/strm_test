import re
from pathlib import Path


PROJECT_WORKFLOW_DIR = Path(__file__).resolve().parents[1] / ".github" / "workflows"
ROOT_WORKFLOW_DIR = Path(__file__).resolve().parents[2] / ".github" / "workflows"


def resolve_workflow_path(filename: str) -> Path:
    root_path = ROOT_WORKFLOW_DIR / filename
    if root_path.exists():
        return root_path
    return PROJECT_WORKFLOW_DIR / filename


WORKFLOW_PATH = PROJECT_WORKFLOW_DIR / "docker-deploy-test.yml"
ROOT_PYTEST_WORKFLOW_PATH = resolve_workflow_path("pytest.yml")
ROOT_CI_WORKFLOW_PATH = resolve_workflow_path("ci.yml")


def test_prebuild_pytest_step_does_not_ignore_failures() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

    assert '-m "not slow" || true' not in workflow
    assert "- name: Run unit tests" in workflow


def test_summary_job_fails_when_prebuild_tests_fail() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "needs.pre-build-tests.result" in workflow
    assert 'if [[ "${{ needs.pre-build-tests.result }}" == "failure" ]]' in workflow


def test_root_pytest_workflow_does_not_ignore_test_failures() -> None:
    workflow = ROOT_PYTEST_WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "- name: Run Tests" in workflow
    assert "continue-on-error: true" not in workflow.split("- name: Run Tests", 1)[1].split("- name:", 1)[0]


def test_root_pytest_workflow_coverage_threshold_not_too_low() -> None:
    workflow = ROOT_PYTEST_WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "--cov-fail-under=${{ env.COVERAGE_FAIL_UNDER }}" in workflow

    match = re.search(r"COVERAGE_FAIL_UNDER:\s*\"?(?P<value>\d+)\"?", workflow)
    assert match is not None
    assert int(match.group("value")) >= 35



def test_root_ci_workflow_does_not_ignore_python_test_failures() -> None:
    workflow = ROOT_CI_WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "- name: Run tests with coverage" in workflow
    assert "continue-on-error: true" not in workflow.split("- name: Run tests with coverage", 1)[1].split("- name:", 1)[0]
