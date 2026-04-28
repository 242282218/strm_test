"""
首段缓存服务

当前实现聚焦于零偏移有界 Range 请求，使用内存缓存首段字节，减少播放器重复探测带来的上游请求。
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from time import monotonic

from app.services.config_service import get_config_service


@dataclass(slots=True)
class FirstSegmentCacheEntry:
    data: bytes
    total_length: int
    content_type: str
    accept_ranges: str
    etag: str | None
    last_modified: str | None
    expires_at: float


class FirstSegmentCacheService:
    def __init__(self, config_getter=None, time_getter=None):
        self._config_getter = config_getter or (lambda: get_config_service().get_config())
        self._time_getter = time_getter or monotonic
        self._entries: dict[str, FirstSegmentCacheEntry] = {}
        self._lock = Lock()

    def _prune_expired_locked(self, now: float | None = None) -> None:
        current_time = self._time_getter() if now is None else now
        expired_keys = [cache_key for cache_key, entry in self._entries.items() if entry.expires_at <= current_time]
        for cache_key in expired_keys:
            self._entries.pop(cache_key, None)

    def is_enabled(self) -> bool:
        playback_cfg = getattr(self._config_getter(), "playback", None)
        return bool(getattr(playback_cfg, "first_segment_cache_enabled", False)) and self.get_segment_size_bytes() > 0

    def get_segment_size_bytes(self) -> int:
        playback_cfg = getattr(self._config_getter(), "playback", None)
        segment_mb = int(getattr(playback_cfg, "first_segment_cache_mb", 0) or 0)
        return max(0, segment_mb) * 1024 * 1024

    def get_ttl_seconds(self) -> int:
        playback_cfg = getattr(self._config_getter(), "playback", None)
        ttl_sec = int(getattr(playback_cfg, "first_segment_cache_ttl_sec", 0) or 0)
        return max(0, ttl_sec)

    def get(self, cache_key: str) -> FirstSegmentCacheEntry | None:
        if not self.is_enabled():
            return None

        now = self._time_getter()
        with self._lock:
            self._prune_expired_locked(now)
            entry = self._entries.get(cache_key)
            if entry is None:
                return None
            return entry

    def put(
        self,
        cache_key: str,
        *,
        data: bytes,
        total_length: int,
        content_type: str,
        accept_ranges: str,
        etag: str | None,
        last_modified: str | None,
    ) -> None:
        if not self.is_enabled():
            return

        ttl_sec = self.get_ttl_seconds()
        if ttl_sec <= 0 or not data:
            return

        entry = FirstSegmentCacheEntry(
            data=data,
            total_length=total_length,
            content_type=content_type or "application/octet-stream",
            accept_ranges=accept_ranges or "bytes",
            etag=etag,
            last_modified=last_modified,
            expires_at=self._time_getter() + ttl_sec,
        )
        with self._lock:
            self._entries[cache_key] = entry

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

    def get_stats(self) -> dict[str, int | bool]:
        now = self._time_getter()
        with self._lock:
            self._prune_expired_locked(now)
            entry_count = len(self._entries)
            total_bytes = sum(len(entry.data) for entry in self._entries.values())

        return {
            "enabled": self.is_enabled(),
            "entry_count": entry_count,
            "total_bytes": total_bytes,
            "segment_size_bytes": self.get_segment_size_bytes(),
            "ttl_seconds": self.get_ttl_seconds(),
        }


_first_segment_cache_service_singleton = FirstSegmentCacheService()


def get_first_segment_cache_service() -> FirstSegmentCacheService:
    return _first_segment_cache_service_singleton
