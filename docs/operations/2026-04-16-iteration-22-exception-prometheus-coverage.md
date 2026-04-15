# 2026-04-16 Iteration 22: Exception & Prometheus Coverage Hardening

## 当前状态判断
- 全量覆盖率从 `46.17%` 提升到 `47.36%`，已满足将 CI 门槛提升到 `47` 的条件。
- 核心风险从“错误处理契约缺乏回归保护”转为“低覆盖大模块（如 `media/*`、`integrations/*`）仍会限制后续门槛上调速度”。

## 对标项目可借鉴点
- 成熟 FastAPI 项目通常把异常映射逻辑（HTTP/Validation/AppException）单独做契约测试，避免改动时无感破坏前端错误处理。
- 监控链路遵循“指标采集失败不影响主流程”，通过日志记录降级，不把 telemetry 故障升级为业务故障。
- 覆盖率门槛上调采用“先补薄弱关键路径，再抬门槛”的渐进策略，避免 CI 抖动。

## 差距清单（按 P0/P1/P2/P3）
- P1: 异常处理层此前覆盖不足，`request_id` 透传、detail 脱敏、500 隐藏细节等契约没有强保护。
- P1: Prometheus helper/装饰器此前缺少异常分支验证，存在“指标异常可能被静默改坏”的风险。
- P2: `app/core/exceptions.py` 转换函数未被系统验证，边界协议映射可能回归。

## 本轮要做的优化项
- 新增异常处理契约测试，覆盖 5 类 handler 的核心分支与 header 行为。
- 新增 Prometheus API 与 metrics helper 测试，覆盖成功/失败分支和 sync/async 装饰器路径。
- 新增异常类型与转换函数测试，为门槛 `47` 提供覆盖缓冲。
- 将 workflow 覆盖率门槛从 `46` 提升到 `47`，并同步守护测试下限。

## 具体修改方案
- 新增 `quark_strm/tests/test_exception_handler.py`
  - 覆盖 `app_exception_handler/http_exception_handler/validation_exception_handler/input_validation_exception_handler/exception_handler`。
- 新增 `quark_strm/tests/test_prometheus_api.py`
  - 覆盖 `/metrics` 成功与异常回退、`/metrics/health` 契约。
- 新增 `quark_strm/tests/test_prometheus_metrics.py`
  - 覆盖所有 helper 的正常/异常路径、`prometheus_track` 同步与异步分支。
- 新增 `quark_strm/tests/test_exceptions.py`
  - 覆盖异常类构造与 `convert_http_exception/convert_aiohttp_error` 映射。
- 更新 `quark_strm/.github/workflows/pytest.yml`
  - `COVERAGE_FAIL_UNDER` 从 `46` 调整到 `47`。
- 更新 `quark_strm/tests/test_pytest_workflow_coverage_gate.py`
  - 守护断言改为 `>=47`。

## 验证方案
- 目标回归：
  - `python -m pytest -q -o addopts='--tb=short -v' tests/test_exception_handler.py tests/test_prometheus_api.py tests/test_prometheus_metrics.py tests/test_exceptions.py`
- 模块覆盖：
  - `python -m pytest -q -o addopts='-v --tb=short --cov=app.core.prometheus_metrics --cov-report=term-missing' tests/test_prometheus_metrics.py`
  - `python -m pytest -q -o addopts='-v --tb=short --cov=app.core.exceptions --cov-report=term-missing' tests/test_exceptions.py`
- 门槛守护：
  - `python -m pytest -q -o addopts='--tb=short -v' tests/test_pytest_workflow_coverage_gate.py tests/test_ci_workflow.py`
- 全量强校验：
  - `python -m pytest -q -o addopts='-v --tb=short --strict-markers --cov=app --cov-fail-under=47'`
- 结果：全量 `732 passed, 2 skipped`，总覆盖率 `47.36%`；`app/core/prometheus_metrics.py` 提升到 `97.84%`，`app/core/exceptions.py` 提升到 `98.66%`。

## 本轮风险
- 当前门槛缓冲约 `0.36%`，若后续引入大体量低覆盖模块，仍可能触发 CI 波动。
- 现有优化主要集中于核心异常/监控链路，业务重模块 (`media`, `integrations`) 仍是后续门槛提升瓶颈。

## 下一轮建议
1. 优先补 `app/core/error_handler.py`（兼容层）或 `app/core/db_utils.py`（工具层）中高风险分支，继续扩大 `47` 门槛缓冲。
2. 选择一个高体量低覆盖模块（建议 `app/services/integrations/quark.py`）做最小闭环补测，提升门槛上调空间。
3. 维持“先补关键路径后抬门槛”的节奏，避免无缓冲上调到 `48`。
