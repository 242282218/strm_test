"""
配置模块测试
对应测试矩阵: CORE-001, CORE-002
"""
import pytest
import yaml
from pathlib import Path


class TestAppConfig:
    """AppConfig配置加载测试"""
    
    def test_load_valid_config(self, tmp_path):
        """CORE-001: 加载有效YAML配置"""
        from app.config.settings import AppConfig
        
        # 创建有效配置文件
        config_content = {
            "database": "test.db",
            "log_level": "DEBUG",
            "quark": {
                "cookie": "test_cookie",
                "root_id": "0"
            },
            "tmdb": {
                "api_key": "test_key"
            }
        }
        config_file = tmp_path / "valid_config.yaml"
        with open(config_file, 'w') as f:
            yaml.dump(config_content, f)
        
        # 加载配置
        config = AppConfig.from_yaml(str(config_file))
        
        # 验证
        assert config.database == "test.db"
        assert config.log_level == "DEBUG"
        assert config.quark.cookie == "test_cookie"
        assert config.tmdb.api_key == "test_key"
    
    def test_load_invalid_yaml_format(self, tmp_path):
        """CORE-002: 加载无效YAML格式应抛出异常"""
        from app.config.settings import AppConfig
        
        # 创建无效YAML文件
        config_file = tmp_path / "invalid_config.yaml"
        config_file.write_text("invalid: yaml: content: [")
        
        # 应抛出YAML解析错误
        with pytest.raises(Exception) as exc_info:
            AppConfig.from_yaml(str(config_file))
        
        assert "yaml" in str(exc_info.value).lower() or "scanner" in str(exc_info.value).lower()
    
    def test_load_nonexistent_config(self, tmp_path):
        """SVC-002: 加载不存在的配置文件"""
        from app.config.settings import AppConfig
        
        nonexistent_path = str(tmp_path / "nonexistent.yaml")
        
        with pytest.raises(FileNotFoundError):
            AppConfig.from_yaml(nonexistent_path)
    
    def test_config_validation_log_level(self):
        """测试log_level验证"""
        from app.config.settings import AppConfig
        
        # 有效log_level
        config = AppConfig(log_level="INFO")
        assert config.log_level == "INFO"
        
        # 无效log_level应抛出异常
        with pytest.raises(ValueError) as exc_info:
            AppConfig(log_level="INVALID")
        assert "log_level" in str(exc_info.value)


class TestConfigService:
    """ConfigService测试"""
    
    def test_get_config_with_valid_path(self, tmp_path):
        """SVC-001: 使用有效路径获取配置"""
        from app.services.config_service import ConfigService
        
        # 创建测试配置
        config_file = tmp_path / "test_config.yaml"
        config_file.write_text("database: test.db\nlog_level: DEBUG\n")
        
        # 创建服务并加载配置
        service = ConfigService(str(config_file))
        config = service.get_config()
        
        # 验证
        assert config is not None
        assert config.database == "test.db"
    
    def test_get_config_caching(self, tmp_path):
        """测试配置缓存"""
        from app.services.config_service import ConfigService
        
        config_file = tmp_path / "cached_config.yaml"
        config_file.write_text("database: cache_test.db\nlog_level: INFO\n")
        
        service = ConfigService(str(config_file))
        config1 = service.get_config()
        config2 = service.get_config()
        
        # 应返回同一实例（缓存）
        assert config1 is config2
