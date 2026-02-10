"""
Pytest配置和共享fixture
"""
import os
import sys
import pytest
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 设置测试环境变量
os.environ.setdefault("CONFIG_PATH", str(project_root / "tests" / "fixtures" / "test_config.yaml"))
os.environ.setdefault("TESTING", "true")


@pytest.fixture
def test_config_path(tmp_path):
    """创建临时测试配置文件"""
    config_content = """
database: test.db
log_level: DEBUG
quark:
  cookie: "test_cookie"
  root_id: "0"
tmdb:
  api_key: "test_key"
"""
    config_file = tmp_path / "test_config.yaml"
    config_file.write_text(config_content)
    return str(config_file)


@pytest.fixture
def mock_quark_cookie():
    """Mock夸克Cookie"""
    return "test_quark_cookie_12345"


@pytest.fixture
def mock_tmdb_api_key():
    """Mock TMDB API Key"""
    return "test_tmdb_api_key_67890"


@pytest.fixture
def valid_cloud_drive_data():
    """有效的云盘创建数据"""
    return {
        "name": "测试云盘",
        "drive_type": "quark",
        "cookie": "test_cookie_value",
        "remark": "测试备注"
    }


@pytest.fixture
def invalid_cloud_drive_data():
    """无效的云盘创建数据（空name）"""
    return {
        "name": "",
        "drive_type": "quark",
        "cookie": "test_cookie_value"
    }


@pytest.fixture
def valid_task_data():
    """有效的任务创建数据"""
    return {
        "task_type": "strm_generate",
        "params": {
            "source_dir": "/test",
            "target_dir": "/output"
        },
        "priority": "normal"
    }
