# 2026-04-16 Iteration 28: Cache Warmer Coverage & Gate to 53

## 当前状态判断
- 门槛 `52` 已稳定通过，但仍有多个 0% 模块会拖慢后续质量门槛收敛。
- `app/services/cache_warmer.py` 为缓存主动预热核心模块，之前覆盖为 `0%`，自动预热循环和失败重试链路没有回归保护。
- 本轮补测后，总覆盖率提升到 `53.90%`，足以将门槛进一步上调到 `53`。

## 对标项目可借鉴点
- 成熟缓存系统会将“访问学习 + 依赖预热 + 定时循环 + 失败退避”作为一体化测试目标，而不是单测单点函数。
- 对异步调度路径，推荐通过 mock `asyncio.create_task/sleep` 和 fake service 驱动验证，避免时间依赖导致 flaky。
- 覆盖率门槛上调继续采用“补 0% 基础模块 -> 留缓冲 -> 小步抬升”策略。

## 差距清单（按 P0/P1/P2/P3）
- P1: `cache_warmer` 缺少核心逻辑覆盖（预热策略分支、循环异常处理、调度预热路径）。
  - 影响：缓存预热失效会导致命中率退化，且难以及时发现。
  - 根因：历史测试集中在 cache read/write，未覆盖预热调度模块。
  - 建议：补齐策略预热、依赖链预热、自动循环与全局 helper 分支。
- P1: 门槛仍在 `52`，低于当前稳定覆盖能力。
  - 影响：质量门槛收紧不充分。
  - 建议：上调到 `53` 并同步守护测试。

## 本轮要做的优化项
- 新增 `tests/test_cache_warmer.py`，覆盖预热器核心异步分支和异常路径。
- 将 workflow 默认 `COVERAGE_FAIL_UNDER` 从 `52` 提升到 `53`。
- 将 `tests/test_pytest_workflow_coverage_gate.py` 下限同步为 `>=53`。
- 执行目标回归与全量 `--cov-fail-under=53` 强校验。

## 具体修改方案
- 新增 `quark_strm/tests/test_cache_warmer.py`
  - 覆盖：
    - pattern 排序、访问记录、依赖登记、统计汇总
    - `start_automatic_warming/stop_automatic_warming`
    - `_automatic_warming_loop` 异常路径（错误日志 + 60 秒退避）
    - `perform_comprehensive_warming` 调度顺序
    - `_warmup_by_patterns/_warmup_pattern` 的 user/movie/unmatched 分支与失败路径
    - `_warmup_by_access_patterns` 空历史与高频 key 预热分支
    - `_warmup_by_dependencies` 依赖链成功/失败分支
    - `schedule_warming` 调度与日志分支
    - `_discover_*` 和 `_load_*` 辅助函数
    - 全局 helper：`get_cache_warmer/setup_default_warming_patterns`
- 更新 `quark_strm/.github/workflows/pytest.yml`
  - `COVERAGE_FAIL_UNDER` 调整为 `53`。
- 更新 `quark_strm/tests/test_pytest_workflow_coverage_gate.py`
  - 测试名及断言下限同步为 `>=53`。

## 验证方案
- 模块测试：
  - `python -m pytest -q -o addopts='--tb=short -v' tests/test_cache_warmer.py`
- 模块覆盖：
  - `python -m pytest -q -o addopts='-v --tb=short --cov=app.services.cache_warmer --cov-report=term-missing' tests/test_cache_warmer.py`
- 门槛守护回归：
  - `python -m pytest -q -o addopts='--tb=short -v' tests/test_cache_warmer.py tests/test_pytest_workflow_coverage_gate.py tests/test_ci_workflow.py`
- 全量强校验：
  - `python -m pytest -q -o addopts='-v --tb=short --strict-markers --cov=app --cov-fail-under=53'`
- 结果：
  - `tests/test_cache_warmer.py`：`9 passed`
  - `app/services/cache_warmer.py`：`96.67%`
  - 全量：`826 passed, 2 skipped`
  - 总覆盖率：`53.90%`，满足门槛 `53`

## 本轮风险
- 门槛 `53` 当前缓冲约 `0.90%`，短期可接受，但仍不宜一次性跳升过大。
- 高体量低覆盖模块（`media/*`、`tiered_cache`）依旧是后续上调瓶颈。

## 下一轮建议
1. 优先补 `app/services/tiered_cache.py` 或 `app/services/media/strm_generator.py` 的关键分支，继续扩缓冲。
2. 若覆盖率稳定 `54.5%+`，再评估门槛上调到 `54`。
3. 继续坚持“先补基础设施/核心链路，再上调门槛”的节奏。

