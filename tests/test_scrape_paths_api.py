from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.core.db import Base, engine
from app.main import app
from app.services.scrape_service import get_scrape_service

Base.metadata.create_all(bind=engine)
client = TestClient(app)


def test_scrape_paths_crud_and_actions(tmp_path: Path):
    source = tmp_path / "source"
    dest = tmp_path / "dest"
    source.mkdir(parents=True)
    dest.mkdir(parents=True)
    (source / "Movie.Name.2024.1080p.mkv").write_bytes(b"movie")

    create_resp = client.post(
        "/api/scrape/pathes",
        json={
            "source_path": str(source),
            "dest_path": str(dest),
            "media_type": "auto",
            "scrape_mode": "scrape_and_rename",
            "rename_mode": "copy",
            "max_threads": 2,
            "cron": "*/5 * * * *",
            "enabled": True,
            "enable_secondary_category": True,
        },
    )
    assert create_resp.status_code == 200
    path_id = create_resp.json()["path_id"]

    list_resp = client.get("/api/scrape/pathes", params={"keyword": str(source)})
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] >= 1

    get_resp = client.get(f"/api/scrape/pathes/{path_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["path_id"] == path_id

    update_resp = client.put(
        f"/api/scrape/pathes/{path_id}",
        json={
            "max_threads": 4,
            "rename_mode": "move",
        },
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["max_threads"] == 4
    assert update_resp.json()["rename_mode"] == "move"

    service = get_scrape_service()
    original_scrape = service._scrape_single_item

    async def _slow_scrape(item, options):
        import asyncio

        await asyncio.sleep(0.35)
        return await original_scrape(item, options)

    service._scrape_single_item = _slow_scrape  # type: ignore[assignment]
    try:
        start_resp = client.post("/api/scrape/pathes/start", json={"path_id": path_id})
        assert start_resp.status_code == 200
        start_data = start_resp.json()
        assert start_data["ok"] is True
        assert start_data["path_id"] == path_id
        assert "job_id" in start_data

        second_start_resp = client.post("/api/scrape/pathes/start", json={"path_id": path_id})
        assert second_start_resp.status_code == 200
        second_data = second_start_resp.json()
        assert second_data["ok"] is True
        assert "already_running" in second_data
        assert "job_id" in second_data
    finally:
        service._scrape_single_item = original_scrape  # type: ignore[assignment]

    toggle_on_resp = client.post(
        "/api/scrape/pathes/toggle-cron",
        json={"path_id": path_id, "enabled": True},
    )
    assert toggle_on_resp.status_code == 200
    assert toggle_on_resp.json()["cron_enabled"] is True

    toggle_off_resp = client.post(
        "/api/scrape/pathes/toggle-cron",
        json={"path_id": path_id, "enabled": False},
    )
    assert toggle_off_resp.status_code == 200
    assert toggle_off_resp.json()["cron_enabled"] is False

    stop_resp = client.post("/api/scrape/pathes/stop", json={"path_id": path_id})
    assert stop_resp.status_code == 200
    assert stop_resp.json()["path_id"] == path_id
    assert stop_resp.json()["stopped"] is True

    delete_resp = client.delete(f"/api/scrape/pathes/{path_id}")
    assert delete_resp.status_code == 200
    assert delete_resp.json()["deleted"] is True
