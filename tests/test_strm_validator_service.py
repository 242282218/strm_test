from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services import strm_validator as sv


def _make_validator(tmp_path: Path, cache_file: str | None = None) -> sv.StrmValidator:
    return sv.StrmValidator(
        target_directory=str(tmp_path),
        remote_base="/remote",
        video_formats={"mkv", "mp4"},
        size_threshold_mb=1,
        cache_file=cache_file,
    )


def test_validation_result_to_dict_counts_and_truncates() -> None:
    valid = [f"v{i}" for i in range(12)]
    invalid = [f"i{i}" for i in range(12)]
    result = sv.ValidationResult(valid_files=valid, invalid_files=invalid, missing_files=["m"], extra_files=["e"])

    payload = result.to_dict()

    assert payload["valid_count"] == 12
    assert payload["invalid_count"] == 12
    assert payload["missing_count"] == 1
    assert payload["extra_count"] == 1
    assert payload["total_count"] == 24
    assert len(payload["valid_files"]) == 10
    assert len(payload["invalid_files"]) == 10


def test_load_cached_tree_success_and_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    cache_file = tmp_path / "tree.json"
    cache_file.write_text(json.dumps({"children": []}), encoding="utf-8")
    validator = _make_validator(tmp_path, cache_file=str(cache_file))

    loaded = validator.load_cached_tree()

    assert loaded == {"children": []}
    assert validator.cached_tree == {"children": []}

    bad_cache_file = tmp_path / "bad.json"
    bad_cache_file.write_text("{not-json", encoding="utf-8")
    errors: list[str] = []
    bad_validator = _make_validator(tmp_path, cache_file=str(bad_cache_file))
    monkeypatch.setattr(sv.logger, "error", lambda message: errors.append(message))

    assert bad_validator.load_cached_tree() is None
    assert any("Failed to load cached tree" in message for message in errors)


def test_list_local_strm_files_only_returns_strm_files(tmp_path: Path) -> None:
    (tmp_path / "movies").mkdir()
    keep = tmp_path / "movies" / "a.strm"
    keep.write_text("http://example/a", encoding="utf-8")
    drop = tmp_path / "movies" / "a.txt"
    drop.write_text("text", encoding="utf-8")
    nested = tmp_path / "movies" / "nested.strm"
    nested.write_text("http://example/b", encoding="utf-8")

    validator = _make_validator(tmp_path)
    files = validator.list_local_strm_files()

    assert set(files) == {os.path.abspath(str(keep)), os.path.abspath(str(nested))}


def test_build_expected_strm_set_filters_by_base_size_and_extension(tmp_path: Path) -> None:
    validator = sv.StrmValidator(
        target_directory=str(tmp_path),
        remote_base="/remote",
        video_formats={"mkv", "mp4"},
        size_threshold_mb=100,
    )
    big = 200 * 1024 * 1024
    tiny = 5 * 1024 * 1024
    tree = {
        "children": [
            {"m1": {"name": "/remote/movies/Movie.mkv", "size": big, "is_dir": False}},
            {"small": {"name": "/remote/movies/Small.mp4", "size": tiny, "is_dir": False}},
            {"txt": {"name": "/remote/movies/Readme.txt", "size": big, "is_dir": False}},
            {"outside": {"name": "/other/Other.mkv", "size": big, "is_dir": False}},
            {
                "folder": {
                    "name": "/remote/series",
                    "is_dir": True,
                    "children": [{"ep1": {"name": "/remote/series/Ep01.mp4", "size": big, "is_dir": False}}],
                }
            },
        ]
    }

    expected = validator.build_expected_strm_set(tree)

    movie_path = os.path.abspath(str(tmp_path / "movies" / "Movie.strm"))
    episode_path = os.path.abspath(str(tmp_path / "series" / "Ep01.strm"))
    assert expected == {movie_path, episode_path}


@pytest.mark.asyncio
async def test_fast_scan_without_cache_marks_all_local_files_invalid(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    validator = _make_validator(tmp_path)
    monkeypatch.setattr(validator, "load_cached_tree", lambda: None)

    local = ["/tmp/a.strm", "/tmp/b.strm"]
    result = await validator.fast_scan(local)

    assert result.valid_files == []
    assert result.invalid_files == local
    assert result.missing_files == []
    assert result.extra_files == []


@pytest.mark.asyncio
async def test_fast_scan_reports_extra_and_missing_files(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    validator = _make_validator(tmp_path)
    expected_set = {
        "/tmp/keep.strm",
        "/tmp/missing.strm",
    }
    monkeypatch.setattr(validator, "load_cached_tree", lambda: {"children": []})
    monkeypatch.setattr(validator, "build_expected_strm_set", lambda _tree: expected_set)

    result = await validator.fast_scan(["/tmp/keep.strm", "/tmp/extra.strm"])

    assert set(result.valid_files) == {"/tmp/keep.strm"}
    assert set(result.extra_files) == {"/tmp/extra.strm"}
    assert set(result.missing_files) == {"/tmp/missing.strm"}
    assert set(result.invalid_files) == {"/tmp/extra.strm", "/tmp/missing.strm"}


@pytest.mark.asyncio
async def test_slow_scan_validates_status_empty_content_and_exceptions(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    validator = _make_validator(tmp_path)

    ok = tmp_path / "ok.strm"
    ok.write_text("http://ok", encoding="utf-8")
    partial = tmp_path / "partial.strm"
    partial.write_text("http://partial", encoding="utf-8")
    redirect = tmp_path / "redirect.strm"
    redirect.write_text("http://redirect", encoding="utf-8")
    bad = tmp_path / "bad.strm"
    bad.write_text("http://bad", encoding="utf-8")
    empty = tmp_path / "empty.strm"
    empty.write_text("", encoding="utf-8")
    err = tmp_path / "err.strm"
    err.write_text("http://err", encoding="utf-8")

    statuses = {
        "http://ok": 200,
        "http://partial": 206,
        "http://redirect": 302,
        "http://bad": 404,
        "http://err": RuntimeError("network failed"),
    }

    class FakeHeadContext:
        def __init__(self, behavior):
            self.behavior = behavior

        async def __aenter__(self):
            if isinstance(self.behavior, Exception):
                raise self.behavior
            return SimpleNamespace(status=self.behavior)

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class FakeClientSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        def head(self, url: str, timeout):
            assert timeout.total == 10
            return FakeHeadContext(statuses[url])

    monkeypatch.setattr(sv.aiohttp, "ClientSession", FakeClientSession)
    monkeypatch.setattr(sv.aiohttp, "ClientTimeout", lambda total: SimpleNamespace(total=total))

    result = await validator.slow_scan(
        [str(ok), str(partial), str(redirect), str(bad), str(empty), str(err)],
        concurrent_limit=3,
    )

    valid = {os.path.abspath(str(ok)), os.path.abspath(str(partial)), os.path.abspath(str(redirect))}
    invalid = {os.path.abspath(str(bad)), os.path.abspath(str(empty)), os.path.abspath(str(err))}
    assert set(result.valid_files) == valid
    assert set(result.invalid_files) == invalid
    assert result.missing_files == []
    assert result.extra_files == []


@pytest.mark.asyncio
async def test_validate_dispatches_scan_mode_and_rejects_unknown_mode(tmp_path: Path) -> None:
    validator = _make_validator(tmp_path)
    validator.list_local_strm_files = lambda: ["a", "b"]  # type: ignore[method-assign]
    validator.fast_scan = AsyncMock(return_value=sv.ValidationResult(["a"], [], [], []))  # type: ignore[method-assign]
    validator.slow_scan = AsyncMock(return_value=sv.ValidationResult([], ["a"], [], []))  # type: ignore[method-assign]

    quick = await validator.validate(sv.ScanMode.QUICK)
    slow = await validator.validate(sv.ScanMode.SLOW, concurrent_limit=9, download_interval=(0, 0))

    assert quick.valid_files == ["a"]
    assert slow.invalid_files == ["a"]
    validator.fast_scan.assert_awaited_once_with(["a", "b"])
    validator.slow_scan.assert_awaited_once_with(["a", "b"], 9, (0, 0))

    with pytest.raises(ValueError, match="Unknown scan mode"):
        await validator.validate("other")  # type: ignore[arg-type]
