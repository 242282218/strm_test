from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.scrape import (
    CategoryPreviewRequest,
    CategoryStrategyUpdateRequest,
    get_category_strategy,
    preview_category_strategy,
    update_category_strategy,
)
from app.core.db import Base


def _build_session(tmp_path: Path):
    db_file = tmp_path / "category_strategy.db"
    engine = create_engine(
        f"sqlite:///{db_file}",
        connect_args={"check_same_thread": False},
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    return SessionLocal


@pytest.mark.asyncio
async def test_category_strategy_get_update_preview(tmp_path: Path):
    SessionLocal = _build_session(tmp_path)
    db = SessionLocal()
    try:
        current = await get_category_strategy(db=db)
        assert current.enabled is True
        assert current.folder_names["anime"] == "动漫文件夹"
        assert current.folder_names["movie"] == "电影"
        assert current.folder_names["tv"] == "电视剧"

        updated = await update_category_strategy(
            body=CategoryStrategyUpdateRequest(
                enabled=True,
                anime_keywords=["naruto", "one piece"],
                folder_names={
                    "anime": "动漫文件夹",
                    "movie": "电影",
                    "tv": "电视剧",
                },
            ),
            _auth=None,
            db=db,
        )
        assert "naruto" in [kw.lower() for kw in updated.anime_keywords]

        anime_preview = await preview_category_strategy(
            body=CategoryPreviewRequest(file_name="Naruto.S01E01.1080p.mkv", media_type="auto"),
            db=db,
        )
        assert anime_preview.category_key == "anime"
        assert anime_preview.category_folder == "动漫文件夹"

        movie_preview = await preview_category_strategy(
            body=CategoryPreviewRequest(file_name="Interstellar.2014.1080p.mkv", media_type="movie"),
            db=db,
        )
        assert movie_preview.category_key == "movie"
        assert movie_preview.category_folder == "电影"
    finally:
        db.close()

