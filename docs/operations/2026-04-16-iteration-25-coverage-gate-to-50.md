# 2026-04-16 Iteration 25: Pool Monitoring Coverage & Gate to 50

## 当前状态判断
- 在门槛 `49` 下，总覆盖率已提升到 `49.90%`，但距离 `50` 仍无缓冲。
- `app/core/db_pool_monitor.py` 作为连接池监控与告警核心模块，历史覆盖几乎为空，存在监控链路回归盲区。
- `app/services/integrations/quark.py` 已在上一轮补测并达到高覆盖，可将本轮重心转向监控基础设施层。

## 对标项目可借鉴点
- 成熟后端项目通常优先保证“监控与告警模块”的契约测试覆盖，因为这类代码出错会导致故障不可观测。
- 覆盖率上调前会先补低耦合但高风险的基础模块（如 pool monitor），再进行全量门槛强校验。
- 监控类测试倾向于通过 mock 驱动覆盖线程启动、告警分发、健康摘要分级和全局单例辅助函数。

## 差距清单（按 P0/P1/P2/P3）
- P1: `db_pool_monitor` 缺乏系统补测，告警阈值和状态分级逻辑无回归保护。
  - 影响：连接池压力或异常状态可能无法正确告警，影响稳定性。
  - 根因：历史优化重心偏业务路径，基础监控模块被忽略。
  - 建议：补齐采集、历史裁剪、告警触发、状态摘要与全局 helper 路径测试。
- P1: 覆盖率门槛 `50` 未收敛，CI 质量信号仍低于当前可达上限。
  - 影响：高风险改动进入主线时，门槛保护不足。
  - 建议：在覆盖率稳定超过 `50` 后上调门槛并补守护测试。

## 本轮要做的优化项
- 新增 `tests/test_db_pool_monitor.py`，补齐连接池监控模块关键分支。
- 将 workflow 覆盖率门槛从 `49` 上调到 `50`，同步守护测试下限。
- 补跑全量 `--cov-fail-under=50` 作为门槛提升后的强校验证据。

## 具体修改方案
- 新增 `quark_strm/tests/test_db_pool_monitor.py`
  - 覆盖 `collect_metrics/_add_to_history/_check_alerts/_trigger_alerts/start/stop/get_status/get_health_summary`。
  - 覆盖全局 helper：`get_pool_monitor/start_monitoring/stop_monitoring/default_alert_handler`。
- 更新 `quark_strm/.github/workflows/pytest.yml`
  - `COVERAGE_FAIL_UNDER` 从 `49` 调整到 `50`。
- 更新 `quark_strm/tests/test_pytest_workflow_coverage_gate.py`
  - workflow 断言下限同步为 `>=50`。

## 验证方案
- 目标回归：
  - `python -m pytest -q -o addopts='--tb=short -v' tests/test_db_pool_monitor.py`
  - `python -m pytest -q -o addopts='--tb=short -v' tests/test_pytest_workflow_coverage_gate.py tests/test_ci_workflow.py tests/test_integrations_quark.py tests/test_db_pool_monitor.py`
- 模块覆盖：
  - `python -m pytest -q -o addopts='-v --tb=short --cov=app.core.db_pool_monitor --cov-report=term-missing' tests/test_db_pool_monitor.py`
  - `python -m pytest -q -o addopts='-v --tb=short --cov=app.services.integrations.quark --cov-report=term-missing' tests/test_integrations_quark.py`
- 全量强校验：
  - `python -m pytest -q -o addopts='-v --tb=short --strict-markers --cov=app --cov-fail-under=50'`
- 结果：
  - 全量 `797 passed, 2 skipped`；
  - 总覆盖率 `50.57%`；
  - `db_pool_monitor.py` `85.03%`，`integrations/quark.py` `90.67%`。

## 本轮风险
- 门槛 `50` 缓冲约 `0.57%`，若后续引入大体量低覆盖代码仍有抖动风险。
- 仍有多个高体量低覆盖模块（`media/*`、`db_write_queue`、`cache_statistics`）会限制下一轮上调空间。

## 下一轮建议
1. 优先补 `app/core/db_write_queue.py` 关键分支（写队列消费、重试、异常处理）提升基础可靠性。
2. 或选择 `app/services/cache_statistics.py` 做指标聚合契约补测，扩大 `50` 门槛缓冲。
3. 在覆盖率稳定 `50.5%+` 后再评估门槛提升到 `51`，继续保持“小步上调 + 守护测试 + 全量回归”。
