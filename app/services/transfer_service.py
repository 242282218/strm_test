import re
from typing import Optional, List
from app.services.cloud_drive_service import CloudDriveService
from app.services.quark_service import QuarkService
from app.services.config_service import get_config_service

from app.core.logging import get_logger

logger = get_logger(__name__)

class TransferService:
    def __init__(self, db_session):
        self.db = db_session
        self.cloud_drive_service = CloudDriveService(db_session)

    async def transfer_share(
        self, 
        drive_id: Optional[int],
        share_url: str, 
        target_dir: str, 
        password: str = "",
        auto_organize: bool = False,
        background_tasks = None
    ):
        # 1. 解析 share_url
        pwd_id = self._extract_pwd_id(share_url)
        if not pwd_id:
            raise ValueError("Invalid share URL")

        # 2. Resolve cookie source.
        # Priority: explicit cloud drive account > global quark cookie in config.
        cookie = ""
        if drive_id is not None:
            drive = self.cloud_drive_service.get_drive(drive_id)
            if not drive:
                raise ValueError(f"Drive {drive_id} not found")
            if drive.drive_type != "quark":
                raise ValueError("Only quark drive is supported for transfer")
            cookie = (drive.cookie or "").strip()
            if not cookie:
                raise ValueError(f"Drive {drive_id} cookie is empty")
        else:
            config = get_config_service().get_config()
            cookie = (config.quark.cookie or "").strip() if config and config.quark else ""
            if not cookie:
                raise ValueError("No quark drive configured and quark.cookie is empty")

        quark_service = QuarkService(cookie)
        
        try:
            # 3. Get share token
            stoken = await quark_service.client.get_share_token(pwd_id, password)
            if not stoken:
                logger.warning(f"Could not get stoken for {pwd_id}, trying without it (or empty)")

            # 4. Get share files (to get fid_list)
            # 默认转存根目录下的所有内容
            files = await quark_service.client.get_share_files(pwd_id, stoken)
            if not files:
                raise ValueError("No files found in share")
            
            fid_list = [f["fid"] for f in files]
            
            # 5. Get target fid
            target_file = await quark_service.get_file_by_path(target_dir)
            if not target_file:
                 raise ValueError(f"Target directory {target_dir} not found")
            if not target_file.is_dir:
                 raise ValueError(f"Target path {target_dir} is not a directory")
            
            target_fid = target_file.fid
            
            # 6. Save
            await quark_service.client.save_share(pwd_id, stoken, fid_list, target_fid)
            logger.info(f"Transferred share {pwd_id} to {target_dir}")
            
            # 7. Auto Organize
            if auto_organize:
                if drive_id is None:
                    logger.warning("Auto-organize skipped because drive_id is missing")
                    return

                from app.services.task_queue_service import TaskService
                from app.schemas.task import TaskCreate
                from app.services.task_runner import TaskRunner
                
                task_service = TaskService(self.db)
                task_in = TaskCreate(
                    task_type="strm_generation",
                    params={
                        "drive_id": drive_id,
                        "source_dir": target_dir,
                        "target_dir": "data/media", # 默认
                        "media_type": "auto"
                    }
                )
                task = task_service.create_task(task_in)
                
                if background_tasks:
                    background_tasks.add_task(TaskRunner.run_task, task.id)
                else:
                    logger.warning("Background tasks handler not provided, auto-organize task created but not started immediately")
        finally:
            await quark_service.close()

    def _extract_pwd_id(self, url: str) -> Optional[str]:
        # Supported formats:
        # https://pan.quark.cn/s/abcdef123456
        match = re.search(r'/s/([a-zA-Z0-9]+)', url)
        if match:
            return match.group(1)
        # Maybe handle raw pwd_id input
        if re.match(r'^[a-zA-Z0-9]{12,32}$', url):
            return url
        return None
