"""
Token 监控与保活服务

定期检查夸克 Cookie 的有效性，并在失效时发出警告。
由于目前配置仅包含 Cookie 而无账号密码，我们无法自动执行重新登录流程，
只能通过定期访问 API 来尝试延长 Session 有效期（如果服务器支持），
或者及时通知用户手动更新。
"""

import asyncio

from app.core.logging import get_logger
from app.services.config_service import get_config_service
from app.services.notification_service import NotificationPriority, NotificationType, get_notification_service
from app.services.quark_service import QuarkService


logger = get_logger(__name__)


def get_quark_cookie() -> str | None:
    app_config = get_config_service().get_config()
    quark_config = getattr(app_config, "quark", None)
    return getattr(quark_config, "cookie", None)


class TokenMonitor:
    def __init__(self):
        self.notifier = get_notification_service()

    async def check_token(self) -> bool:
        """
        检查 Token 有效性

        Returns:
            bool: Token 是否有效
        """
        cookie = get_quark_cookie()
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
            error_msg = f"Quark Cookie check failed: {e}"
            logger.error(f"TokenMonitor: {error_msg}")

            # 发送系统告警通知
            try:
                await self.notifier.send_notification(
                    type=NotificationType.SYSTEM_ALERT,
                    title="🚨 夸克 Token 失效",
                    content=f"检测到 Quark Cookie 可能已失效，请及时更新。\n错误信息: {e!s}",
                    priority=NotificationPriority.HIGH,
                )
            except Exception as notify_error:
                logger.error(f"Failed to send token expiration notification: {notify_error}")

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
