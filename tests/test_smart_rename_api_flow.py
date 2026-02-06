"""
Smart rename API contract and execution flow regression tests.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.core.db import SessionLocal
from app.models.scrape import RenameBatch, RenameHistory
from app.services.smart_rename_service import SmartRenameService


client = TestClient(app)


def test_validate_accepts_json_body():
    response = client.post(
        "/api/smart-rename/validate",
        json={"filename": "Movie.Name.2023.mkv"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["filename"] == "Movie.Name.2023.mkv"
    assert "is_valid" in data


def test_execute_with_operations_can_process_needs_confirmation(tmp_path: Path):
    src = tmp_path / "raw-video-name.mkv"
    src.write_text("dummy", encoding="utf-8")

    batch_id = f"ut_{uuid.uuid4().hex[:20]}"
    initial_new_path = tmp_path / "placeholder-name.mkv"
    override_name = "Renamed Video (2023).mkv"
    expected_new_path = tmp_path / override_name

    db = SessionLocal()
    try:
        batch = RenameBatch(
            batch_id=batch_id,
            target_path=str(tmp_path),
            media_type="auto",
            total_items=1,
            status="previewing",
            options={},
        )
        db.add(batch)
        db.add(
            RenameHistory(
                batch_id=batch_id,
                file_id=uuid.uuid4().hex[:16],
                original_path=str(src),
                original_name=src.name,
                new_path=str(initial_new_path),
                new_name=initial_new_path.name,
                status="needs_confirmation",
                confidence=0.2,
            )
        )
        db.commit()
    finally:
        db.close()

    response = client.post(
        "/api/smart-rename/execute",
        json={
            "batch_id": batch_id,
            "operations": [
                {
                    "original_path": str(src),
                    "new_name": override_name,
                }
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total_items"] == 1
    assert body["success_items"] == 1
    assert body["failed_items"] == 0
    assert body["skipped_items"] == 0
    assert expected_new_path.exists()
    assert not src.exists()

    db = SessionLocal()
    try:
        history = db.query(RenameHistory).filter(RenameHistory.batch_id == batch_id).first()
        batch = db.query(RenameBatch).filter(RenameBatch.batch_id == batch_id).first()

        assert history is not None
        assert history.status == "success"
        assert history.new_name == override_name
        assert history.new_path == str(expected_new_path)

        assert batch is not None
        assert batch.status in ("completed", "completed_with_errors")
        assert batch.success_items == 1
        assert batch.failed_items == 0
    finally:
        # Cleanup database test rows.
        db.query(RenameHistory).filter(RenameHistory.batch_id == batch_id).delete()
        db.query(RenameBatch).filter(RenameBatch.batch_id == batch_id).delete()
        db.commit()
        db.close()


def test_normalize_parsed_title_removes_file_extension():
    service = SmartRenameService()
    parsed = {"title": "Unknown_File_abcdefg.mp4"}
    normalized = service._normalize_parsed_title("Unknown_File_abcdefg.mp4", parsed)
    assert normalized["title"] == "Unknown_File_abcdefg"

