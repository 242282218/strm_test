from __future__ import annotations

import os
import sys
from collections.abc import Sequence
from pathlib import Path


_PYTEST_EXECUTABLE_NAMES = {"pytest", "pytest.exe", "py.test", "py.test.exe"}


def _looks_like_pytest_invocation(argv: Sequence[str]) -> bool:
    if not argv:
        return False

    executable = Path(argv[0]).name.lower()
    if executable in _PYTEST_EXECUTABLE_NAMES:
        return True

    for index, token in enumerate(argv[:-1]):
        if token == "-m" and argv[index + 1] == "pytest":
            return True
    return False


def build_pytest_coverage_file(
    *,
    argv: Sequence[str],
    existing: str | None,
    pid: int,
) -> str | None:
    if existing:
        return existing
    if not _looks_like_pytest_invocation(argv):
        return None
    return f".coverage.pytest.{pid}"


def configure_pytest_coverage_file() -> str | None:
    coverage_file = build_pytest_coverage_file(
        argv=sys.argv,
        existing=os.environ.get("COVERAGE_FILE"),
        pid=os.getpid(),
    )
    if coverage_file is not None:
        os.environ["COVERAGE_FILE"] = coverage_file
    return coverage_file


configure_pytest_coverage_file()
