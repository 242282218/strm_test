"""
配置管理模块

用于读取和管理YAML配置文件
"""

import os
import threading
from typing import Dict, Any, Optional
from pydantic import ValidationError
from app.core.logging import get_logger
from app.config.settings import AppConfig, AListConfig, WebDAVConfig

logger = get_logger(__name__)


class ConfigManager:
    """配置管理器"""

    _instance = None
    _config = None
    _lock = threading.Lock()

    def __new__(cls, config_path: str = "config.yaml"):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance.config_path = config_path
                    cls._instance.load_config()
                    try:
                        from app.services.config_service import get_config_service
                        get_config_service(config_path).register_change_callback(
                            cls._instance.reload
                        )
                    except Exception as e:
                        logger.warning(f"Failed to register config callback: {e}")
        return cls._instance

    def load_config(self):
        """加载配置文件"""
        try:
            if os.path.exists(self.config_path):
                app_config = AppConfig.from_yaml(self.config_path)
                self._config = app_config.model_dump()
                logger.info(f"Configuration loaded from {self.config_path}")
            else:
                logger.warning(f"Configuration file not found: {self.config_path}")
                self._config = {}
        except Exception as e:
            logger.error(f"Failed to load configuration: {str(e)}")
            if self._config is None:
                self._config = {}

    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值

        Args:
            key: 配置键，支持点号分隔（如 "quark.cookie"）
            default: 默认值

        Returns:
            配置值
        """
        keys = key.split('.')
        value = self._config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def get_quark_config(self) -> Dict[str, Any]:
        """
        获取夸克配置

        Returns:
            夸克配置字典
        """
        return self.get('quark', {})

    def get_quark_cookie(self) -> str:
        """
        获取夸克Cookie

        Returns:
            Cookie字符串
        """
        return self.get('quark.cookie', '')

    def get_quark_referer(self) -> str:
        """
        获取夸克Referer

        Returns:
            Referer地址
        """
        return self.get('quark.referer', 'https://pan.quark.cn/')

    def get_quark_root_id(self) -> str:
        """
        获取夸克根目录ID

        Returns:
            根目录ID
        """
        return self.get('quark.root_id', '0')

    def get_quark_only_video(self) -> bool:
        """
        获取是否只获取视频文件

        Returns:
            是否只获取视频文件
        """
        return self.get('quark.only_video', True)

    def get_alist_config(self) -> Dict[str, Any]:
        """获取AList配置"""
        return self.get('alist', {})

    def get_webdav_config(self) -> Dict[str, Any]:
        """获取WebDAV配置"""
        return self.get('webdav', {})

    def reload(self):
        """重新加载配置"""
        self.load_config()
        logger.info("Configuration reloaded")


# 全局配置管理器实例
config_manager = ConfigManager()


def get_config() -> ConfigManager:
    """
    获取配置管理器实例

    Returns:
        配置管理器实例
    """
    return config_manager
