from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

from sitecustomize import build_pytest_coverage_file


SITE_CUSTOMIZE_PATH = Path(__file__).resolve().parents[1] / "sitecustomize.py"
PYTEST_INI_PATH = Path(__file__).resolve().parents[1] / "pytest.ini"


def test_build_pytest_coverage_file_assigns_unique_file_for_pytest_process() -> None:
    result = build_pytest_coverage_file(
        argv=["python", "-m", "pytest", "tests/test_api_docs_contract.py"],
        existing=None,
        pid=4321,
    )

    assert result == ".coverage.pytest.4321"


def test_build_pytest_coverage_file_keeps_existing_override() -> None:
    result = build_pytest_coverage_file(
        argv=["python", "-m", "pytest"],
        existing="custom.coverage",
        pid=4321,
    )

    assert result == "custom.coverage"


def test_build_pytest_coverage_file_ignores_non_pytest_process() -> None:
    result = build_pytest_coverage_file(
        argv=["python", "app/main.py"],
        existing=None,
        pid=4321,
    )

    assert result is None


def test_sitecustomize_sets_runtime_coverage_file_for_pytest_process(monkeypatch) -> None:
    monkeypatch.delenv("COVERAGE_FILE", raising=False)
    monkeypatch.setattr(sys, "argv", ["python", "-m", "pytest", "tests/test_api_docs_contract.py"])
    monkeypatch.setattr(os, "getpid", lambda: 2468)

    module_name = "_sitecustomize_runtime_contract"
    sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(module_name, SITE_CUSTOMIZE_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
        assert os.environ["COVERAGE_FILE"] == ".coverage.pytest.2468"
    finally:
        sys.modules.pop(module_name, None)


def test_local_pytest_runtime_does_not_force_pytest_cov_in_addopts() -> None:
    pytest_ini = PYTEST_INI_PATH.read_text(encoding="utf-8")

    assert "addopts =" in pytest_ini
    assert "--cov=app" not in pytest_ini
