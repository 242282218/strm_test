from __future__ import annotations

import time
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.db import Base, engine
from app.main import app

Base.metadata.create_all(bind=engine)
client = TestClient(app)


def test_scope5_end_to_end(tmp_path: Path):
    # 1) 刮削目录 -> 启动任务（范围点 1 + 2）
    source = tmp_path / "scope5_source"
    dest = tmp_path / "scope5_dest"
    source.mkdir(parents=True, exist_ok=True)
    dest.mkdir(parents=True, exist_ok=True)
    (source / "Scope5.Movie.2024.1080p.mkv").write_bytes(b"movie")

    create_path = client.post(
        "/api/scrape/pathes",
        json={
            "source_path": str(source),
            "dest_path": str(dest),
            "media_type": "movie",
            "scrape_mode": "scrape_and_rename",
            "rename_mode": "copy",
            "max_threads": 1,
            "cron": None,
            "enabled": True,
            "enable_secondary_category": True,
        },
    )
    assert create_path.status_code == 200
    path_id = create_path.json()["path_id"]

    start = client.post("/api/scrape/pathes/start", json={"path_id": path_id})
    assert start.status_code == 200
    assert start.json()["ok"] is True

    time.sleep(0.8)

    # 2) 刮削记录可查询（范围点 3）
    records = client.get("/api/scrape/records", params={"keyword": "Scope5.Movie", "page": 1, "size": 20})
    assert records.status_code == 200
    assert records.json()["total"] >= 1

    # 3) 二级分类策略预览（范围点 4）
    preview = client.post(
        "/api/scrape/category-strategy/preview",
        json={"file_name": "My.Anime.S01E01.1080p.mkv", "media_type": "auto"},
    )
    assert preview.status_code == 200
    assert preview.json()["category_key"] in {"anime", "movie", "tv"}

    # 4) Emby webhook -> events 可观测（范围点 5）
    webhook = client.post(
        "/api/emby/webhook",
        json={
            "Event": "library.new",
            "Item": {"Id": "scope5-item-1", "Type": "Movie", "Name": "Scope5 Movie"},
        },
    )
    assert webhook.status_code == 200
    assert webhook.json()["status"] == "processed"

    events = client.get("/api/emby/events", params={"keyword": "scope5-item-1", "page": 1, "size": 20})
    assert events.status_code == 200
    assert events.json()["total"] >= 1
