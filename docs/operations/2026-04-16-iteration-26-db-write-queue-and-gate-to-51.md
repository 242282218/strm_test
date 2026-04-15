# 2026-04-16 Iteration 26: DB Write Queue Coverage & Gate to 51

## 当前状态判断
- 上一轮门槛 `50` 已通过，但缓冲不足，仍需补核心基础模块来降低 CI 抖动风险。
- `app/core/db_write_queue.py` 作为写入并发控制核心路径，之前缺少系统级分支测试，存在“写入队列回归无感”的结构性风险。
- 本轮完成补测后，全量覆盖率稳定到 `52.06%`，具备门槛继续收敛到 `51` 的条件。

## 对标项目可借鉴点
- 成熟后端项目会优先覆盖“写队列/重试/批处理”这类基础设施模块，而不是只堆业务接口测试。
- 覆盖率上调采用“先补高风险基础模块 + 再抬门槛 + 守护测试”闭环，避免门槛与真实质量脱节。
- 对多线程模块，主流做法是用 fake session + mock worker 路径做确定性测试，不依赖真实线程调度。

## 差距清单（按 P0/P1/P2/P3）
- P1: `db_write_queue` 缺少核心回归保护（队列合并、分组执行、重试、worker 错误分支）。
  - 影响：并发写入错误可能在生产阶段才暴露。
  - 根因：历史优化更多聚焦 API/service，基础设施层补测滞后。
  - 建议：补齐提交、消费、执行、重试、状态与全局 helper 路径。
- P1: CI 门槛仍停留在 `50`，低于当前稳定可达值。
  - 影响：质量信号收敛速度偏慢。
  - 建议：在总覆盖率稳定 `52%+` 后小步上调到 `51` 并同步守护测试。

## 本轮要做的优化项
- 新增 `tests/test_db_write_queue.py`，覆盖写队列关键分支与异常路径。
- 将 workflow 默认覆盖率门槛从 `50` 提升到 `51`。
- 同步 `tests/test_pytest_workflow_coverage_gate.py` 的防回退断言下限到 `>=51`。
- 执行目标回归 + 全量 `--cov-fail-under=51` 强校验。

## 具体修改方案
- 新增 `quark_strm/tests/test_db_write_queue.py`
  - 覆盖点：
    - 单例初始化、`start/stop`、`submit_batch`
    - `submit` 的未运行/队列满/merge key 合并
    - `_get_batch` 批量提取、等待时间统计、merge cache 清理
    - `_execute_batch` 按模型分组与组级失败重试
    - `_execute_model_batch` 的未注册模型、成功回调、失败重试
    - `_execute_single_task` 的 `INSERT/UPDATE/DELETE/UPSERT(create_or_update/fallback)`
    - `_retry_task` 的重入队列与最终失败回调
    - `_worker_loop` 的批处理统计与异常日志路径
    - `get_status/get_metrics/clear` 与全局 helper（`get_write_queue/start_write_queue/stop_write_queue`）
- 更新 `quark_strm/.github/workflows/pytest.yml`
  - `COVERAGE_FAIL_UNDER` 从 `50` 提升到 `51`。
- 更新 `quark_strm/tests/test_pytest_workflow_coverage_gate.py`
  - 守护测试函数与断言同步为 `>=51`。

## 验证方案
- 模块测试：
  - `python -m pytest -q -o addopts='--tb=short -v' tests/test_db_write_queue.py`
- 模块覆盖：
  - `python -m pytest -q -o addopts='-v --tb=short --cov=app.core.db_write_queue --cov-report=term-missing' tests/test_db_write_queue.py`
- 门槛守护回归：
  - `python -m pytest -q -o addopts='--tb=short -v' tests/test_db_write_queue.py tests/test_pytest_workflow_coverage_gate.py tests/test_ci_workflow.py`
- 全量强校验：
  - `python -m pytest -q -o addopts='-v --tb=short --strict-markers --cov=app --cov-fail-under=51'`
- 结果：
  - `db_write_queue` 测试 `11 passed`，模块覆盖 `93.53%`
  - 全量 `808 passed, 2 skipped`
  - 总覆盖率 `52.06%`，满足 `--cov-fail-under=51`

## 本轮风险
- 门槛 `51` 目前有约 `1.06%` 缓冲，短期稳定性可接受，但大体量低覆盖模块（如 `cache_statistics`、`media/*`）仍是后续上调瓶颈。
- `db_write_queue` 尚有少量分支未覆盖，主要是特定 callback/线程退出细分路径，对主链路风险较低。

## 下一轮建议
1. 优先补 `app/services/cache_statistics.py`（当前 0%）的统计汇总与报告分支，扩大门槛 `51` 缓冲。
2. 若缓冲可达 `52%+` 且稳定，再评估门槛提升到 `52`。
3. 继续保持“基础设施优先 + 小步抬门槛 + 全量强校验”的节奏。

