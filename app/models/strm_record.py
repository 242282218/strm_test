from sqlalchemy import Column, DateTime, String
from sqlalchemy.sql import func

from app.core.db import Base


class StrmRecord(Base):
    __tablename__ = "strm"

    key = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    local_dir = Column(String, nullable=False)
    remote_dir = Column(String, nullable=False, index=True)
    raw_url = Column(String, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class ScanRecord(Base):
    __tablename__ = "records"

    remote_dir = Column(String, primary_key=True, index=True)
    last_scan = Column(DateTime, server_default=func.now(), onupdate=func.now())
