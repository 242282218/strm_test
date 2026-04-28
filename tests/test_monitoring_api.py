"""
监控 API 模块单元测试

测试指标查询、系统状态和健康检查端点
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.monitoring import router
from app.core.dependencies import require_api_key
from app.core.metrics_collector import (
    AlertManager,
    AlertThreshold,
    MetricsCollector,
    SystemMonitor,
    get_alert_manager,
    get_metrics_collector,
    get_system_monitor,
)


@pytest.fixture
def app():
    """创建测试应用"""
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[require_api_key] = lambda: None
    return app


@pytest.fixture
def client(app):
    """创建测试客户端"""
    return TestClient(app)


@pytest.fixture
def mock_collector():
    """创建模拟指标收集器"""
    collector = MetricsCollector(max_points=100)

    # 添加一些测试数据
    collector.record_metric("system.cpu.percent", 50.0)
    collector.record_metric("system.memory.percent", 60.0)
    collector.record_metric("system.disk.percent", 70.0)

    return collector


@pytest.fixture
def mock_monitor(mock_collector):
    """创建模拟系统监控器"""
    return SystemMonitor(mock_collector)


@pytest.fixture
def mock_alert_manager(mock_collector):
    """创建模拟告警管理器"""
    return AlertManager(mock_collector)


class TestHealthEndpoint:
    """健康检查端点测试"""

    def test_health_check(self, client):
        """测试健康检查"""
        response = client.get("/monitor/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "monitoring-api"
        assert "timestamp" in data


class TestMonitoringAuthorization:
    """监控读取端点鉴权测试"""

    def test_metrics_requires_authentication(self):
        """测试获取监控指标需要鉴权"""
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        response = client.get("/monitor/metrics")

        assert response.status_code == 401

    def test_db_pool_status_requires_authentication(self):
        """测试获取数据库连接池状态需要鉴权"""
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        response = client.get("/monitor/db-pool/status")

        assert response.status_code == 401


class TestMetricsEndpoint:
    """指标端点测试"""

    def test_get_metrics(self, app, mock_collector):
        """测试获取指标"""
        app.dependency_overrides[get_metrics_collector] = lambda: mock_collector
        client = TestClient(app)

        response = client.get("/monitor/metrics")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "data" in data

    def test_get_metrics_empty(self, app):
        """测试获取空指标"""
        empty_collector = MetricsCollector()
        app.dependency_overrides[get_metrics_collector] = lambda: empty_collector
        client = TestClient(app)

        response = client.get("/monitor/metrics")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"

    def test_get_metric_history(self, app, mock_collector):
        """测试获取指标历史"""
        app.dependency_overrides[get_metrics_collector] = lambda: mock_collector
        client = TestClient(app)

        response = client.get("/monitor/metrics/system.cpu.percent")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["metric_name"] == "system.cpu.percent"
        assert "history" in data
        assert "stats" in data

    def test_get_metric_history_not_found(self, app, mock_collector):
        """测试获取不存在的指标历史"""
        app.dependency_overrides[get_metrics_collector] = lambda: mock_collector
        client = TestClient(app)

        response = client.get("/monitor/metrics/nonexistent.metric")

        assert response.status_code == 404

    def test_get_metric_history_with_limit(self, app, mock_collector):
        """测试获取指标历史带限制"""
        # 添加更多数据点
        for i in range(50):
            mock_collector.record_metric("test.metric", float(i))

        app.dependency_overrides[get_metrics_collector] = lambda: mock_collector
        client = TestClient(app)

        response = client.get("/monitor/metrics/test.metric?limit=10")

        assert response.status_code == 200
        data = response.json()
        assert len(data["history"]) <= 10


class TestAlertsEndpoint:
    """告警端点测试"""

    def test_get_active_alerts(self, app, mock_alert_manager):
        """测试获取活跃告警"""
        app.dependency_overrides[get_alert_manager] = lambda: mock_alert_manager
        client = TestClient(app)

        response = client.get("/monitor/alerts")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "active_alerts" in data
        assert "count" in data

    def test_get_active_alerts_with_data(self, app, mock_collector):
        """测试获取有数据的活跃告警"""
        alert_manager = AlertManager(mock_collector)

        # 添加告警阈值并触发
        threshold = AlertThreshold("system.cpu.percent", 40.0, "gt", duration=0)
        alert_manager.add_threshold(threshold)
        alert_manager.check_thresholds()

        app.dependency_overrides[get_alert_manager] = lambda: alert_manager
        client = TestClient(app)

        response = client.get("/monitor/alerts")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"


class TestSystemStatusEndpoint:
    """系统状态端点测试"""

    def test_get_system_status(self, app, mock_collector):
        """测试获取系统状态"""
        app.dependency_overrides[get_metrics_collector] = lambda: mock_collector
        client = TestClient(app)

        response = client.get("/monitor/system/status")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "system_health" in data
        assert "metrics" in data

    def test_get_system_status_healthy(self, app):
        """测试获取健康的系统状态"""
        collector = MetricsCollector()
        collector.record_metric("system.cpu.percent", 30.0)
        collector.record_metric("system.memory.percent", 40.0)
        collector.record_metric("system.disk.percent", 50.0)

        app.dependency_overrides[get_metrics_collector] = lambda: collector
        client = TestClient(app)

        response = client.get("/monitor/system/status")

        assert response.status_code == 200
        data = response.json()
        assert data["system_health"] == "healthy"

    def test_get_system_status_warning(self, app):
        """测试获取警告状态的系统状态"""
        collector = MetricsCollector()
        collector.record_metric("system.cpu.percent", 85.0)  # 高 CPU
        collector.record_metric("system.memory.percent", 40.0)
        collector.record_metric("system.disk.percent", 50.0)

        app.dependency_overrides[get_metrics_collector] = lambda: collector
        client = TestClient(app)

        response = client.get("/monitor/system/status")

        assert response.status_code == 200
        data = response.json()
        assert data["system_health"] == "warning"

    def test_get_system_status_critical(self, app):
        """测试获取严重状态的系统状态"""
        collector = MetricsCollector()
        collector.record_metric("system.cpu.percent", 50.0)
        collector.record_metric("system.memory.percent", 50.0)
        collector.record_metric("system.disk.percent", 95.0)  # 严重磁盘使用

        app.dependency_overrides[get_metrics_collector] = lambda: collector
        client = TestClient(app)

        response = client.get("/monitor/system/status")

        assert response.status_code == 200
        data = response.json()
        assert data["system_health"] == "critical"


class TestMonitoringControl:
    """监控控制端点测试"""

    def test_start_monitoring(self, app, mock_monitor):
        """测试启动监控"""
        app.dependency_overrides[get_system_monitor] = lambda: mock_monitor
        client = TestClient(app)

        response = client.post("/monitor/monitoring/start?interval=5.0")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "started" in data["message"]

    def test_stop_monitoring(self, app, mock_monitor):
        """测试停止监控"""
        app.dependency_overrides[get_system_monitor] = lambda: mock_monitor
        client = TestClient(app)

        response = client.post("/monitor/monitoring/stop")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "stopped" in data["message"]


class TestHTTPPoolEndpoints:
    """HTTP 连接池端点测试"""

    def test_get_http_pool_stats(self, app):
        """测试获取 HTTP 连接池统计"""
        mock_pool = MagicMock()
        mock_pool.get_stats = MagicMock(return_value={"pool_stats": {}, "total_clients": 0, "initialized": True})

        with patch("app.api.monitoring.get_http_pool") as mock_get_pool:
            mock_get_pool.return_value = mock_pool
            client = TestClient(app)

            response = client.get("/monitor/http-pool/stats")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            assert "data" in data

    def test_get_http_pool_health(self, app):
        """测试获取 HTTP 连接池健康状态"""
        mock_pool = MagicMock()
        mock_pool.get_health_status = MagicMock(
            return_value={"status": "healthy", "healthy_clients": 2, "unhealthy_clients": 0}
        )

        with patch("app.api.monitoring.get_http_pool") as mock_get_pool:
            mock_get_pool.return_value = mock_pool
            client = TestClient(app)

            response = client.get("/monitor/http-pool/health")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            assert "data" in data


class TestMetricsCollector:
    """指标收集器测试"""

    def test_record_metric(self):
        """测试记录指标"""
        collector = MetricsCollector()

        collector.record_metric("test.metric", 42.0)

        stats = collector.get_metric_stats("test.metric")
        assert stats["count"] == 1
        assert stats["latest"] == 42.0

    def test_record_metric_with_tags(self):
        """测试带标签记录指标"""
        collector = MetricsCollector()

        collector.record_metric("test.metric", 42.0, tags={"host": "localhost"})

        stats = collector.get_metric_stats("test.metric")
        assert stats["count"] == 1

    def test_get_metric_stats_empty(self):
        """测试获取空指标统计"""
        collector = MetricsCollector()

        stats = collector.get_metric_stats("nonexistent")

        assert stats == {}

    def test_get_metric_stats_multiple_points(self):
        """测试获取多数据点统计"""
        collector = MetricsCollector()

        for i in range(10):
            collector.record_metric("test.metric", float(i))

        stats = collector.get_metric_stats("test.metric")

        assert stats["count"] == 10
        assert stats["min"] == 0.0
        assert stats["max"] == 9.0
        assert stats["avg"] == 4.5

    def test_get_recent_points(self):
        """测试获取最近数据点"""
        collector = MetricsCollector(max_points=100)

        for i in range(50):
            collector.record_metric("test.metric", float(i))

        points = collector.get_recent_points("test.metric", limit=10)

        assert len(points) == 10
        assert points[-1].value == 49.0

    def test_max_points_limit(self):
        """测试最大数据点限制"""
        collector = MetricsCollector(max_points=10)

        for i in range(20):
            collector.record_metric("test.metric", float(i))

        stats = collector.get_metric_stats("test.metric")
        assert stats["count"] == 10


class TestAlertManager:
    """告警管理器测试"""

    def test_add_threshold(self):
        """测试添加告警阈值"""
        collector = MetricsCollector()
        manager = AlertManager(collector)

        threshold = AlertThreshold("test.metric", 80.0, "gt")
        manager.add_threshold(threshold)

        assert len(manager.thresholds) == 1

    def test_check_thresholds_gt(self):
        """测试大于阈值检查"""
        collector = MetricsCollector()
        collector.record_metric("test.metric", 90.0)

        manager = AlertManager(collector)
        threshold = AlertThreshold("test.metric", 80.0, "gt", duration=0)
        manager.add_threshold(threshold)

        manager.check_thresholds()

        # 应该触发告警
        assert len(manager.alerts) == 1

    def test_check_thresholds_lt(self):
        """测试小于阈值检查"""
        collector = MetricsCollector()
        collector.record_metric("test.metric", 10.0)

        manager = AlertManager(collector)
        threshold = AlertThreshold("test.metric", 20.0, "lt", duration=0)
        manager.add_threshold(threshold)

        manager.check_thresholds()

        assert len(manager.alerts) == 1

    def test_check_thresholds_not_triggered(self):
        """测试阈值未触发"""
        collector = MetricsCollector()
        collector.record_metric("test.metric", 50.0)

        manager = AlertManager(collector)
        threshold = AlertThreshold("test.metric", 80.0, "gt", duration=0)
        manager.add_threshold(threshold)

        manager.check_thresholds()

        assert len(manager.alerts) == 0

    def test_evaluate_condition(self):
        """测试条件评估"""
        collector = MetricsCollector()
        manager = AlertManager(collector)

        assert manager._evaluate_condition(10, 5, "gt") is True
        assert manager._evaluate_condition(5, 10, "gt") is False
        assert manager._evaluate_condition(5, 10, "lt") is True
        assert manager._evaluate_condition(10, 10, "eq") is True
        assert manager._evaluate_condition(10, 10, "ge") is True
        assert manager._evaluate_condition(10, 10, "le") is True
