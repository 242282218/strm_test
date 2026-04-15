import os
import sys
import types
from pathlib import Path

import pytest

import app.core.path_security as path_security


def test_get_allowed_directories_appends_config_local_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    extra_dir = tmp_path / "media"

    class DummyConfigManager:
        def get(self, key: str, default):
            if key == "endpoints":
                return [{"dirs": [{"local_directory": str(extra_dir)}]}]
            return default

    fake_module = types.SimpleNamespace(ConfigManager=DummyConfigManager)
    monkeypatch.setitem(sys.modules, "app.core.config_manager", fake_module)

    allowed = path_security.get_allowed_directories()

    assert os.path.abspath(str(extra_dir)) in allowed


def test_get_allowed_directories_falls_back_to_default_on_config_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class BadConfigManager:
        def __init__(self) -> None:
            raise RuntimeError("config load failed")

    warnings: list[str] = []
    fake_module = types.SimpleNamespace(ConfigManager=BadConfigManager)
    monkeypatch.setitem(sys.modules, "app.core.config_manager", fake_module)
    monkeypatch.setattr(path_security.logger, "warning", lambda msg: warnings.append(msg))

    allowed = path_security.get_allowed_directories()

    assert len(allowed) >= 4
    assert any("Failed to load allowed directories" in msg for msg in warnings)


def test_validate_file_path_uses_default_allowed_dirs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    target = allowed / "file.txt"
    target.write_text("ok", encoding="utf-8")

    monkeypatch.setattr(path_security, "get_allowed_directories", lambda: [str(allowed)])

    validated = path_security.validate_file_path(str(target), allowed_dirs=None, check_exists=True)

    assert validated == os.path.realpath(str(target))


def test_validate_file_path_rejects_invalid_inputs(tmp_path: Path) -> None:
    with pytest.raises(path_security.PathSecurityError, match="cannot be empty"):
        path_security.validate_file_path("", allowed_dirs=[str(tmp_path)])

    with pytest.raises(path_security.PathSecurityError, match="No allowed directories"):
        path_security.validate_file_path("x", allowed_dirs=[])


def test_validate_file_path_rejects_symlink_when_not_allowed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    target = tmp_path / "a.txt"
    target.write_text("x", encoding="utf-8")
    monkeypatch.setattr(path_security.os.path, "islink", lambda _path: True)

    with pytest.raises(path_security.PathSecurityError, match="Symbolic links are not allowed"):
        path_security.validate_file_path(str(target), allowed_dirs=[str(tmp_path)])


def test_validate_file_path_raises_when_realpath_resolution_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    target = tmp_path / "a.txt"
    target.write_text("x", encoding="utf-8")
    monkeypatch.setattr(path_security.os.path, "islink", lambda _path: False)

    def raise_realpath(_path: str) -> str:
        raise OSError("boom")

    monkeypatch.setattr(path_security.os.path, "realpath", raise_realpath)

    with pytest.raises(path_security.PathSecurityError, match="Failed to resolve path"):
        path_security.validate_file_path(str(target), allowed_dirs=[str(tmp_path)])


def test_validate_file_path_rejects_outside_allowed_and_missing_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("x", encoding="utf-8")
    warnings: list[str] = []
    monkeypatch.setattr(path_security.logger, "warning", lambda msg: warnings.append(msg))

    with pytest.raises(path_security.PathSecurityError, match="Access denied"):
        path_security.validate_file_path(str(outside), allowed_dirs=[str(allowed)])

    missing_inside = allowed / "missing.txt"
    with pytest.raises(path_security.PathSecurityError, match="File does not exist"):
        path_security.validate_file_path(str(missing_inside), allowed_dirs=[str(allowed)], check_exists=True)

    assert any("Path security violation" in msg for msg in warnings)


def test_safe_open_writes_and_reads_with_auto_directory_creation(tmp_path: Path) -> None:
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    target = allowed / "nested" / "data.txt"

    with path_security.safe_open(str(target), mode="w", encoding="utf-8", allowed_dirs=[str(allowed)]) as fp:
        fp.write("hello")

    with path_security.safe_open(str(target), mode="r", encoding="utf-8", allowed_dirs=[str(allowed)]) as fp:
        assert fp.read() == "hello"


def test_safe_makedirs_supports_existing_and_new_paths(tmp_path: Path) -> None:
    allowed = tmp_path / "allowed"
    allowed.mkdir()

    existing = allowed / "existing"
    existing.mkdir()
    assert path_security.safe_makedirs(str(existing), allowed_dirs=[str(allowed)]) == os.path.abspath(str(existing))

    created = allowed / "new" / "child"
    result = path_security.safe_makedirs(str(created), allowed_dirs=[str(allowed)])
    assert result == os.path.abspath(str(created))
    assert created.is_dir()


def test_safe_rename_moves_file_and_creates_target_directory(tmp_path: Path) -> None:
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    src = allowed / "src.txt"
    src.write_text("rename", encoding="utf-8")
    dst = allowed / "nested" / "dst.txt"

    path_security.safe_rename(str(src), str(dst), allowed_dirs=[str(allowed)])

    assert not src.exists()
    assert dst.read_text(encoding="utf-8") == "rename"


def test_safe_symlink_invokes_os_symlink_with_validated_paths(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    src = allowed / "src.txt"
    src.write_text("link", encoding="utf-8")
    dst = allowed / "links" / "src.link"
    calls: list[tuple[str, str]] = []

    monkeypatch.setattr(path_security.os, "symlink", lambda a, b: calls.append((a, b)))

    path_security.safe_symlink(str(src), str(dst), allowed_dirs=[str(allowed)])

    assert calls
    assert calls[0][0] == os.path.realpath(str(src))
    assert calls[0][1] == os.path.realpath(str(dst))


def test_safe_hardlink_falls_back_to_copy_on_cross_device(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    src = allowed / "src.txt"
    src.write_text("hardlink", encoding="utf-8")
    dst = allowed / "copy" / "dst.txt"
    copied: list[tuple[str, str]] = []
    warnings: list[str] = []

    def raise_exdev(_src: str, _dst: str) -> None:
        raise OSError(18, "Invalid cross-device link")

    monkeypatch.setattr(path_security.os, "link", raise_exdev)
    monkeypatch.setattr(path_security.logger, "warning", lambda msg: warnings.append(msg))
    monkeypatch.setattr("shutil.copy2", lambda a, b: copied.append((a, b)))

    path_security.safe_hardlink(str(src), str(dst), allowed_dirs=[str(allowed)])

    assert copied
    assert any("Cross-device link detected" in msg for msg in warnings)


def test_safe_hardlink_reraises_non_cross_device_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    src = allowed / "src.txt"
    src.write_text("hardlink", encoding="utf-8")
    dst = allowed / "dst.txt"

    def raise_other(_src: str, _dst: str) -> None:
        raise OSError(5, "io error")

    monkeypatch.setattr(path_security.os, "link", raise_other)

    with pytest.raises(OSError, match="io error"):
        path_security.safe_hardlink(str(src), str(dst), allowed_dirs=[str(allowed)])
