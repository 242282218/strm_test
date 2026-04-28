"""
稳定媒体映射服务
"""

from __future__ import annotations

import uuid
from pathlib import PurePosixPath

from sqlalchemy.orm import Session

from app.core.db import Base, SessionLocal, get_engine
from app.core.logging import get_logger
from app.models.media_mapping import MediaMapping


logger = get_logger(__name__)

DEFAULT_BACKEND_ID = "quark"


class MediaMappingService:
    """管理 media_id <-> provider/source 映射。"""

    def __init__(self, session_factory=SessionLocal):
        self._session_factory = session_factory
        Base.metadata.create_all(bind=get_engine(), tables=[MediaMapping.__table__])

    @staticmethod
    def normalize_source_path(source_path: str | None) -> str:
        raw = (source_path or "").strip().replace("\\", "/")
        if not raw:
            return "/"
        if not raw.startswith("/"):
            raw = "/" + raw
        if len(raw) > 1:
            raw = raw.rstrip("/")
        return raw

    @staticmethod
    def _derive_display_name(source_path: str, provider_file_id: str | None) -> str:
        name = PurePosixPath(source_path).name
        if name:
            return name
        return (provider_file_id or "media").strip() or "media"

    @staticmethod
    def _derive_source_ext(display_name: str) -> str:
        suffix = PurePosixPath(display_name).suffix
        return suffix.lstrip(".")

    @staticmethod
    def build_media_id(backend_id: str, provider_file_id: str | None, source_path: str) -> str:
        key = provider_file_id or source_path
        return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{backend_id}:{key}"))

    def get_by_media_id(self, media_id: str) -> MediaMapping | None:
        with self._session_factory() as db:
            return db.query(MediaMapping).filter(MediaMapping.media_id == media_id).first()

    def get_or_create(
        self,
        *,
        backend_id: str = DEFAULT_BACKEND_ID,
        provider_file_id: str | None,
        source_path: str,
        strm_path: str | None = None,
        display_name: str | None = None,
        source_ext: str | None = None,
    ) -> MediaMapping:
        normalized_source_path = self.normalize_source_path(source_path)
        resolved_display_name = display_name or self._derive_display_name(normalized_source_path, provider_file_id)
        resolved_source_ext = source_ext or self._derive_source_ext(resolved_display_name)

        with self._session_factory() as db:
            mapping = self._find_existing_mapping(
                db=db,
                backend_id=backend_id,
                provider_file_id=provider_file_id,
                source_path=normalized_source_path,
            )
            if mapping is None:
                mapping = MediaMapping(
                    media_id=self.build_media_id(backend_id, provider_file_id, normalized_source_path),
                    backend_id=backend_id,
                    provider_file_id=provider_file_id,
                    source_path=normalized_source_path,
                    display_name=resolved_display_name,
                    source_ext=resolved_source_ext,
                    strm_path=strm_path,
                )
                db.add(mapping)
            else:
                mapping.provider_file_id = provider_file_id or mapping.provider_file_id
                mapping.source_path = normalized_source_path
                mapping.display_name = resolved_display_name
                mapping.source_ext = resolved_source_ext
                if strm_path:
                    mapping.strm_path = strm_path

            db.commit()
            db.refresh(mapping)
            return mapping

    def update_provider_file_id(self, media_id: str, provider_file_id: str) -> MediaMapping | None:
        with self._session_factory() as db:
            mapping = db.query(MediaMapping).filter(MediaMapping.media_id == media_id).first()
            if mapping is None:
                return None
            mapping.provider_file_id = provider_file_id
            db.commit()
            db.refresh(mapping)
            return mapping

    def _find_existing_mapping(
        self,
        *,
        db: Session,
        backend_id: str,
        provider_file_id: str | None,
        source_path: str,
    ) -> MediaMapping | None:
        if provider_file_id:
            mapping = (
                db.query(MediaMapping)
                .filter(
                    MediaMapping.backend_id == backend_id,
                    MediaMapping.provider_file_id == provider_file_id,
                )
                .first()
            )
            if mapping:
                return mapping

        return (
            db.query(MediaMapping)
            .filter(
                MediaMapping.backend_id == backend_id,
                MediaMapping.source_path == source_path,
            )
            .first()
        )
