from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.services.integrations.quark import QuarkService


class FakeClient:
    def __init__(self) -> None:
        self.cookie = "updated-cookie"
        self.request_responses: list[dict[str, Any] | Exception] = []
        self.request_calls: list[tuple[str, dict[str, str]]] = []
        self.file_info_map: dict[str, dict[str, Any]] = {}
        self.get_download_link_result: dict[str, Any] = {"url": "https://download.example.com/video.mp4"}
        self.rename_file_result: dict[str, Any] = {"ok": True}
        self.rename_calls: list[tuple[str, str]] = []
        self.move_calls: list[tuple[tuple[str, ...], str]] = []
        self.delete_calls: list[tuple[str, ...]] = []
        self.mkdir_calls: list[tuple[str, str]] = []
        self.closed = False

    async def request(self, endpoint: str, params: dict[str, str]) -> dict[str, Any]:
        self.request_calls.append((endpoint, params))
        if not self.request_responses:
            return {"data": {"list": [], "metadata": {"total": 0}}}
        response = self.request_responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    async def get_file_info(self, fid: str) -> dict[str, Any]:
        return self.file_info_map.get(fid, {})

    async def get_download_link(self, file_id: str) -> dict[str, Any]:
        return self.get_download_link_result

    async def get_transcoding_link(self, file_id: str) -> dict[str, Any]:
        return {"url": f"https://transcoding.example.com/{file_id}"}

    async def rename_file(self, fid: str, new_name: str) -> dict[str, Any]:
        self.rename_calls.append((fid, new_name))
        return self.rename_file_result

    async def move_files(self, fids: list[str], to_pdir_fid: str) -> None:
        self.move_calls.append((tuple(fids), to_pdir_fid))

    async def delete_files(self, fids: list[str]) -> None:
        self.delete_calls.append(tuple(fids))

    async def create_directory(self, parent_fid: str, name: str) -> dict[str, Any]:
        self.mkdir_calls.append((parent_fid, name))
        return {"fid": "new-dir", "name": name}

    async def close(self) -> None:
        self.closed = True


def _new_service(fake_client: FakeClient) -> QuarkService:
    service = QuarkService.__new__(QuarkService)
    service.client = fake_client
    service.cookie = "initial-cookie"
    service.referer = "https://pan.quark.cn/"
    return service


def test_looks_like_fid_validation() -> None:
    assert QuarkService._looks_like_fid("a" * 32) is True
    assert QuarkService._looks_like_fid("A" * 32) is True
    assert QuarkService._looks_like_fid("g" * 32) is False
    assert QuarkService._looks_like_fid("short") is False


def test_file_model_from_info_maps_dir_and_file_fields() -> None:
    file_info = {
        "fid": "fid-1",
        "file_name": "movie.mp4",
        "file_type": 1,
        "category": 1,
        "size": 1024,
        "created_at": 1,
        "updated_at": 2,
    }
    dir_info = {"fid": "dir-1", "file_name": "dir", "file_type": 0, "category": 0}

    file_model = QuarkService._file_model_from_info(file_info)
    dir_model = QuarkService._file_model_from_info(dir_info)

    assert file_model.file is True
    assert file_model.is_dir is False
    assert file_model.file_name == "movie.mp4"
    assert dir_model.file is False
    assert dir_model.is_dir is True


@pytest.mark.asyncio
async def test_get_files_supports_pagination_and_video_filter() -> None:
    client = FakeClient()
    client.request_responses = [
        {
            "data": {
                "list": [
                    {"fid": "1", "file_name": "Tom &amp; Jerry.mp4", "file_type": 1, "category": 1},
                    {"fid": "2", "file_name": "folder", "file_type": 0, "category": 0},
                ],
                "metadata": {"total": 3},
            }
        },
        {
            "data": {
                "list": [
                    {"fid": "3", "file_name": "song.mp3", "file_type": 1, "category": 2},
                ],
                "metadata": {"total": 3},
            }
        },
    ]
    service = _new_service(client)

    files = await service.get_files(parent="0", page_size=2, only_video=True)

    assert [item.fid for item in files] == ["1"]
    assert files[0].file_name == "Tom & Jerry.mp4"
    assert len(client.request_calls) == 2


@pytest.mark.asyncio
async def test_get_files_stops_and_returns_partial_on_request_error() -> None:
    client = FakeClient()
    client.request_responses = [
        {
            "data": {
                "list": [{"fid": "1", "file_name": "a.mp4", "file_type": 1, "category": 1}],
                "metadata": {"total": 10},
            }
        },
        RuntimeError("boom"),
    ]
    service = _new_service(client)

    files = await service.get_files(parent="0", page_size=1, only_video=False)

    assert [item.fid for item in files] == ["1"]
    assert len(client.request_calls) == 2


@pytest.mark.asyncio
async def test_get_file_by_path_root_and_not_found_cases() -> None:
    client = FakeClient()
    service = _new_service(client)

    root = await service.get_file_by_path("/")
    assert root.fid == "0"
    assert root.file_name == "/"
    assert root.is_dir is True

    service.get_files = AsyncMock(return_value=[])
    missing = await service.get_file_by_path("Movies/NotExist.mp4")
    assert missing is None


@pytest.mark.asyncio
async def test_get_file_by_path_resolves_from_legacy_fid_prefix() -> None:
    client = FakeClient()
    legacy_fid = "a" * 32
    client.file_info_map[legacy_fid] = {
        "fid": legacy_fid,
        "file_name": "LegacyDir",
        "file_type": 0,
        "category": 0,
    }
    service = _new_service(client)

    legacy_child = QuarkService._file_model_from_info(
        {"fid": "child-1", "file_name": "Movie.mp4", "file_type": 1, "category": 1}
    )
    service.get_files = AsyncMock(return_value=[legacy_child])

    result = await service.get_file_by_path(f"{legacy_fid}/Movie.mp4")

    assert result is not None
    assert result.fid == "child-1"


@pytest.mark.asyncio
async def test_get_full_path_by_fid_builds_path_and_handles_loops() -> None:
    client = FakeClient()
    client.file_info_map = {
        "f2": {"fid": "f2", "file_name": "Movie.mp4", "pdir_fid": "f1"},
        "f1": {"fid": "f1", "file_name": "Folder", "pdir_fid": "0"},
        "loop": {"fid": "loop", "file_name": "Loop", "pdir_fid": "loop"},
    }
    service = _new_service(client)

    full_path = await service.get_full_path_by_fid("f2")
    assert full_path == "Folder/Movie.mp4"

    loop_path = await service.get_full_path_by_fid("loop")
    assert loop_path == "Loop"


@pytest.mark.asyncio
async def test_get_download_and_transcoding_links() -> None:
    client = FakeClient()
    service = _new_service(client)

    link = await service.get_download_link("fid-1")
    assert link.url == "https://download.example.com/video.mp4"
    assert link.headers["Cookie"] == "updated-cookie"
    assert link.headers["Referer"] == "https://pan.quark.cn/"
    assert service.cookie == "updated-cookie"

    transcoding = await service.get_transcoding_link("fid-1")
    assert transcoding.url.endswith("/fid-1")
    assert transcoding.part_size == 10 * 1024 * 1024


@pytest.mark.asyncio
async def test_list_files_unescapes_names_and_raises_on_failure() -> None:
    client = FakeClient()
    client.request_responses = [
        {
            "data": {
                "list": [{"file_name": "Tom &amp; Jerry.mp4", "file_type": 1}],
                "metadata": {"total": 1},
            }
        }
    ]
    service = _new_service(client)

    result = await service.list_files()
    assert result["list"][0]["file_name"] == "Tom & Jerry.mp4"

    client.request_responses = [RuntimeError("request failed")]
    with pytest.raises(RuntimeError, match="request failed"):
        await service.list_files()


@pytest.mark.asyncio
async def test_rename_file_skip_verify_success_and_failure_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())
    client = FakeClient()
    service = _new_service(client)

    # Skip path: same name
    client.file_info_map["f1"] = {"fid": "f1", "file_name": "Movie.mp4"}
    skipped = await service.rename_file("f1", "Movie.mp4")
    assert skipped["status"] == "skipped"
    assert skipped["changed"] is False
    assert client.rename_calls == []

    # Success path: name changes and verification passes
    verify_states = iter(
        [
            {"fid": "f2", "file_name": "Old.mp4"},
            {"fid": "f2", "file_name": "New.mp4"},
        ]
    )

    async def dynamic_get_file_info(fid: str) -> dict[str, Any]:
        if fid == "f2":
            return next(verify_states)
        return {}

    client.get_file_info = dynamic_get_file_info  # type: ignore[assignment]
    renamed = await service.rename_file("f2", "New.mp4")
    assert renamed["status"] == "success"
    assert renamed["verified"] is True
    assert renamed["changed"] is True
    assert client.rename_calls[-1] == ("f2", "New.mp4")

    # Verification failure path
    async def never_match(_fid: str) -> dict[str, Any]:
        return {"fid": "f3", "file_name": "StillOld.mp4"}

    client.get_file_info = never_match  # type: ignore[assignment]
    with pytest.raises(Exception, match="rename verification failed"):
        await service.rename_file("f3", "Target.mp4")


@pytest.mark.asyncio
async def test_move_delete_mkdir_and_close_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())
    client = FakeClient()
    service = _new_service(client)

    moved = await service.move_file("f1", "dir-1")
    assert moved == {"fid": "f1", "to_pdir_fid": "dir-1", "status": "success"}
    assert client.move_calls == [(("f1",), "dir-1")]

    await service.delete_file("f1")
    assert client.delete_calls == [("f1",)]

    mkdir_result = await service.mkdir("0", "NewFolder")
    assert mkdir_result["fid"] == "new-dir"
    assert client.mkdir_calls == [("0", "NewFolder")]

    await service.close()
    assert client.closed is True


@pytest.mark.asyncio
async def test_get_all_video_files_handles_recursion_depth_and_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())
    client = FakeClient()
    service = _new_service(client)

    listing_map = {
        "0": {
            "list": [
                {"fid": "d1", "file_name": "Folder", "file_type": 0},
                {"fid": "v1", "file_name": "movie.mp4", "file_type": 1},
                {"fid": "a1", "file_name": "audio.mp3", "file_type": 1},
            ]
        },
        "d1": {
            "list": [
                {"fid": "v2", "file_name": "episode.mkv", "file_type": 1},
                {"fid": "d2", "file_name": "Nested", "file_type": 0},
            ]
        },
    }

    async def fake_list_files(pdir_fid: str = "0", page: int = 1, size: int = 100) -> dict[str, Any]:
        if pdir_fid == "d2":
            raise RuntimeError("scan failed")
        return listing_map.get(pdir_fid, {"list": []})

    service.list_files = fake_list_files  # type: ignore[assignment]

    videos = await service.get_all_video_files(pdir_fid="0", recursive=True, max_files=10)
    assert sorted(item["fid"] for item in videos) == ["v1", "v2"]

    # Depth protection path
    async def deep_list_files(pdir_fid: str = "0", page: int = 1, size: int = 100) -> dict[str, Any]:
        return {"list": [{"fid": f"{pdir_fid}-next", "file_name": "Dir", "file_type": 0}]}

    service.list_files = deep_list_files  # type: ignore[assignment]
    deep_videos = await service.get_all_video_files(pdir_fid="root", recursive=True, max_files=5)
    assert deep_videos == []


def test_is_video_file_delegates_to_shared_helper() -> None:
    service = _new_service(FakeClient())
    assert service.is_video_file("movie.mkv") is True
    assert service.is_video_file("document.txt") is False
