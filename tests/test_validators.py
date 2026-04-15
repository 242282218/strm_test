from pathlib import Path

import pytest

from app.core.validators import (
    InputValidationError,
    _validate_basic_string,
    validate_http_url,
    validate_identifier,
    validate_path,
    validate_proxy_path,
)


@pytest.mark.parametrize(
    ("value", "error_substr"),
    [
        (None, "is required"),
        (1, "must be a string"),
        ("   ", "is required"),
        ("a" * 6, "length must be <="),
        ("ab\x01cd", "contains invalid characters"),
    ],
)
def test_validate_basic_string_rejects_invalid_inputs(value, error_substr: str) -> None:
    with pytest.raises(InputValidationError, match=error_substr):
        _validate_basic_string(value, "field", 5)


def test_validate_basic_string_returns_trimmed_value() -> None:
    assert _validate_basic_string("  ok  ", "field", 10) == "ok"


def test_validate_path_accepts_valid_relative_path() -> None:
    assert validate_path("folder/file.txt") == "folder/file.txt"


def test_validate_path_rejects_traversal_and_absolute_policy() -> None:
    with pytest.raises(InputValidationError, match="path traversal sequence"):
        validate_path("../etc/passwd")

    with pytest.raises(InputValidationError, match="relative path"):
        validate_path("/etc/passwd")


def test_validate_path_respects_base_dir(tmp_path: Path) -> None:
    base = tmp_path / "base"
    base.mkdir()

    valid = validate_path("child/data.txt", base_dir=str(base))
    assert valid == "child/data.txt"

    with pytest.raises(InputValidationError, match="outside of allowed base directory"):
        validate_path(str(tmp_path / "escape.txt"), base_dir=str(base), allow_absolute=True)


def test_validate_path_respects_allowed_dirs_and_allow_absolute(tmp_path: Path) -> None:
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    allowed_file = allowed / "ok.txt"
    outside = tmp_path / "outside" / "bad.txt"

    assert validate_path(str(allowed_file), allowed_dirs=[str(allowed)]) == str(allowed_file)

    with pytest.raises(InputValidationError, match="not in allowed directories"):
        validate_path(str(outside), allowed_dirs=[str(allowed)])

    assert validate_path(str(allowed_file), allow_absolute=True) == str(allowed_file)


def test_validate_identifier_rejects_invalid_format() -> None:
    assert validate_identifier("abc-123_:.") == "abc-123_:."

    with pytest.raises(InputValidationError, match="invalid format"):
        validate_identifier("bad id")


def test_validate_http_url_requires_http_or_https() -> None:
    assert validate_http_url("https://example.com/path") == "https://example.com/path"

    with pytest.raises(InputValidationError, match="http/https URL"):
        validate_http_url("ftp://example.com")

    with pytest.raises(InputValidationError, match="http/https URL"):
        validate_http_url("https:///missing-host")


def test_validate_proxy_path_rejects_scheme_and_parent_segment() -> None:
    assert validate_proxy_path("a/b/c") == "a/b/c"

    with pytest.raises(InputValidationError, match="invalid scheme"):
        validate_proxy_path("http://evil/path")

    with pytest.raises(InputValidationError, match="invalid scheme"):
        validate_proxy_path("//evil/path")

    with pytest.raises(InputValidationError, match="invalid path segment"):
        validate_proxy_path("a/../b")
