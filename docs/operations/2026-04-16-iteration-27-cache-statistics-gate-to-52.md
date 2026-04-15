# 2026-04-16 Iteration 27: Cache Statistics Coverage & Gate to 52

## 当前状态判断
- 在门槛 `51` 下，项目可通过全量回归，但仍有多处 0% 模块影响下一轮收敛速度。
- `app/services/cache_statistics.py` 是缓存可观测性核心模块，历史覆盖为 `0%`，报告聚合与图表生成缺少回归保护。
- 本轮补测后，全量覆盖率提升到 `53.03%`，可稳定支撑门槛上调到 `52`。

## 对标项目可借鉴点
- 成熟项目会把“统计 + 报告 + 导出 + 可视化”链路作为一个闭环模块测试，而不是只测单个计数函数。
- 对图表输出，行业通用做法是断言产物类型/格式（如 PNG base64）而非逐像素比对，减少测试脆弱性。
- 覆盖率收敛采用“先补 0% 高价值模块，再小步抬门槛”的策略，保证质量信号和稳定性同步提升。

## 差距清单（按 P0/P1/P2/P3）
- P1: `cache_statistics` 缺少核心分支保护（趋势、报告、导出、可视化）。
  - 影响：缓存观测指标回归会被延迟发现，影响运维判断。
  - 根因：历史测试聚焦缓存读写功能，统计层未覆盖。
  - 建议：补齐统计计算、趋势分支、JSON 导出和图表输出路径。
- P1: CI 门槛仍停留在 `51`，低于当前可稳定达到的覆盖率。
  - 影响：质量门槛收敛速度偏慢。
  - 建议：在覆盖率稳定 `53%+` 后提升到 `52` 并同步守护测试。

## 本轮要做的优化项
- 新增 `tests/test_cache_statistics.py`，覆盖统计模块主链路与边界路径。
- 将 workflow 默认 `COVERAGE_FAIL_UNDER` 从 `51` 提升到 `52`。
- 同步更新 `tests/test_pytest_workflow_coverage_gate.py` 下限断言到 `>=52`。
- 补跑目标回归与全量 `--cov-fail-under=52` 强校验。

## 具体修改方案
- 新增 `quark_strm/tests/test_cache_statistics.py`
  - 覆盖：
    - `record_hit/record_miss/record_set/record_delete/record_eviction/record_expiration/get_current_stats`
    - `get_history_stats` 时间窗口过滤
    - `generate_performance_report` 空数据与聚合统计路径
    - `_calculate_trends/_calculate_slope` 边界分支
    - `export_stats_json/clear_history`
    - `CacheVisualizer` 的命中率图、内存图、空图、对比图（PNG base64）
    - 全局单例 helper：`get_cache_statistics/get_cache_visualizer`
- 更新 `quark_strm/.github/workflows/pytest.yml`
  - `COVERAGE_FAIL_UNDER` 调整为 `52`。
- 更新 `quark_strm/tests/test_pytest_workflow_coverage_gate.py`
  - 测试名和阈值断言同步到 `>=52`。

## 验证方案
- 模块测试：
  - `python -m pytest -q -o addopts='--tb=short -v' tests/test_cache_statistics.py`
- 模块覆盖：
  - `python -m pytest -q -o addopts='-v --tb=short --cov=app.services.cache_statistics --cov-report=term-missing' tests/test_cache_statistics.py`
- 门槛守护回归：
  - `python -m pytest -q -o addopts='--tb=short -v' tests/test_cache_statistics.py tests/test_pytest_workflow_coverage_gate.py tests/test_ci_workflow.py`
- 全量强校验：
  - `python -m pytest -q -o addopts='-v --tb=short --strict-markers --cov=app --cov-fail-under=52'`
- 结果：
  - `tests/test_cache_statistics.py`：`9 passed`
  - `app/services/cache_statistics.py`：`97.44%`
  - 全量：`817 passed, 2 skipped`
  - 总覆盖率：`53.03%`，满足门槛 `52`

## 本轮风险
- 门槛 `52` 当前缓冲约 `1.03%`，短期稳定，但仍受多个 0% 大模块拖累（如 `cache_warmer`、`tiered_cache`、`media/*`）。
- 图表相关测试依赖 matplotlib 环境；当前 CI 已安装依赖，风险可控。

## 下一轮建议
1. 优先补 `app/services/cache_warmer.py`（当前 0%）关键路径，继续扩大门槛缓冲。
2. 视覆盖率提升幅度评估门槛上调到 `53`（建议缓冲至少 `0.5%` 再上调）。
3. 继续保持“基础设施优先 + 门槛渐进 + 全量强校验”策略。

