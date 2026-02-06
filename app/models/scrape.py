from sqlalchemy import Column, Integer, String, Float, DateTime, Text, JSON, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.db import Base

class ScrapePath(Base):
    """Scrape path configuration."""
    __tablename__ = "scrape_paths"

    id = Column(Integer, primary_key=True, index=True)
    path_id = Column(String(50), unique=True, index=True, nullable=False)
    source_path = Column(String(500), nullable=False, index=True)
    dest_path = Column(String(500), nullable=False)
    media_type = Column(String(20), default="auto", nullable=False)
    scrape_mode = Column(String(30), default="scrape_and_rename", nullable=False)
    rename_mode = Column(String(20), default="move", nullable=False)
    max_threads = Column(Integer, default=1, nullable=False)
    cron = Column(String(120))
    enabled = Column(Boolean, default=True, nullable=False)
    cron_enabled = Column(Boolean, default=False, nullable=False)
    enable_secondary_category = Column(Boolean, default=True, nullable=False)
    status = Column(String(20), default="idle", nullable=False)
    last_job_id = Column(String(50))
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class ScrapeRecord(Base):
    """Operational records for scrape pipeline."""
    __tablename__ = "scrape_records"

    id = Column(Integer, primary_key=True, index=True)
    record_id = Column(String(50), unique=True, index=True, nullable=False)
    job_id = Column(String(50), index=True, nullable=False)
    path_id = Column(String(50), index=True)
    item_id = Column(Integer, index=True)
    source_file = Column(String(500), nullable=False, index=True)
    target_file = Column(String(500))
    media_type = Column(String(20), index=True)
    tmdb_id = Column(Integer, index=True)
    title = Column(String(200), index=True)
    year = Column(Integer)
    status = Column(String(30), index=True, nullable=False, default="pending")
    error_code = Column(String(80))
    error_message = Column(Text)
    recognition_result = Column(JSON)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class CategoryStrategy(Base):
    """Secondary category strategy configuration."""
    __tablename__ = "category_strategy"

    id = Column(Integer, primary_key=True, index=True)
    enabled = Column(Boolean, default=True, nullable=False)
    anime_keywords = Column(JSON, nullable=False, default=list)
    folder_names = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class ScrapeJob(Base):
    """刮削任务"""
    __tablename__ = "scrape_jobs"
    
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String(50), unique=True, index=True, nullable=False)
    target_path = Column(String(500), nullable=False)
    media_type = Column(String(20), nullable=False)  # movie/tv/auto
    status = Column(String(20), default="pending")  # pending/running/completed/failed/cancelled
    total_items = Column(Integer, default=0)
    processed_items = Column(Integer, default=0)
    success_items = Column(Integer, default=0)
    failed_items = Column(Integer, default=0)
    options = Column(JSON)  # 刮削选项
    created_at = Column(DateTime, server_default=func.now())
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    error_message = Column(Text)
    
    items = relationship("ScrapeItem", back_populates="job", cascade="all, delete-orphan")

class ScrapeItem(Base):
    """刮削项目"""
    __tablename__ = "scrape_items"
    
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String(50), ForeignKey("scrape_jobs.job_id"), nullable=False)
    file_id = Column(String(100)) # 夸克文件ID
    file_path = Column(String(500), nullable=False)
    file_name = Column(String(200), nullable=False)
    media_type = Column(String(20)) # movie/episode
    status = Column(String(20), default="pending") # pending/matched/scraped/failed
    
    # 识别结果
    tmdb_id = Column(Integer, index=True)
    title = Column(String(200))
    original_title = Column(String(200))
    year = Column(Integer)
    season = Column(Integer)
    episode = Column(Integer)
    
    # 刮削结果 (路径)
    nfo_path = Column(String(500))
    poster_path = Column(String(500))
    fanart_path = Column(String(500))
    
    confidence = Column(Float, default=0) # 匹配置信度
    error_message = Column(Text)
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
    
    job = relationship("ScrapeJob", back_populates="items")

class RenameHistory(Base):
    """重命名历史"""
    __tablename__ = "rename_history"
    
    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(String(50), ForeignKey("rename_batches.batch_id"), index=True, nullable=False)
    file_id = Column(String(100), index=True, nullable=False) # 夸克文件ID或本地路径hash
    original_path = Column(String(500), nullable=False)
    original_name = Column(String(200), nullable=False)
    new_path = Column(String(500))
    new_name = Column(String(200))
    status = Column(String(20), default="pending") # pending/success/failed/rolled_back
    
    # 辅助信息
    tmdb_id = Column(Integer)
    confidence = Column(Float)
    error_message = Column(Text)
    
    created_at = Column(DateTime, server_default=func.now())
    executed_at = Column(DateTime)
    rolled_back_at = Column(DateTime)
    
    batch = relationship("RenameBatch", back_populates="items")


class RenameBatch(Base):
    """重命名批次"""
    __tablename__ = "rename_batches"
    
    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(String(50), unique=True, index=True, nullable=False)
    target_path = Column(String(500), nullable=False)
    media_type = Column(String(20), default="auto")  # auto/movie/tv
    total_items = Column(Integer, default=0)
    success_items = Column(Integer, default=0)
    failed_items = Column(Integer, default=0)
    skipped_items = Column(Integer, default=0)
    status = Column(String(20), default="pending")  # pending/previewing/executing/completed/failed/rolled_back
    options = Column(JSON)
    
    created_at = Column(DateTime, server_default=func.now())
    executed_at = Column(DateTime)
    completed_at = Column(DateTime)
    
    items = relationship("RenameHistory", back_populates="batch", cascade="all, delete-orphan")
