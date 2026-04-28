from __future__ import annotations

import tomllib
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT_PATH = PROJECT_ROOT / "pyproject.toml"
README_PATH = PROJECT_ROOT / "README.md"
LICENSE_PATH = PROJECT_ROOT / "LICENSE"


def load_pyproject() -> dict[str, object]:
    with PYPROJECT_PATH.open("rb") as file:
        return tomllib.load(file)


def test_project_readme_path_exists() -> None:
    pyproject = load_pyproject()

    project = pyproject["project"]

    assert project["readme"] == "README.md"
    assert README_PATH.exists()


def test_project_license_metadata_has_repo_file() -> None:
    pyproject = load_pyproject()

    project = pyproject["project"]

    assert project["license"] == "MIT"
    assert LICENSE_PATH.exists()


def test_setuptools_build_contract_targets_only_app_packages() -> None:
    pyproject = load_pyproject()

    build_system = pyproject["build-system"]
    setuptools_find = pyproject["tool"]["setuptools"]["packages"]["find"]

    requires = build_system["requires"]

    assert build_system["build-backend"] == "setuptools.build_meta"
    assert any(requirement.startswith("setuptools") for requirement in requires)
    assert "wheel" in requires
    assert setuptools_find["where"] == ["."]
    assert setuptools_find["include"] == ["app*"]


def test_coverage_run_contract_uses_repo_scoped_non_parallel_data_file() -> None:
    pyproject = load_pyproject()

    coverage_run = pyproject["tool"]["coverage"]["run"]

    assert coverage_run["parallel"] is False
    assert coverage_run["data_file"] == ".coverage.pytest"
