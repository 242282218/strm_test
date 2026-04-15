# 2026-04-16 Iteration 19: Coverage Gate to 45

## 当前状态判断
- 在 `path_security` 补测后，总覆盖率稳定达到 `45.75%`。
- 门槛 `44` 已落后于当前稳定质量区间，存在可继续收紧空间。
- 本轮目标是延续渐进策略，将 CI 门槛提升到 `45` 并确保回归稳定。

## 对标项目可借鉴点
- 成熟项目会将覆盖率门槛与“稳定可达区间”保持同步，避免质量红线长期滞后。
- 门槛上调必须配套“守护测试 + 全量回归”双证据，防止配置回退或局部假通过。

## 差距清单（按 P0/P1/P2/P3）
- P1: 门槛 `44` 低于当前稳定覆盖率 `45.75%`，质量下滑预警敏感度不足。
- P2: 现有缓冲约 `0.75%`，需继续补关键模块覆盖避免后续门槛波动。

## 本轮要做的优化项
- 将 `pytest` workflow 默认覆盖率门槛从 `44` 提升到 `45`。
- 同步更新守护测试断言下限到 `>=45`。

## 具体修改方案
- 文件：`quark_strm/.github/workflows/pytest.yml`
  - `COVERAGE_FAIL_UNDER` 从 `"44"` 调整为 `"45"`。
- 文件：`quark_strm/tests/test_pytest_workflow_coverage_gate.py`
  - 测试名更新为 `test_pytest_workflow_coverage_threshold_not_below_45`；
  - 断言更新为 `>=45`。

## 验证方案
- `python -m pytest -q -o addopts='--tb=short -v' tests/test_pytest_workflow_coverage_gate.py tests/test_ci_workflow.py`
- `python -m pytest -q -o addopts='-v --tb=short --strict-markers --cov=app --cov-fail-under=45'`
- 结果：全部通过；全量结果 `671 passed, 2 skipped`，总覆盖率 `45.75%`。

## 本轮风险
- 门槛缓冲仍有限，后续若引入低覆盖代码，CI 失败概率将上升。
- 这是预期内质量约束，需通过“改动即补测”策略维持稳定。

## 下一轮建议
1. 补 `app/services/security_audit_service.py` 的告警发送与线程告警分支，提高安全链路覆盖。
2. 继续优先低耦合高风险模块（如安全、配置、边界工具层）来扩大门槛缓冲。
3. 覆盖率稳定达到 `46%+` 后，再评估门槛 `45 -> 46`。
