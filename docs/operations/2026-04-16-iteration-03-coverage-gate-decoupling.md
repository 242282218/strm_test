# 2026-04-16 Iteration 03: Coverage Gate Decoupling

## 当前状态判断
- 之前本地默认 `pytest` 与覆盖率门槛强耦合，执行子集测试会因 `--cov-fail-under=70` 失败。
- 该行为会掩盖真实回归结果，降低日常修复效率。

## 对标项目可借鉴点
- 主流项目通常将覆盖率门槛放在 CI 中强约束，本地默认回归更关注快速反馈。
- 本地与 CI 策略分层能减少误报，同时保留质量红线。

## 差距清单（按 P0/P1/P2/P3）
- P1: 本地子集回归被覆盖率门槛阻断，开发体验与效率受影响。
- P1: `pytest.ini` 与 CI workflow 职责边界不清晰。
- P2: 覆盖率告警输出较长，需后续优化报告可读性。

## 本轮要做的优化项
- 将 `--cov-fail-under=70` 从 `pytest.ini` 默认 addopts 移除。
- 保留 `--cov=app`，保证本地仍产出覆盖率观察数据。
- 继续由 CI workflow 显式维持 `--cov-fail-under=70`。

## 具体修改方案
- `quark_strm/pytest.ini`
  - `addopts` 从 `-v --tb=short --strict-markers --disable-warnings --cov=app --cov-fail-under=70`
  - 调整为 `-v --tb=short --strict-markers --disable-warnings --cov=app`

## 验证方案
- 命令: `python -m pytest -q tests/test_ci_workflow.py tests/test_lifecycle.py tests/test_main_entrypoint.py tests/test_api_v1_routes.py tests/test_dependencies.py`
- 结果: `42 passed, 2 skipped`，本地默认执行不再被覆盖率阈值阻断。

## 本轮风险
- 当前关键子集覆盖率约 `24%`，说明测试覆盖仍偏低；若直接进入 CI，仍会被门槛拦截（符合预期）。

## 下一轮建议
1. 为高频核心链路补最小增量测试，优先提高覆盖率到可持续区间。
2. 在开发文档补充“本地回归 vs CI 门槛”执行建议，减少认知偏差。
3. 针对 `app/config/application.py` 做小范围重构并补测试，降低后续 lint 与维护风险。
