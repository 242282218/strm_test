# 2026-04-16 Iteration 29: Tiered Cache Coverage & Gate to 54

## 当前状态判断
- 门槛 `53` 阶段已稳定通过，但项目中仍有部分缓存基础设施模块覆盖不足，影响持续收敛效率。
- `app/services/tiered_cache.py` 是多级缓存核心调度模块，历史覆盖为 `0%`，L1/L2/L3 读写回填与降级路径缺少回归保护。
- 本轮补测后全量覆盖率提升到 `55.11%`，可以稳定支撑门槛上调到 `54`。

## 对标项目可借鉴点
- 成熟缓存架构项目会优先保障“多级回填和故障降级”路径测试，而非仅验证单层缓存读写。
- 对异步写队列/回退逻辑，通用做法是 fake backend + queue 控制，验证行为契约而不是依赖真实外部服务。
- 覆盖率上调继续采用“补关键基础模块 + 小步提门槛 + 守护测试”闭环。

## 差距清单（按 P0/P1/P2/P3）
- P1: `tiered_cache` 缺少核心分支覆盖（读取层级回填、写队列回退、预热与统计）。
  - 影响：缓存降级/回填回归可能导致性能退化或行为不一致。
  - 根因：此前测试聚焦 cache service 与统计模块，tiered 组合层未覆盖。
  - 建议：补齐 start/stop、worker、get/set/delete/clear/get_or_set/get_stats/warmup 关键路径。
- P1: CI 门槛仍在 `53`，低于当前稳定可达覆盖率。
  - 影响：质量门槛收紧速度偏慢。
  - 建议：上调到 `54` 并同步防回退断言。

## 本轮要做的优化项
- 新增 `tests/test_tiered_cache.py`，补齐多级缓存调度核心分支。
- 将 workflow 默认 `COVERAGE_FAIL_UNDER` 从 `53` 提升到 `54`。
- 同步 `tests/test_pytest_workflow_coverage_gate.py` 下限断言到 `>=54`。
- 执行目标回归与全量 `--cov-fail-under=54` 强校验。

## 具体修改方案
- 新增 `quark_strm/tests/test_tiered_cache.py`
  - 覆盖：
    - 枚举与全局单例 helper
    - `start/stop` 生命周期与异步写 worker
    - `get` 的 L1/L2/L3 命中与回填链路
    - `set` 的同步写、异步队列、队列满回退、L1 失败分支
    - `delete/clear/get_or_set`
    - `get_stats` 聚合返回
    - `warmup` 的空输入、L2 批量、L3 回填分支
- 更新 `quark_strm/.github/workflows/pytest.yml`
  - `COVERAGE_FAIL_UNDER` 调整为 `54`。
- 更新 `quark_strm/tests/test_pytest_workflow_coverage_gate.py`
  - 测试名与阈值断言同步为 `>=54`。

## 验证方案
- 模块测试：
  - `python -m pytest -q -o addopts='--tb=short -v' tests/test_tiered_cache.py`
- 模块覆盖：
  - `python -m pytest -q -o addopts='-v --tb=short --cov=app.services.tiered_cache --cov-report=term-missing' tests/test_tiered_cache.py`
- 门槛守护回归：
  - `python -m pytest -q -o addopts='--tb=short -v' tests/test_tiered_cache.py tests/test_pytest_workflow_coverage_gate.py tests/test_ci_workflow.py`
- 全量强校验：
  - `python -m pytest -q -o addopts='-v --tb=short --strict-markers --cov=app --cov-fail-under=54'`
- 结果：
  - `tests/test_tiered_cache.py`：`6 passed`
  - `app/services/tiered_cache.py`：`88.01%`
  - 全量：`832 passed, 2 skipped`
  - 总覆盖率：`55.11%`，满足门槛 `54`

## 本轮风险
- 门槛 `54` 当前缓冲约 `1.11%`，短期稳定。
- 大体量低覆盖模块仍集中在 `media/*`、`search_service`、`notification_service`，后续上调需继续补齐高收益路径。

## 下一轮建议
1. 优先补 `app/services/media/strm_generator.py` 或 `app/services/search_service.py` 关键分支，继续扩大缓冲。
2. 覆盖率稳定 `55.5%+` 后再评估门槛上调到 `55`。
3. 保持“补关键模块 -> 强校验 -> 门槛渐进”的节奏。

