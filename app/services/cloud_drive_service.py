from datetime import datetime

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.cloud_drive import CloudDrive
from app.schemas.cloud_drive import CloudDriveCreate, CloudDriveUpdate
from app.services.quark_service import QuarkService


logger = get_logger(__name__)


class CloudDriveService:
    def __init__(self, db: Session):
        self.db = db

    def get_drives(self, skip: int = 0, limit: int = 100):
        return self.db.query(CloudDrive).offset(skip).limit(limit).all()

    def get_drive(self, drive_id: int):
        return self.db.query(CloudDrive).filter(CloudDrive.id == drive_id).first()

    def get_default_drive(self):
        """获取默认可用网盘（优先 active 的 quark）"""
        return (
            self.db.query(CloudDrive)
            .filter(CloudDrive.drive_type == "quark")
            .order_by((CloudDrive.status == "active").desc(), CloudDrive.id.asc())
            .first()
        )

    def create_drive(self, drive: CloudDriveCreate) -> CloudDrive:
        db_drive = CloudDrive(name=drive.name, drive_type=drive.drive_type, cookie=drive.cookie, remark=drive.remark)
        self.db.add(db_drive)
        self.db.commit()
        self.db.refresh(db_drive)
        return db_drive

    def update_drive(self, drive_id: int, drive_update: CloudDriveUpdate) -> CloudDrive:
        db_drive = self.get_drive(drive_id)
        if not db_drive:
            return None

        update_data = drive_update.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_drive, key, value)

        self.db.commit()
        self.db.refresh(db_drive)
        return db_drive

    def delete_drive(self, drive_id: int) -> bool:
        db_drive = self.get_drive(drive_id)
        if not db_drive:
            return False

        self.db.delete(db_drive)
        self.db.commit()
        return True

    async def check_cookie(self, drive_id: int) -> bool:
        """检查Cookie有效性"""
        db_drive = self.get_drive(drive_id)
        if not db_drive:
            return False

        if db_drive.drive_type != "quark":
            # 暂时只支持夸克
            return False

        logger.info(f"Checking cookie for drive {db_drive.name} ({drive_id})")

        # 临时创建 QuarkService 实例进行检测
        # 注意: 这里不依赖全局配置，而是使用账号特定的Cookie
        service = QuarkService(cookie=db_drive.cookie)
        try:
            # 尝试获取根目录，只取1个文件，最小化开销
            await service.get_files(parent="0", page_size=1)

            db_drive.status = "active"
            db_drive.last_check = datetime.now()
            self.db.commit()
            logger.info(f"Cookie check success for {db_drive.name}")
            return True

        except Exception as e:
            logger.error(f"Cookie check failed for {db_drive.name}: {e}")
            db_drive.status = "expired"
            db_drive.last_check = datetime.now()
            self.db.commit()
            return False
        finally:
            await service.close()
