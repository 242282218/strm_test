from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.db import Base
from app.models.scrape import CategoryStrategy, ScrapeItem, ScrapeJob
from app.services.scrape_service import ScrapeService


class _DummyNotificationService:
    async def send_notification(self, **_kwargs):
        return None


class _DummyEmbyService:
    async def refresh_library(self, _library_id=None):
        return True


def _build_service(tmp_path: Path) -> tuple[ScrapeService, sessionmaker]:
    db_file = tmp_path / "test_scrape.db"
    engine = create_engine(
        f"sqlite:///{db_file}",
        connect_args={"check_same_thread": False},
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    service = ScrapeService(
        tmdb_service=None,
        notification_service=_DummyNotificationService(),
        emby_service=_DummyEmbyService(),
        db_session_factory=SessionLocal,
    )
    return service, SessionLocal


async def _wait_job_done(service: ScrapeService, job_id: str, timeout_seconds: float = 15.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        task = service._active_jobs.get(job_id)
        if task is None:
            return
        if task.done():
            await asyncio.gather(task, return_exceptions=True)
            return
        await asyncio.sleep(0.05)
    raise TimeoutError(f"scrape job timeout: {job_id}")


@pytest.mark.asyncio
async def test_scrape_pipeline_movie_and_tv_sample(tmp_path: Path):
    service, SessionLocal = _build_service(tmp_path)
    source_dir = tmp_path / "source"
    dest_dir = tmp_path / "dest"
    source_dir.mkdir(parents=True)
    dest_dir.mkdir(parents=True)

    (source_dir / "Movie.Name.2024.1080p.mkv").write_bytes(b"movie")
    (source_dir / "Show.Name.S01E02.1080p.WEB-DL.mkv").write_bytes(b"episode")

    job = await service.create_job(
        target_path=str(source_dir),
        media_type="auto",
        options={
            "source_path": str(source_dir),
            "dest_path": str(dest_dir),
            "scrape_mode": "scrape_and_rename",
            "rename_mode": "copy",
            "generate_nfo": True,
            "download_images": False,
            "enable_secondary_category": False,
        },
    )
    started = await service.start_job(job.job_id)
    assert started is True
    await _wait_job_done(service, job.job_id)

    db = SessionLocal()
    try:
        stored_job = db.query(ScrapeJob).filter(ScrapeJob.job_id == job.job_id).first()
        assert stored_job is not None
        assert stored_job.status == "completed"
        assert stored_job.success_items == 2
        assert stored_job.failed_items == 0

        items = db.query(ScrapeItem).filter(ScrapeItem.job_id == job.job_id).all()
        assert len(items) == 2
        assert {item.status for item in items} == {"renamed"}
        assert all(item.nfo_path and Path(item.nfo_path).exists() for item in items)
    finally:
        db.close()

    assert (dest_dir / "Movie Name (2024).mkv").exists()
    assert (dest_dir / "Show Name - S01E02.mkv").exists()


@pytest.mark.asyncio
async def test_scrape_modes_only_scrape_and_only_rename(tmp_path: Path):
    service, SessionLocal = _build_service(tmp_path)
    source_dir = tmp_path / "source"
    source_dir.mkdir(parents=True)
    (source_dir / "Movie.Name.2024.1080p.mkv").write_bytes(b"movie")

    only_scrape_job = await service.create_job(
        target_path=str(source_dir),
        options={
            "source_path": str(source_dir),
            "dest_path": str(tmp_path / "only_scrape_dest"),
                "scrape_mode": "only_scrape",
                "generate_nfo": True,
                "download_images": False,
                "enable_secondary_category": False,
            },
        )
    assert await service.start_job(only_scrape_job.job_id) is True
    await _wait_job_done(service, only_scrape_job.job_id)

    db = SessionLocal()
    try:
        item = db.query(ScrapeItem).filter(ScrapeItem.job_id == only_scrape_job.job_id).first()
        assert item is not None
        assert item.status == "scraped"
        assert item.nfo_path and Path(item.nfo_path).exists()
    finally:
        db.close()

    # only_rename should skip NFO generation.
    second_source = tmp_path / "source_only_rename"
    second_source.mkdir(parents=True)
    (second_source / "Show.Name.S01E03.1080p.mkv").write_bytes(b"episode")
    only_rename_dest = tmp_path / "only_rename_dest"

    only_rename_job = await service.create_job(
        target_path=str(second_source),
        options={
            "source_path": str(second_source),
                "dest_path": str(only_rename_dest),
                "scrape_mode": "only_rename",
                "rename_mode": "copy",
                "enable_secondary_category": False,
            },
        )
    assert await service.start_job(only_rename_job.job_id) is True
    await _wait_job_done(service, only_rename_job.job_id)

    db = SessionLocal()
    try:
        item = db.query(ScrapeItem).filter(ScrapeItem.job_id == only_rename_job.job_id).first()
        assert item is not None
        assert item.status == "renamed"
        assert item.nfo_path is None
    finally:
        db.close()

    assert (only_rename_dest / "Show Name - S01E03.mkv").exists()


@pytest.mark.asyncio
async def test_failure_reason_contains_code_and_message(tmp_path: Path):
    class _FailingRenameService(ScrapeService):
        def _organize_item(self, item, options):  # type: ignore[override]
            return False, None, self._standardize_error("RENAME_FAIL", "forced rename failure")

    service, SessionLocal = _build_service(tmp_path)
    failing_service = _FailingRenameService(
        tmdb_service=service.tmdb_service,
        notification_service=service.notification_service,
        emby_service=service.emby_service,
        db_session_factory=SessionLocal,
    )

    source_dir = tmp_path / "source"
    source_dir.mkdir(parents=True)
    (source_dir / "Movie.Name.2024.1080p.mkv").write_bytes(b"movie")

    job = await failing_service.create_job(
        target_path=str(source_dir),
        options={
            "source_path": str(source_dir),
            "dest_path": str(tmp_path / "dest"),
            "scrape_mode": "only_rename",
            "rename_mode": "copy",
        },
    )
    assert await failing_service.start_job(job.job_id) is True
    await _wait_job_done(failing_service, job.job_id)

    db = SessionLocal()
    try:
        item = db.query(ScrapeItem).filter(ScrapeItem.job_id == job.job_id).first()
        assert item is not None
        assert item.status == "rename_failed"
        assert item.error_message is not None
        payload = json.loads(item.error_message)
        assert payload["code"] == "RENAME_FAIL"
        assert payload["message"] == "forced rename failure"
    finally:
        db.close()


@pytest.mark.asyncio
async def test_secondary_category_directory_output(tmp_path: Path):
    service, SessionLocal = _build_service(tmp_path)
    source_dir = tmp_path / "source"
    dest_dir = tmp_path / "dest"
    source_dir.mkdir(parents=True)
    dest_dir.mkdir(parents=True)
    (source_dir / "Movie.Name.2024.1080p.mkv").write_bytes(b"movie")
    (source_dir / "Show.Name.S01E01.1080p.mkv").write_bytes(b"tv")
    (source_dir / "Naruto.S01E01.1080p.mkv").write_bytes(b"anime")

    db = SessionLocal()
    try:
        strategy = CategoryStrategy(
            enabled=True,
            anime_keywords=["naruto"],
            folder_names={
                "anime": "动漫文件夹",
                "movie": "电影",
                "tv": "电视剧",
            },
        )
        db.add(strategy)
        db.commit()
    finally:
        db.close()

    job = await service.create_job(
        target_path=str(source_dir),
        options={
            "source_path": str(source_dir),
            "dest_path": str(dest_dir),
            "scrape_mode": "only_rename",
            "rename_mode": "copy",
            "enable_secondary_category": True,
        },
    )
    assert await service.start_job(job.job_id) is True
    await _wait_job_done(service, job.job_id)

    assert (dest_dir / "电影" / "Movie Name (2024).mkv").exists()
    assert (dest_dir / "电视剧" / "Show Name - S01E01.mkv").exists()
    assert (dest_dir / "动漫文件夹" / "Naruto - S01E01.mkv").exists()


@pytest.mark.asyncio
async def test_start_job_is_idempotent_while_running(tmp_path: Path):
    service, SessionLocal = _build_service(tmp_path)
    source_dir = tmp_path / "source"
    source_dir.mkdir(parents=True)
    (source_dir / "Movie.Name.2024.1080p.mkv").write_bytes(b"movie")

    job = await service.create_job(target_path=str(source_dir))

    calls: list[str] = []
    original_process = service._process_job

    async def _slow_process(job_id: str):
        calls.append(job_id)
        await asyncio.sleep(0.35)
        await original_process(job_id)

    service._process_job = _slow_process  # type: ignore[assignment]
    try:
        first = await service.start_job(job.job_id)
        second = await service.start_job(job.job_id)
        assert first is True
        assert second is True
        await asyncio.sleep(0.05)
        assert len(calls) == 1
        await _wait_job_done(service, job.job_id)
    finally:
        service._process_job = original_process  # type: ignore[assignment]
