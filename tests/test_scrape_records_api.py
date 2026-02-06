from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.scrape import (
    RecordIdsRequest,
    clear_failed_records,
    get_scrape_record,
    list_scrape_records,
    re_scrape_records,
    truncate_all_records,
)
from app.core.db import Base
from app.models.scrape import ScrapeRecord


def _build_session(tmp_path: Path):
    db_file = tmp_path / "records_api.db"
    engine = create_engine(
        f"sqlite:///{db_file}",
        connect_args={"check_same_thread": False},
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    return SessionLocal


@pytest.mark.asyncio
async def test_scrape_records_query_and_bulk_actions(tmp_path: Path):
    SessionLocal = _build_session(tmp_path)
    db = SessionLocal()
    try:
        marker = str(uuid.uuid4())
        failed_record = ScrapeRecord(
            record_id=str(uuid.uuid4()),
            job_id="job-1",
            source_file=f"{marker}-failed.mkv",
            status="scrape_failed",
            error_code="SCRAPE_FAIL",
            error_message="scrape failure",
            recognition_result={"title": "Failed Movie"},
        )
        failed_record_2 = ScrapeRecord(
            record_id=str(uuid.uuid4()),
            job_id="job-1",
            source_file=f"{marker}-rename.mkv",
            status="rename_failed",
            error_code="RENAME_FAIL",
            error_message="rename failure",
            recognition_result={"title": "Rename Movie"},
        )
        success_record = ScrapeRecord(
            record_id=str(uuid.uuid4()),
            job_id="job-1",
            source_file=f"{marker}-ok.mkv",
            status="renamed",
            recognition_result={"title": "OK Movie"},
        )
        db.add_all([failed_record, failed_record_2, success_record])
        db.commit()

        records = await list_scrape_records(
            keyword=marker,
            status=None,
            page=1,
            size=20,
            db=db,
        )
        assert records.total == 3
        assert len(records.items) == 3

        detail = await get_scrape_record(record_id=failed_record.record_id, db=db)
        assert detail.error_code == "SCRAPE_FAIL"
        assert detail.error_message == "scrape failure"

        rescrape_result = await re_scrape_records(
            body=RecordIdsRequest(record_ids=[failed_record.record_id]),
            _auth=None,
            db=db,
        )
        assert rescrape_result["requested"] == 1
        assert rescrape_result["updated"] == 1
        db.refresh(failed_record)
        assert failed_record.status == "pending"
        assert failed_record.error_code is None
        assert failed_record.error_message is None

        clear_result = await clear_failed_records(_auth=None, db=db)
        assert clear_result["cleared"] == 1

        truncate_result = await truncate_all_records(_auth=None, db=db)
        assert truncate_result["truncated"] == 2
        assert db.query(ScrapeRecord).count() == 0
    finally:
        db.close()

