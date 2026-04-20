"""
STRM 记录迁移脚本

将原 strm 表数据迁移到新的 strm_records 表
"""

import sqlite3
import sys
from pathlib import Path
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.core.db import SessionLocal, init_db, resolve_db_path
from app.models.strm_record import StrmRecord, ScanRecord
from app.core.logging import get_logger

logger = get_logger(__name__)


def migrate_strm_records():
    """
    迁移 strm 表数据到 strm_records 表
    """
    db_path = resolve_db_path()
    logger.info(f"Starting migration from {db_path}")
    
    # 初始化新表结构
    init_db()
    
    # 连接原数据库
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # 检查原表是否存在
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='strm'")
    if not cursor.fetchone():
        logger.info("No existing strm table found, skipping migration")
        conn.close()
        return
    
    # 读取原表数据
    cursor.execute("SELECT * FROM strm")
    rows = cursor.fetchall()
    logger.info(f"Found {len(rows)} records in strm table")
    
    # 迁移数据到新表
    db = SessionLocal()
    try:
        migrated_count = 0
        skipped_count = 0
        
        for row in rows:
            try:
                # 检查是否已存在
                existing = db.query(StrmRecord).filter(
                    StrmRecord.file_id == row['key']
                ).first()
                
                if existing:
                    skipped_count += 1
                    continue
                
                # 创建新记录
                record = StrmRecord(
                    file_id=row['key'],
                    file_name=row['name'],
                    local_dir=row['local_dir'],
                    remote_dir=row['remote_dir'],
                    raw_url=row['raw_url'],
                    strm_path=None,  # 原表没有此字段
                    created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else datetime.utcnow(),
                    updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else datetime.utcnow(),
                )
                db.add(record)
                migrated_count += 1
                
            except Exception as e:
                logger.error(f"Failed to migrate record {row['key']}: {e}")
        
        db.commit()
        logger.info(f"Migration completed: {migrated_count} migrated, {skipped_count} skipped")
        
    except Exception as e:
        db.rollback()
        logger.error(f"Migration failed: {e}")
        raise
    finally:
        db.close()
    
    conn.close()


def migrate_scan_records():
    """
    迁移 records 表数据到 scan_records 表
    """
    db_path = resolve_db_path()
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # 检查原表是否存在
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='records'")
    if not cursor.fetchone():
        logger.info("No existing records table found, skipping migration")
        conn.close()
        return
    
    # 读取原表数据
    cursor.execute("SELECT * FROM records")
    rows = cursor.fetchall()
    logger.info(f"Found {len(rows)} records in records table")
    
    # 迁移数据
    db = SessionLocal()
    try:
        migrated_count = 0
        
        for row in rows:
            try:
                existing = db.query(ScanRecord).filter(
                    ScanRecord.remote_dir == row['remote_dir']
                ).first()
                
                if existing:
                    continue
                
                record = ScanRecord(
                    remote_dir=row['remote_dir'],
                    last_scan=datetime.fromisoformat(row['last_scan']) if row['last_scan'] else datetime.utcnow(),
                )
                db.add(record)
                migrated_count += 1
                
            except Exception as e:
                logger.error(f"Failed to migrate scan record {row['remote_dir']}: {e}")
        
        db.commit()
        logger.info(f"Scan records migration completed: {migrated_count} migrated")
        
    except Exception as e:
        db.rollback()
        logger.error(f"Scan records migration failed: {e}")
        raise
    finally:
        db.close()
    
    conn.close()


def verify_migration():
    """
    验证迁移结果
    """
    db_path = resolve_db_path()
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 检查新表是否存在
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='strm_records'")
    if cursor.fetchone():
        cursor.execute("SELECT COUNT(*) FROM strm_records")
        count = cursor.fetchone()[0]
        logger.info(f"strm_records table exists with {count} records")
    else:
        logger.warning("strm_records table not found")
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='scan_records'")
    if cursor.fetchone():
        cursor.execute("SELECT COUNT(*) FROM scan_records")
        count = cursor.fetchone()[0]
        logger.info(f"scan_records table exists with {count} records")
    else:
        logger.warning("scan_records table not found")
    
    conn.close()


def run_migration():
    """
    执行完整迁移流程
    """
    logger.info("=" * 50)
    logger.info("Starting database migration")
    logger.info("=" * 50)
    
    try:
        # 迁移 STRM 记录
        migrate_strm_records()
        
        # 迁移扫描记录
        migrate_scan_records()
        
        # 验证迁移
        verify_migration()
        
        logger.info("=" * 50)
        logger.info("Migration completed successfully")
        logger.info("=" * 50)
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    run_migration()
