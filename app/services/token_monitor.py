"""
Token 监控与保活服务

定期检查夸克 Cookie 的有效性，并在失效时发出警告。
由于目前配置仅包含 Cookie 而无账号密码，我们无法自动执行重新登录流程，
只能通过定期访问 API 来尝试延长 Session 有效期（如果服务器支持），
或者及时通知用户手动更新。
"""

import asyncio
from app.services.quark_service import QuarkService
from app.core.config_manager import get_config
from app.core.logging import get_logger

logger = get_logger(__name__)

class TokenMonitor:
    def __init__(self):
        self.config = get_config()
    
    async def check_token(self) -> bool:
        """
        检查 Token 有效性
        
        Returns:
            bool: Token 是否有效
        """
        cookie = self.config.get_quark_cookie()
        if not cookie:
            logger.warning("TokenMonitor: No cookie configured")
            return False
            
        service = None
        try:
            service = QuarkService(cookie=cookie)
            # 尝试访问根目录，轻量级操作
            await service.list_files(pdir_fid="0", page=1, size=1)
            logger.info("TokenMonitor: Cookie is valid")
            return True
        except Exception as e:
            logger.error(f"TokenMonitor: Cookie check failed: {e}")
            # 这里可以集成通知服务 (Telegram/WeChat)
            return False
        finally:
            if service:
                await service.close()

    async def start_monitor_loop(self, interval_seconds: int = 3600):
        """启动监控循环"""
        logger.info(f"Starting TokenMonitor loop (interval: {interval_seconds}s)")
        while True:
            await self.check_token()
            await asyncio.sleep(interval_seconds)
