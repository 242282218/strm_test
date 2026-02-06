from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.db import Base


class EmbyLibrary(Base):
    __tablename__ = "emby_libraries"

    id = Column(Integer, primary_key=True, index=True)
    emby_id = Column(String(50), unique=True, index=True)
    name = Column(String(100))
    path = Column(String(500))
    last_sync_at = Column(DateTime)
    created_at = Column(DateTime, server_default=func.now())

    items = relationship("EmbyMediaItem", back_populates="library")


class EmbyMediaItem(Base):
    __tablename__ = "emby_media_items"

    id = Column(Integer, primary_key=True, index=True)
    emby_id = Column(String(50), unique=True, index=True)
    library_id = Column(Integer, ForeignKey("emby_libraries.id"))
    name = Column(String(200))
    type = Column(String(50))
    path = Column(String(500))
    pickcode = Column(String(100), index=True)
    is_strm = Column(Boolean, default=False)
    sync_status = Column(String(20), default="synced")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    library = relationship("EmbyLibrary", back_populates="items")


class EmbyEventLog(Base):
    __tablename__ = "emby_event_logs"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(String(50), unique=True, index=True, nullable=False)
    event_type = Column(String(50), index=True, nullable=False)
    item_id = Column(String(100), index=True)
    item_name = Column(String(300))
    item_type = Column(String(50), index=True)
    aggregated_count = Column(Integer, default=1, nullable=False)
    payload = Column(JSON)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class EmbyDeletePlan(Base):
    __tablename__ = "emby_delete_plans"

    id = Column(Integer, primary_key=True, index=True)
    plan_id = Column(String(50), unique=True, index=True, nullable=False)
    source = Column(String(50), default="manual", nullable=False)
    dry_run = Column(Boolean, default=True, nullable=False)
    executed = Column(Boolean, default=False, nullable=False)
    status = Column(String(30), default="planned", nullable=False)
    request_payload = Column(JSON)
    plan_items = Column(JSON)
    executed_by = Column(String(100))
    executed_at = Column(DateTime)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

