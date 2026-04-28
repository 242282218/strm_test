from pathlib import Path

from app.services.media.files import build_stable_file_id, discover_media_files, find_related_files


def test_discover_media_files_returns_sorted_results(tmp_path: Path) -> None:
    nested = tmp_path / "b_dir"
    nested.mkdir()
    (nested / "episode.mkv").write_text("video")
    (tmp_path / "a_movie.mp4").write_text("video")
    (tmp_path / "notes.txt").write_text("ignore")

    files = discover_media_files(str(tmp_path))

    assert files == sorted(files)
    assert files == [str(tmp_path / "a_movie.mp4"), str(nested / "episode.mkv")]


def test_discover_media_files_respects_non_recursive_scan(tmp_path: Path) -> None:
    nested = tmp_path / "season1"
    nested.mkdir()
    (nested / "episode.mkv").write_text("video")
    (tmp_path / "movie.strm").write_text("video")

    files = discover_media_files(str(tmp_path), recursive=False)

    assert files == [str(tmp_path / "movie.strm")]


def test_find_related_files_returns_sorted_sidecars(tmp_path: Path) -> None:
    video = tmp_path / "sample.mkv"
    video.write_text("video")
    (tmp_path / "sample.srt").write_text("subtitle")
    (tmp_path / "sample.nfo").write_text("metadata")

    related = find_related_files(str(video))

    assert related == [str(tmp_path / "sample.nfo"), str(tmp_path / "sample.srt")]


def test_build_stable_file_id_is_deterministic() -> None:
    left = build_stable_file_id("D:/media/show/file.mkv")
    right = build_stable_file_id("D:/media/show/file.mkv")

    assert left == right
    assert len(left) == 16
