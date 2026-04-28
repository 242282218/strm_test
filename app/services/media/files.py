"""
Shared helpers for media file discovery and related-file lookup.
"""

from __future__ import annotations

import hashlib
import os
from typing import Final

from app.core.logging import get_logger


logger = get_logger(__name__)

VIDEO_EXTENSIONS: Final[frozenset[str]] = frozenset(
    {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".ts", ".m2ts", ".strm"}
)
RELATED_EXTENSIONS: Final[frozenset[str]] = frozenset({".nfo", ".jpg", ".png", ".srt", ".ass", ".sub", ".idx", ".sup"})


def build_stable_file_id(path: str) -> str:
    """Build a stable short identifier from a filesystem path."""
    return hashlib.md5(path.encode("utf-8")).hexdigest()[:16]


def is_video_path(path: str, extensions: frozenset[str] = VIDEO_EXTENSIONS) -> bool:
    """Check whether a path points to a supported video file."""
    return os.path.splitext(path)[1].lower() in extensions


def discover_media_files(path: str, recursive: bool = True, extensions: frozenset[str] = VIDEO_EXTENSIONS) -> list[str]:
    """
    Discover media files with deterministic ordering.

    Uses ``os.scandir`` to reduce per-entry overhead and avoids following
    symlinks to keep scans bounded and predictable.
    """
    if not path or not os.path.exists(path):
        return []

    if os.path.isfile(path):
        return [path] if is_video_path(path, extensions) else []

    discovered: list[str] = []
    pending_dirs = [path]

    while pending_dirs:
        current_dir = pending_dirs.pop()
        try:
            with os.scandir(current_dir) as entries:
                for entry in entries:
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            if recursive:
                                pending_dirs.append(entry.path)
                            continue

                        if entry.is_file(follow_symlinks=False) and is_video_path(entry.name, extensions):
                            discovered.append(entry.path)
                    except OSError as exc:
                        logger.debug("Skipping unreadable directory entry %s: %s", entry.path, exc)
        except OSError as exc:
            logger.warning("Skipping unreadable directory %s: %s", current_dir, exc)

    discovered.sort()
    return discovered


def find_related_files(file_path: str, extensions: frozenset[str] = RELATED_EXTENSIONS) -> list[str]:
    """Find sidecar files that share the same basename."""
    base_path = os.path.splitext(file_path)[0]
    related_files = [base_path + ext for ext in sorted(extensions) if os.path.exists(base_path + ext)]
    related_files.sort()
    return related_files
