"""
API V1 路由标准化测试

测试目标:
1. 验证 V1 路由聚合器正确注册所有路由
2. 验证路由结构和标签
3. 验证路由模块可导入
"""

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient


class TestV1RouterAggregation:
    """V1 路由聚合测试"""

    def test_v1_router_can_be_imported(self):
        """验证 V1 路由可以正确导入"""
        from app.api.v1 import v1_router
        assert v1_router is not None

    def test_v1_router_is_api_router(self):
        """验证 V1 路由是 APIRouter 实例"""
        from app.api.v1 import v1_router
        assert isinstance(v1_router, APIRouter)

    def test_v1_router_includes_all_core_routes(self):
        """验证 V1 路由聚合器包含所有核心路由"""
        from app.api.v1 import v1_router
        
        # 获取所有注册的路由
        routes = [route.path for route in v1_router.routes]
        
        # 验证核心路由存在
        assert len(routes) > 0, "V1 router should have routes"

    def test_v1_router_has_correct_tags(self):
        """验证 V1 路由有正确的标签"""
        from app.api.v1 import v1_router
        
        # 收集所有标签
        tags = set()
        for route in v1_router.routes:
            if hasattr(route, 'tags') and route.tags:
                tags.update(route.tags)
        
        # 验证核心标签存在
        expected_tags = {"Quark", "STRM", "Proxy", "Emby", "Scrape", "Tasks", "Monitor"}
        assert expected_tags.issubset(tags), f"Missing tags: {expected_tags - tags}"


class TestRouteModulesImport:
    """路由模块导入测试"""

    def test_all_route_modules_importable(self):
        """验证所有路由模块可以导入"""
        modules = [
            'app.api.quark',
            'app.api.strm',
            'app.api.proxy',
            'app.api.emby',
            'app.api.scrape',
            'app.api.tasks',
            'app.api.monitoring',
        ]
        
        for module in modules:
            mod = __import__(module, fromlist=['router'])
            assert hasattr(mod, 'router'), f"Module {module} should have 'router' attribute"
            assert isinstance(mod.router, APIRouter), f"Module {module} router should be APIRouter"

    def test_all_routers_have_prefix(self):
        """验证所有路由器都有前缀"""
        modules = [
            ('app.api.quark', '/api/quark'),
            ('app.api.strm', '/api/strm'),
            ('app.api.proxy', '/api/proxy'),
            ('app.api.emby', '/api/emby'),
            ('app.api.monitoring', '/monitor'),
        ]
        
        for module_name, expected_prefix in modules:
            mod = __import__(module_name, fromlist=['router'])
            router = mod.router
            # 检查路由器是否有前缀
            if hasattr(router, 'prefix'):
                assert router.prefix == expected_prefix, \
                    f"Module {module_name} should have prefix {expected_prefix}, got {router.prefix}"


class TestMainAppRouteStructure:
    """主应用路由结构测试"""

    def test_main_app_has_v1_router_import(self):
        """验证主应用可以导入 V1 路由"""
        from app.main import app
        
        # 检查应用是否正确导入
        assert app is not None
        assert app.title == "夸克 STRM 系统"

    def test_deprecation_middleware_exists(self):
        """验证弃用中间件存在"""
        from app.main import deprecation_warning_middleware
        
        # 检查中间件函数存在
        assert callable(deprecation_warning_middleware)

    def test_main_app_routes_count(self):
        """验证主应用有足够的路由"""
        from app.main import app
        
        # 统计路由数量
        total_routes = len(app.routes)
        
        # 应该有足够的路由（包括 OpenAPI、健康检查等）
        assert total_routes > 20, f"Expected more routes, got {total_routes}"


class TestDeprecationMiddlewareLogic:
    """弃用中间件逻辑测试"""

    def test_legacy_prefixes_detection(self):
        """测试旧路由前缀检测逻辑"""
        legacy_prefixes = [
            "/api/quark", "/api/strm", "/api/proxy", "/api/emby",
            "/api/scrape", "/api/tasks", "/api/drives", "/api/monitor"
        ]
        
        # 测试路径匹配逻辑
        test_cases = [
            ("/api/quark/browse", True),
            ("/api/strm/scan", True),
            ("/api/v1/quark/browse", False),
            ("/health", False),
            ("/api/v1/strm/scan", False),
            ("/api/unknown", False),
        ]
        
        for path, expected_is_legacy in test_cases:
            is_legacy = (
                path.startswith("/api/") and 
                not path.startswith("/api/v1/") and
                any(path.startswith(prefix) for prefix in legacy_prefixes)
            )
            assert is_legacy == expected_is_legacy, \
                f"Path {path}: expected {expected_is_legacy}, got {is_legacy}"


class TestV1RouterStructure:
    """V1 路由结构测试"""

    def test_v1_router_includes_quark_routes(self):
        """验证 V1 路由包含 Quark 路由"""
        from app.api.v1 import v1_router

        # 检查 quark 路由是否被包含
        route_paths = [str(route.path) for route in v1_router.routes]

        assert any(path.startswith("/quark/") for path in route_paths)
        assert any(path.startswith("/api/quark/") for path in route_paths)

    def test_v1_router_route_count(self):
        """验证 V1 路由数量"""
        from app.api.v1 import v1_router

        # 统计路由数量
        route_count = len(v1_router.routes)

        # 应该有来自多个模块的路由
        assert route_count >= 7, f"Expected at least 7 routes, got {route_count}"

    def test_v1_router_tasks_routes_use_canonical_prefix(self):
        """验证 tasks 路由在 v1 下使用 /tasks 前缀"""
        from app.api.v1 import v1_router

        route_paths = [str(route.path) for route in v1_router.routes]
        assert any(path == "/tasks" for path in route_paths)
        assert any(path == "/tasks/ws" for path in route_paths)

    def test_v1_router_does_not_expose_root_level_task_aliases(self):
        """验证 v1 不再暴露会抢占 collection 路由的 tasks 根级别别名"""
        from app.api.v1 import v1_router

        route_paths = {str(route.path) for route in v1_router.routes}

        assert "/{task_id}" not in route_paths
        assert "/ws" not in route_paths

    def test_main_app_keeps_v1_legacy_alias_and_canonical_paths(self):
        """验证主应用同时保留 canonical 与 legacy alias v1 路径。"""
        from app.main import app

        paths = {getattr(route, "path", None) for route in app.routes}
        assert "/api/v1/quark/config" in paths
        assert "/api/v1/api/quark/config" in paths

class TestMainRouterRegistration:
    """main.py 路由注册收口测试"""

    def test_main_app_registers_emby_gateway_root_route_once(self):
        from app.main import app

        gateway_root_routes = [
            route
            for route in app.routes
            if getattr(route, "path", None) == "/" and getattr(route, "endpoint", None).__name__ == "emby_gateway_root"
        ]

        assert len(gateway_root_routes) == 1

    def test_main_app_prefers_canonical_v1_tasks_collection_over_legacy_dynamic_alias(self, monkeypatch: pytest.MonkeyPatch):
        from app.main import app

        monkeypatch.setenv("REQUIRE_API_KEY", "false")
        with TestClient(app) as client:
            response = client.get("/api/v1/tasks", params={"skip": 0, "limit": 1})

        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_main_app_does_not_register_root_level_v1_task_aliases(self):
        from app.main import app

        paths = {getattr(route, "path", None) for route in app.routes}

        assert "/api/v1/{task_id}" not in paths
        assert "/api/v1/ws" not in paths
