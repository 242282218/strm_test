import asyncio
from datetime import datetime

import aiosqlite
import pytest
from unittest.mock import AsyncMock

from app.services import disk_cache as disk_cache_mod


class BrokenConnection:
    async def __aenter__(self):
        raise RuntimeError("db unavailable")

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest.fixture(autouse=True)
def reset_global_disk_cache():
    disk_cache_mod._global_disk_cache = None
    yield
    disk_cache_mod._global_disk_cache = None


def test_serialize_and_deserialize_roundtrip(tmp_path):
    cache = disk_cache_mod.DiskCache(db_path=str(tmp_path / "cache.db"))

    data, value_type = cache._serialize({"name": "disk"})
    assert value_type == "json"
    assert cache._deserialize(data, value_type) == {"name": "disk"}

    data, value_type = cache._serialize({"set-value"})
    assert value_type == "pickle"
    assert cache._deserialize(data, value_type) == {"set-value"}


@pytest.mark.asyncio
async def test_start_stop_and_periodic_cleanup_loop(monkeypatch, tmp_path):
    cache = disk_cache_mod.DiskCache(db_path=str(tmp_path / "cache.db"), cleanup_interval=1)

    await cache.start()
    assert cache._cleanup_task is not None
    await cache.stop()
    assert cache._cleanup_task.done() is True

    sleep_calls = {"value": 0}

    async def fake_sleep(_seconds):
        sleep_calls["value"] += 1
        if sleep_calls["value"] >= 3:
            raise asyncio.CancelledError()
        return None

    monkeypatch.setattr(disk_cache_mod.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(cache, "cleanup_expired", AsyncMock(side_effect=[2, RuntimeError("cleanup failed")]))

    await cache._periodic_cleanup()
    assert cache.cleanup_expired.await_count == 2


@pytest.mark.asyncio
async def test_basic_crud_and_stats(tmp_path):
    cache = disk_cache_mod.DiskCache(db_path=str(tmp_path / "cache.db"), default_ttl=30)

    assert await cache.set("k1", {"v": 1}, ttl=10) is True
    assert await cache.get("k1") == {"v": 1}
    assert await cache.exists("k1") is True

    stats = await cache.get_stats()
    assert stats["total_entries"] == 1
    assert stats["expired_entries"] == 0
    assert stats["db_size_bytes"] > 0

    assert await cache.delete("k1") is True
    assert await cache.delete("k1") is False
    assert await cache.clear() is True


@pytest.mark.asyncio
async def test_expired_entry_paths(tmp_path):
    cache = disk_cache_mod.DiskCache(db_path=str(tmp_path / "cache.db"), default_ttl=0)
    now = datetime.now().timestamp()

    assert await cache.set("expired_on_get", "value", ttl=5) is True
    async with aiosqlite.connect(cache.db_path) as db:
        await db.execute("UPDATE cache_entries SET expires_at = ? WHERE key = ?", (now - 10, "expired_on_get"))
        await db.commit()

    assert await cache.get("expired_on_get") is None
    assert await cache.exists("expired_on_get") is False

    assert await cache.set("expired_cleanup", "value", ttl=5) is True
    assert await cache.set("alive", "value", ttl=None) is True
    async with aiosqlite.connect(cache.db_path) as db:
        await db.execute("UPDATE cache_entries SET expires_at = ? WHERE key = ?", (now - 1, "expired_cleanup"))
        await db.commit()

    assert await cache.cleanup_expired() == 1
    assert await cache.exists("alive") is True


@pytest.mark.asyncio
async def test_get_many_and_set_many_paths(monkeypatch, tmp_path):
    cache = disk_cache_mod.DiskCache(db_path=str(tmp_path / "cache.db"), default_ttl=120)
    now = datetime.now().timestamp()

    assert await cache.get_many([]) == {}
    assert await cache.set_many({}, ttl=10) == 0

    inserted = await cache.set_many({"k1": {"v": 1}, "k2": "value"}, ttl=60)
    assert inserted == 2
    assert await cache.get_many(["k1", "k2", "missing"]) == {"k1": {"v": 1}, "k2": "value"}

    async with aiosqlite.connect(cache.db_path) as db:
        await db.execute(
            """INSERT OR REPLACE INTO cache_entries
               (key, value, value_type, created_at, expires_at, last_access)
               VALUES (?, ?, ?, ?, ?, ?)""",
            ("bad-json", b"not-json", "json", now, now + 60, now),
        )
        await db.execute("UPDATE cache_entries SET expires_at = ? WHERE key = ?", (now - 1, "k2"))
        await db.commit()

    result = await cache.get_many(["k1", "k2", "bad-json"])
    assert result == {"k1": {"v": 1}}

    original_serialize = cache._serialize

    def flaky_serialize(value):
        if value == "boom":
            raise ValueError("cannot serialize")
        return original_serialize(value)

    monkeypatch.setattr(cache, "_serialize", flaky_serialize)
    assert await cache.set_many({"ok": 1, "bad": "boom"}, ttl=30) == 1


@pytest.mark.asyncio
async def test_methods_return_fallback_on_db_errors(monkeypatch, tmp_path):
    cache = disk_cache_mod.DiskCache(db_path=str(tmp_path / "cache.db"))
    monkeypatch.setattr(disk_cache_mod.aiosqlite, "connect", lambda *_args, **_kwargs: BrokenConnection())

    assert await cache.get("k") is None
    assert await cache.set("k", "v") is False
    assert await cache.delete("k") is False
    assert await cache.clear() is False
    assert await cache.cleanup_expired() == 0
    assert await cache.exists("k") is False
    assert await cache.get_many(["k"]) == {}
    assert await cache.set_many({"k": "v"}) == 0

    stats = await cache.get_stats()
    assert "error" in stats


@pytest.mark.asyncio
async def test_global_disk_cache_singleton(tmp_path):
    first = disk_cache_mod.get_disk_cache(db_path=str(tmp_path / "first.db"), default_ttl=77)
    second = disk_cache_mod.get_disk_cache(db_path=str(tmp_path / "second.db"), default_ttl=11)

    assert first is second
    assert first.db_path == tmp_path / "first.db"
    assert first.default_ttl == 77
