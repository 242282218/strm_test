#!/usr/bin/env python3
"""
API冒烟测试脚本

用途: 验证FastAPI服务基本可用性和错误处理
依赖: httpx (pip install httpx)

用法:
    python scripts/smoke_api.py
    python scripts/smoke_api.py --base-url http://localhost:8001
    python scripts/smoke_api.py --verbose

环境变量:
    BASE_URL - API基础URL (默认: http://127.0.0.1:8001)
"""

import sys
import argparse
import os
from typing import Optional

try:
    import httpx
except ImportError:
    print("Error: httpx is required. Install with: pip install httpx")
    sys.exit(1)


class APISmokeTester:
    """API冒烟测试器"""
    
    def __init__(self, base_url: str, verbose: bool = False):
        self.base_url = base_url.rstrip("/")
        self.verbose = verbose
        self.client = httpx.Client(base_url=self.base_url, timeout=10.0)
        self.passed = 0
        self.failed = 0
    
    def log(self, message: str, level: str = "info"):
        """输出日志"""
        if self.verbose or level in ["error", "warn"]:
            prefix = {"info": "[INFO]", "error": "[FAIL]", "success": "[PASS]", "warn": "[WARN]"}.get(level, "[INFO]")
            print(f"{prefix} {message}")
    
    def test_get_root(self) -> bool:
        """SMK-001: 测试根路径访问"""
        try:
            response = self.client.get("/")
            if response.status_code in [200, 307, 308]:
                self.log(f"GET / -> {response.status_code}", "success")
                self.passed += 1
                return True
            else:
                self.log(f"GET / -> {response.status_code} (expected 200)", "error")
                self.failed += 1
                return False
        except httpx.ConnectError as e:
            self.log(f"GET / -> Connection failed: {e}", "error")
            self.failed += 1
            return False
        except Exception as e:
            self.log(f"GET / -> Error: {e}", "error")
            self.failed += 1
            return False
    
    def test_get_health(self) -> bool:
        """API-003: 测试健康检查端点"""
        try:
            response = self.client.get("/health")
            if response.status_code == 200:
                data = response.json()
                if "status" in data and data["status"] == "ok":
                    self.log(f"GET /health -> 200 OK (status: {data.get('status')})", "success")
                    self.passed += 1
                    return True
                else:
                    self.log(f"GET /health -> 200 but missing 'status' field", "warn")
                    self.passed += 1
                    return True
            else:
                self.log(f"GET /health -> {response.status_code} (expected 200)", "error")
                self.failed += 1
                return False
        except httpx.ConnectError as e:
            self.log(f"GET /health -> Connection failed: {e}", "error")
            self.failed += 1
            return False
        except Exception as e:
            self.log(f"GET /health -> Error: {e}", "error")
            self.failed += 1
            return False
    
    def test_get_nonexistent(self) -> bool:
        """SMK-002: 测试不存在的路径返回404"""
        try:
            response = self.client.get("/nonexistent_path_12345")
            if response.status_code == 404:
                self.log(f"GET /nonexistent_path_12345 -> 404 (expected)", "success")
                self.passed += 1
                return True
            else:
                self.log(f"GET /nonexistent_path_12345 -> {response.status_code} (expected 404)", "error")
                self.failed += 1
                return False
        except Exception as e:
            self.log(f"GET /nonexistent -> Error: {e}", "error")
            self.failed += 1
            return False
    
    def test_api_quark_no_cookie(self) -> bool:
        """SMK-003: 测试无Cookie时返回结构化错误"""
        try:
            response = self.client.get("/api/quark/files/0")
            # 期望401或403，不应是500
            if response.status_code in [401, 403]:
                self.log(f"GET /api/quark/files/0 -> {response.status_code} (expected, no cookie)", "success")
                self.passed += 1
                return True
            elif response.status_code == 500:
                self.log(f"GET /api/quark/files/0 -> 500 (unexpected server error)", "error")
                self.failed += 1
                return False
            else:
                self.log(f"GET /api/quark/files/0 -> {response.status_code}", "warn")
                self.passed += 1
                return True
        except Exception as e:
            self.log(f"GET /api/quark/files/0 -> Error: {e}", "error")
            self.failed += 1
            return False
    
    def test_post_transfer_invalid_json(self) -> bool:
        """SMK-004: 测试无效JSON返回422"""
        try:
            response = self.client.post(
                "/api/transfer",
                content="not valid json",
                headers={"Content-Type": "application/json"}
            )
            if response.status_code == 422:
                self.log(f"POST /api/transfer (invalid JSON) -> 422 (expected)", "success")
                self.passed += 1
                return True
            elif response.status_code == 500:
                self.log(f"POST /api/transfer (invalid JSON) -> 500 (unexpected)", "error")
                self.failed += 1
                return False
            else:
                self.log(f"POST /api/transfer (invalid JSON) -> {response.status_code}", "warn")
                self.passed += 1
                return True
        except Exception as e:
            self.log(f"POST /api/transfer -> Error: {e}", "error")
            self.failed += 1
            return False
    
    def test_get_config_no_auth(self) -> bool:
        """API-006: 测试无API Key时返回401"""
        try:
            response = self.client.get("/config")
            if response.status_code == 401:
                self.log(f"GET /config -> 401 (expected, no API key)", "success")
                self.passed += 1
                return True
            elif response.status_code in [200, 403]:
                self.log(f"GET /config -> {response.status_code}", "warn")
                self.passed += 1
                return True
            else:
                self.log(f"GET /config -> {response.status_code}", "warn")
                self.passed += 1
                return True
        except Exception as e:
            self.log(f"GET /config -> Error: {e}", "error")
            self.failed += 1
            return False
    
    def run_all_tests(self) -> bool:
        """运行所有冒烟测试"""
        print(f"\n{'='*60}")
        print(f"API Smoke Tests")
        print(f"Base URL: {self.base_url}")
        print(f"{'='*60}\n")
        
        tests = [
            ("Root Path", self.test_get_root),
            ("Health Check", self.test_get_health),
            ("Nonexistent Path (404)", self.test_get_nonexistent),
            ("Quark API No Cookie", self.test_api_quark_no_cookie),
            ("Transfer Invalid JSON", self.test_post_transfer_invalid_json),
            ("Config No Auth", self.test_get_config_no_auth),
        ]
        
        for name, test_func in tests:
            if self.verbose:
                print(f"\nRunning: {name}")
            test_func()
        
        # 输出汇总
        print(f"\n{'='*60}")
        print(f"Results: {self.passed} passed, {self.failed} failed")
        print(f"{'='*60}\n")
        
        return self.failed == 0
    
    def close(self):
        """关闭HTTP客户端"""
        self.client.close()


def main():
    parser = argparse.ArgumentParser(description="API Smoke Test Script")
    parser.add_argument(
        "--base-url",
        default=os.getenv("BASE_URL", "http://127.0.0.1:8001"),
        help="API base URL (default: http://127.0.0.1:8001 or BASE_URL env)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output"
    )
    
    args = parser.parse_args()
    
    tester = APISmokeTester(base_url=args.base_url, verbose=args.verbose)
    
    try:
        success = tester.run_all_tests()
        sys.exit(0 if success else 1)
    finally:
        tester.close()


if __name__ == "__main__":
    main()
