# 2026-04-16 Iteration 06: Coverage Gate to 40

## 当前状态判断
- 全量 `pytest` 回归稳定：`601 passed, 2 skipped`。
- 当前总覆盖率 `43.72%`，高于现有门槛 `35%`，但门槛与可达区间存在偏差，质量信号仍偏宽。

## 对标项目可借鉴点
- 成熟项目常用“渐进收紧 + 自动防回退”策略：每次上调到可稳定达成的区间，并用测试守护阈值配置。
- 阈值配置应集中在 workflow 环境变量，避免命令硬编码导致多处漂移。

## 差距清单（按 P0/P1/P2/P3）
- P1: `pytest` workflow 门槛低于当前稳定覆盖率，无法及时暴露覆盖率回落。
- P1: 对 `>=40` 阈值缺乏独立守护测试，存在被无意下调的风险。
- P2: `0%-20%` 覆盖率模块数量仍多，后续继续抬升门槛的缓冲空间有限。

## 本轮要做的优化项
- 将 `.github/workflows/pytest.yml` 默认 `COVERAGE_FAIL_UNDER` 从 `35` 提升到 `40`。
- 新增独立测试文件，守护 `pytest.yml` 的阈值下限与变量注入方式。

## 具体修改方案
- 文件：`quark_strm/.github/workflows/pytest.yml`
  - `COVERAGE_FAIL_UNDER` 默认值调整为 `"40"`。
- 文件：`quark_strm/tests/test_pytest_workflow_coverage_gate.py`
  - 新增 `test_pytest_workflow_coverage_threshold_not_below_40`：
    - 断言 `--cov-fail-under=${{ env.COVERAGE_FAIL_UNDER }}` 仍被使用。
    - 断言 `COVERAGE_FAIL_UNDER` 解析值 `>=40`。

## 验证方案
- `python -m pytest -q -o addopts='--tb=short -v' tests/test_ci_workflow.py`
- `python -m pytest -q -o addopts='--tb=short -v' tests/test_pytest_workflow_coverage_gate.py tests/test_ci_workflow.py`
- `python -m pytest -q -o addopts='-v --tb=short --strict-markers --cov=app --cov-fail-under=40'`
- 结果：全部通过；覆盖率 `43.72%`，满足新门槛。

## 本轮风险
- 新增低覆盖代码若无配套测试，CI 失败概率将上升（这是预期的质量约束，不是误报）。
- 由于当前覆盖率与门槛缓冲约 `3.72%`，大体量重构会更容易触发门槛告警。

## 下一轮建议
1. 针对 `0%` 覆盖模块先补最小烟雾测试（优先 `app/core/audit_log.py`、`app/core/db_loader.py`、`app/core/db_pool_monitor.py`）。
2. 在覆盖率稳定达到 `45%+` 后，继续将门槛提升到 `42` 或 `43`，保持“低风险小步收敛”。
3. 保持每轮只做一类质量策略变更（门槛、warning gate、模块补测三者分轮），降低定位复杂度。
