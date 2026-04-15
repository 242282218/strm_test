# 2026-04-16 Iteration 23: db_utils + Error Handler Hardening & Coverage Gate to 48

## 当前状态判断
- 覆盖率门槛 `47` 在多轮回归后已接近上限，但缓冲不足（上一轮仅 `47.36%`）。
- `app/core/db_utils.py` 与 `app/core/error_handler.py` 作为基础工具/兼容层，回归保护薄弱。
- `app/core/error_handler.py` 存在导入即 `TypeError` 的兼容层缺陷（`Enum` 继承方式非法），属于真实可用性风险。

## 对标项目可借鉴点
- 成熟项目在提升覆盖率门槛前，优先补“高频基础模块 + 兼容层”测试，而非先攻大体量业务模块，收益/风险比更高。
- 兼容层（deprecated module）应至少满足“可导入、可告警、关键工具行为稳定”三项最小契约，避免历史调用方在升级中直接崩溃。
- CI 门槛抬升应采用“先补缓冲，再小步上调，最后全量强校验”的节奏。

## 差距清单（按 P0/P1/P2/P3）
- P0: `app/core/error_handler.py` 兼容枚举定义错误，导入即异常。
  - 影响：历史依赖该模块的调用方无法启动。
  - 根因：`Enum` 不能通过继承扩展已有枚举（`class ErrorCodeCompat(str, NewErrorCode)`）。
  - 建议：改为别名复用 `NewErrorCode`，并补导入契约测试。
  - 收益：消除启动级兼容风险。
  - 风险：极低（仅兼容别名层）。
- P1: `db_utils` 与 `error_handler` 缺少系统补测。
  - 影响：批处理/扫描/兼容脱敏逻辑变更缺乏回归信号。
  - 根因：历史优先级集中在 API/service 主链路。
  - 建议：补齐核心分支与异常分支测试。
  - 收益：提高基建稳定性并为门槛上调提供缓冲。
  - 风险：低（仅新增测试 + 兼容层最小修复）。
- P2: `error_handler` 使用 `response.dict()` 触发 Pydantic V2 弃用告警。
  - 影响：告警噪音、未来版本兼容风险。
  - 建议：替换为 `model_dump()`。
  - 收益：减少告警噪音，提升前向兼容性。

## 本轮要做的优化项
- 新增 `tests/test_db_utils.py`，覆盖批量查询、分页/eager loading、异步批处理、扫描器与性能监控。
- 修复 `app/core/error_handler.py` 导入崩溃与 Pydantic V2 弃用调用，并新增兼容层测试 `tests/test_error_handler_compat.py`。
- 将 CI workflow 覆盖率门槛从 `47` 提升到 `48`，同步守护测试。

## 具体修改方案
- 新增 `quark_strm/tests/test_db_utils.py`
  - 覆盖 `BatchQueryHelper/QueryOptimizer/AsyncBatchProcessor/MemoryEfficientScanner/PerformanceMonitor` 及包装函数。
- 修改 `quark_strm/app/core/error_handler.py`
  - 将 `ErrorCodeCompat` 改为 `NewErrorCode` 别名，修复导入级异常。
  - `create_success_response` 从 `response.dict()` 改为 `response.model_dump()`。
- 新增 `quark_strm/tests/test_error_handler_compat.py`
  - 覆盖弃用告警、兼容别名、脱敏分支、header 脱敏、成功响应、代理函数。
- 更新 `quark_strm/.github/workflows/pytest.yml`
  - `COVERAGE_FAIL_UNDER` 从 `47` 提升到 `48`。
- 更新 `quark_strm/tests/test_pytest_workflow_coverage_gate.py`
  - 断言下限同步为 `>=48`。

## 验证方案
- 目标测试：
  - `python -m pytest -q -o addopts='--tb=short -v' tests/test_db_utils.py`
  - `python -m pytest -q -o addopts='--tb=short -v' tests/test_error_handler_compat.py`
  - `python -m pytest -q -o addopts='--tb=short -v' tests/test_pytest_workflow_coverage_gate.py tests/test_ci_workflow.py tests/test_error_handler_compat.py tests/test_db_utils.py`
- 模块覆盖：
  - `python -m pytest -q -o addopts='-v --tb=short --cov=app.core.db_utils --cov-report=term-missing' tests/test_db_utils.py`
  - `python -m pytest -q -o addopts='-v --tb=short --cov=app.core.error_handler --cov-report=term-missing' tests/test_error_handler_compat.py`
- 全量强校验：
  - `python -m pytest -q -o addopts='-v --tb=short --strict-markers --cov=app --cov-fail-under=48'`
- 结果：
  - 全量 `759 passed, 2 skipped`；
  - 总覆盖率 `48.16%`，达到门槛 `48`；
  - `app/core/db_utils.py` `98.74%`，`app/core/error_handler.py` `100%`。

## 本轮风险
- 门槛 `48` 当前缓冲约 `0.16%`，若后续引入大体量低覆盖代码，仍可能触发 CI 抖动。
- 大量低覆盖历史模块仍集中在 `services/media/*`、`services/integrations/*`、`core/*_monitor/*_queue`。

## 下一轮建议
1. 优先补 `app/core/db_loader.py`（当前 `0%`）的选项应用与模型映射分支，收益高且耦合低。
2. 对 `app/services/integrations/quark.py` 做最小闭环补测，清理高体量低覆盖瓶颈。
3. 在覆盖率稳定超过 `48.5%` 后，再评估门槛上调到 `49`，继续保持“补缓冲后抬门槛”。
