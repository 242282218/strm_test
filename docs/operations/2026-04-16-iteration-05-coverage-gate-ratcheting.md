# 2026-04-16 Iteration 05: Coverage Gate Ratcheting

## 当前状态判断
- `pytest` 全量回归覆盖率基线已稳定在 `43%+`，但 `quark_strm/.github/workflows/pytest.yml` 默认门槛仍是 `20`。
- 20 的门槛已经偏离现状，无法有效阻止覆盖率持续下滑。

## 对标项目可借鉴点
- 成熟项目会使用“渐进抬升”而非一次性拉满：在可达区间内提升阈值，同时配套防回退校验。
- 覆盖率阈值应被测试约束，避免后续被无意下调。

## 差距清单（按 P0/P1/P2/P3）
- P1: CI 覆盖率门槛显著低于当前可达水平，质量信号偏弱。
- P1: 缺少对阈值的自动化断言，存在“参数被悄悄下调”风险。

## 本轮要做的优化项
- 将 `pytest.yml` 默认覆盖率阈值从 20 提升到 35。
- 在 `tests/test_ci_workflow.py` 增加阈值下限断言（`>=35`）和参数引用断言。

## 具体修改方案
- 文件：`quark_strm/.github/workflows/pytest.yml`
  - `COVERAGE_FAIL_UNDER` 默认值改为 `"35"`。
- 文件：`quark_strm/tests/test_ci_workflow.py`
  - 新增正则解析 `COVERAGE_FAIL_UNDER` 的测试。
  - 断言 `--cov-fail-under=${{ env.COVERAGE_FAIL_UNDER }}` 仍被使用且阈值 `>=35`。

## 验证方案
- 命令：`python -m pytest -q tests/test_ci_workflow.py`
- 命令：`python -m pytest -q tests/test_ci_workflow.py tests/test_lifecycle.py tests/test_main_entrypoint.py tests/test_api_v1_routes.py tests/test_dependencies.py`
- 命令：`python -m pytest -q`
- 结果：全部通过；全量覆盖率仍为 `43.72%`（高于 35）。

## 本轮风险
- 覆盖率阈值提高后，若后续新增低覆盖模块但缺少配套测试，CI 失败概率会上升。
- 根仓库 `/.github/workflows/ci.yml` 的测试阶段仍未显式声明 `--cov-fail-under`，跨 workflow 策略尚未完全统一。

## 下一轮建议
1. 在根仓库 `ci.yml` 的测试步骤显式接入同一覆盖率阈值变量，统一门槛策略。
2. 当全量覆盖率连续稳定高于 45% 时，将阈值从 35 提升到 40。
3. 针对 `0%~20%` 覆盖率模块（如 `cache_statistics`、`disk_cache`）优先补最小回归测试，减少后续抬门槛阻力。
