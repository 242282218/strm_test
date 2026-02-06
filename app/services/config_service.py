"""
统一配置服务

提供线程安全的配置读写、原子性保存和配置变更通知
"""

import os
import threading
import shutil
from typing import Optional
from app.config.settings import AppConfig
from app.core.logging import get_logger
from app.core.security import mask_sensitive_data

logger = get_logger(__name__)


class ConfigError(Exception):
    """配置错误"""


class ConfigService:
    """统一配置服务 - 单例模式"""

    _instance = None
    _lock = threading.Lock()
    _instance_lock = threading.Lock()

    def __new__(cls, config_path: str = "config.yaml"):
        """单例模式实现"""
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, config_path: str = "config.yaml"):
        """初始化配置服务"""
        if self._initialized:
            return

        self.config_path = config_path
        self._config: Optional[AppConfig] = None
        self._last_good_config: Optional[AppConfig] = None
        self._last_mtime: Optional[float] = None
        # Reentrant lock avoids deadlock when update flows call nested save operations.
        self._config_lock = threading.RLock()
        self._change_callbacks = []
        self._watcher_thread: Optional[threading.Thread] = None
        self._watcher_stop_event = threading.Event()
        self._load_config()
        self._initialized = True
        logger.info(f"ConfigService initialized with {config_path}")

    def _load_config(self):
        """
        从YAML加载配置

        Args:
            无

        Returns:
            无

        Side Effects:
            设置 self._config，记录日志
        """
        try:
            if os.path.exists(self.config_path):
                self._config = AppConfig.from_yaml(self.config_path)
                self._last_good_config = self._config
                self._last_mtime = os.path.getmtime(self.config_path)
                logger.info(f"Configuration loaded from {self.config_path}")
            else:
                self._config = AppConfig()
                self._save_config()
                self._last_good_config = self._config
                self._last_mtime = os.path.getmtime(self.config_path)
                logger.info(f"Created default configuration at {self.config_path}")
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            raise ConfigError(f"Failed to load config: {e}") from e

    def _save_config(self):
        """
        保存配置到YAML文件（原子性操作）

        Args:
            无

        Returns:
            无

        Side Effects:
            创建临时文件、备份文件、原子替换原文件
        """
        with self._config_lock:
            temp_path = f"{self.config_path}.tmp"
            backup_path = f"{self.config_path}.bak"

            try:
                # 1. 写入临时文件
                self._config.to_yaml(temp_path)

                # 2. 验证临时文件可读
                test_config = AppConfig.from_yaml(temp_path)

                # 3. 备份原文件
                if os.path.exists(self.config_path):
                    shutil.copy2(self.config_path, backup_path)

                # 4. 原子替换
                os.replace(temp_path, self.config_path)

                self._last_good_config = self._config
                self._last_mtime = os.path.getmtime(self.config_path)
                logger.info("Configuration saved successfully")
            except Exception as e:
                # 清理临时文件
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                logger.error(f"Failed to save config: {e}")
                raise e

    def get_config(self) -> AppConfig:
        """
        获取完整配置

        Args:
            无

        Returns:
            AppConfig: 当前配置对象
        """
        with self._config_lock:
            return self._config

    def get_safe_config(self) -> dict:
        """
        获取脱敏后的配置
        """
        with self._config_lock:
            config_dict = self._config.model_dump()
        return mask_sensitive_data(config_dict)

    def update_config(self, new_config: dict) -> AppConfig:
        """
        更新配置

        Args:
            new_config: 新配置字典

        Returns:
            AppConfig: 更新后的配置对象

        Side Effects:
            保存配置到文件，触发变更回调
        """
        with self._config_lock:
            try:
                self._config = AppConfig.model_validate(new_config)
            except Exception as e:
                raise ConfigError(f"Invalid config: {e}") from e
            self._save_config()
            self._notify_config_changed()
        return self._config

    def reload(self):
        """
        重新加载配置文件

        Args:
            无

        Returns:
            无

        Side Effects:
            从文件重新加载配置，触发变更回调
        """
        with self._config_lock:
            self._load_config()
            self._notify_config_changed()
        logger.info("Configuration reloaded")

    def start_watcher(self, interval_seconds: float = 2.0):
        """
        启动配置文件变更监控
        """
        if self._watcher_thread and self._watcher_thread.is_alive():
            return
        self._watcher_stop_event.clear()
        self._watcher_thread = threading.Thread(
            target=self._watch_loop,
            args=(interval_seconds,),
            daemon=True,
        )
        self._watcher_thread.start()
        logger.info("Config watcher started")

    def stop_watcher(self):
        """停止配置文件变更监控"""
        if not self._watcher_thread:
            return
        self._watcher_stop_event.set()
        self._watcher_thread.join(timeout=5)
        self._watcher_thread = None
        logger.info("Config watcher stopped")

    def _watch_loop(self, interval_seconds: float):
        while not self._watcher_stop_event.is_set():
            try:
                self._check_for_changes()
            except Exception as e:
                logger.error(f"Config watcher error: {e}")
            self._watcher_stop_event.wait(interval_seconds)

    def _check_for_changes(self):
        if not os.path.exists(self.config_path):
            return
        current_mtime = os.path.getmtime(self.config_path)
        if self._last_mtime is None:
            self._last_mtime = current_mtime
            return
        if current_mtime <= self._last_mtime:
            return
        logger.info("Config file change detected, reloading...")
        try:
            new_config = AppConfig.from_yaml(self.config_path)
        except Exception as e:
            logger.error(f"Config reload failed: {e}")
            self._rollback_to_last_good()
            return

        with self._config_lock:
            self._config = new_config
            self._last_good_config = new_config
            self._last_mtime = current_mtime
        self._notify_config_changed()
        logger.info("Config reloaded from file")

    def _rollback_to_last_good(self):
        if not self._last_good_config:
            logger.error("No last good config available for rollback")
            return
        try:
            with self._config_lock:
                self._config = self._last_good_config
                self._config.to_yaml(self.config_path)
                self._last_mtime = os.path.getmtime(self.config_path)
            self._notify_config_changed()
            logger.warning("Rolled back to last good configuration")
        except Exception as e:
            logger.error(f"Rollback failed: {e}")

    def register_change_callback(self, callback):
        """
        注册配置变更回调函数

        Args:
            callback: 回调函数，无参数

        Returns:
            无

        Side Effects:
            添加回调到回调列表
        """
        if callback not in self._change_callbacks:
            self._change_callbacks.append(callback)

    def _notify_config_changed(self):
        """
        通知配置变更（用于热更新）

        Args:
            无

        Returns:
            无

        Side Effects:
            调用所有注册的回调函数
        """
        for callback in self._change_callbacks:
            try:
                callback()
            except Exception as e:
                logger.error(f"Config change callback failed: {e}")


# 全局配置服务实例
_config_service_instance: Optional[ConfigService] = None


def get_config_service(config_path: Optional[str] = None) -> ConfigService:
    """
    ????????

    Args:
        config_path: ?????????? CONFIG_PATH ????? config.yaml

    Returns:
        ConfigService: ????????
    """
    global _config_service_instance
    resolved_path = config_path or os.getenv("CONFIG_PATH", "config.yaml")
    if _config_service_instance is None:
        _config_service_instance = ConfigService(resolved_path)
    elif _config_service_instance.config_path != resolved_path:
        logger.warning(
            "ConfigService path changed from %s to %s, reloading instance",
            _config_service_instance.config_path,
            resolved_path,
        )
        ConfigService._instance = None
        _config_service_instance = ConfigService(resolved_path)
    return _config_service_instance
