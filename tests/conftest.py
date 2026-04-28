"""
pytest 配置文件

提供测试夹具和通用配置
"""

import asyncio
import os
import sys
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest
import pytest_asyncio


# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@pytest.fixture(scope="session")
def event_loop():
    """创建事件循环"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_dir() -> Generator[str, None, None]:
    """创建临时目录"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def temp_db_path(temp_dir: str) -> str:
    """创建临时数据库路径"""
    return os.path.join(temp_dir, "test.db")


@pytest.fixture
def sample_cookie() -> str:
    """示例 Cookie"""
    return "__puus=test_value; __pus=another_value; session=test_session"


@pytest.fixture
def sample_strm_data() -> dict:
    """示例 STRM 数据"""
    return {
        "key": "test_file_id_123",
        "name": "test_video.mp4",
        "local_dir": "/tmp/strm",
        "remote_dir": "/videos/movies",
        "raw_url": "http://example.com/video.mp4",
    }


@pytest_asyncio.fixture
async def http_pool():
    """HTTP 连接池夹具"""
    from app.core.http_pool import HTTPConnectionPool

    pool = HTTPConnectionPool()
    await pool.initialize()
    yield pool
    await pool.close()


@pytest.fixture
def lru_cache():
    """LRU 缓存夹具"""
    from app.core.lru_cache import LRUCache

    cache = LRUCache(maxsize=100, ttl=60)
    yield cache
    cache.clear()


@pytest_asyncio.fixture
async def cache_service():
    """缓存服务夹具"""
    from app.services.cache_service import CacheService

    service = CacheService(backend="memory", max_size=100, default_ttl=60)
    await service.start()
    yield service
    await service.stop()


@pytest.fixture
def metrics_collector():
    """指标收集器夹具"""
    from app.core.metrics_collector import MetricsCollector

    collector = MetricsCollector(max_points=100)
    return collector


@pytest.fixture
def mock_config(monkeypatch, temp_dir: str):
    """模拟配置"""
    from unittest.mock import MagicMock

    mock_cfg = MagicMock()
    mock_cfg.database = os.path.join(temp_dir, "test.db")
    mock_cfg.get_quark_cookie.return_value = "test_cookie"
    mock_cfg.get_quark_root_id.return_value = "0"
    mock_cfg.get_quark_only_video.return_value = True
    mock_cfg.get_quark_config.return_value = {
        "cookie": "test_cookie",
        "referer": "https://pan.quark.cn/",
        "root_id": "0",
        "only_video": True,
    }

    return mock_cfg
