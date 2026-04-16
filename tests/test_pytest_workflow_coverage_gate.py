import re
from pathlib import Path


PROJECT_WORKFLOW_DIR = Path(__file__).resolve().parents[1] / ".github" / "workflows"
ROOT_WORKFLOW_DIR = Path(__file__).resolve().parents[2] / ".github" / "workflows"


def resolve_workflow_path(filename: str) -> Path:
    root_path = ROOT_WORKFLOW_DIR / filename
    if root_path.exists():
        return root_path
    return PROJECT_WORKFLOW_DIR / filename


def test_pytest_workflow_coverage_threshold_not_below_65() -> None:
    workflow = resolve_workflow_path("pytest.yml").read_text(encoding="utf-8")

    assert "--cov-fail-under=${{ env.COVERAGE_FAIL_UNDER }}" in workflow

    match = re.search(r"COVERAGE_FAIL_UNDER:\s*\"?(?P<value>\d+)\"?", workflow)
    assert match is not None
    assert int(match.group("value")) >= 65
