# 2026-04-16 Iteration 21: Coverage Gate to 46

## 当前状态判断
- 全量覆盖率已稳定达到 `46.17%`，门槛 `45` 已低于当前稳定质量区间。
- 继续保持“1 点递增 + 全量验证”可在控制风险的前提下增强质量红线。

## 对标项目可借鉴点
- 头部项目通常通过“门槛参数化 + 守护测试 + 全量回归”形成覆盖率防回退闭环。
- 门槛抬升必须以可重复的全量结果为依据，避免局部测试误导决策。

## 差距清单（按 P0/P1/P2/P3）
- P1: 门槛 `45` 已滞后于稳定覆盖率 `46.17%`，质量告警仍有迟滞。
- P2: 当前缓冲约 `0.17%`，后续需继续补关键模块以降低门槛波动风险。

## 本轮要做的优化项
- 将 `pytest` workflow 默认覆盖率门槛从 `45` 提升到 `46`。
- 同步更新守护测试断言为 `>=46`。

## 具体修改方案
- 文件：`quark_strm/.github/workflows/pytest.yml`
  - `COVERAGE_FAIL_UNDER` 从 `"45"` 调整为 `"46"`。
- 文件：`quark_strm/tests/test_pytest_workflow_coverage_gate.py`
  - 测试名更新为 `test_pytest_workflow_coverage_threshold_not_below_46`；
  - 断言更新为 `>=46`。

## 验证方案
- `python -m pytest -q -o addopts='--tb=short -v' tests/test_pytest_workflow_coverage_gate.py tests/test_ci_workflow.py`
- `python -m pytest -q -o addopts='-v --tb=short --strict-markers --cov=app --cov-fail-under=46'`
- 结果：全部通过；全量结果 `694 passed, 2 skipped`，总覆盖率 `46.17%`。

## 本轮风险
- 门槛缓冲偏窄，后续引入大体量低覆盖代码时 CI 失败概率会上升。
- 风险可控，需继续坚持“高风险模块优先补测”的迭代策略。

## 下一轮建议
1. 补 `app/services/security_audit_service.py` 的告警发送与线程告警分支。
2. 优先选择低耦合高收益模块继续扩大覆盖率缓冲（目标 `46.5%+`）。
3. 维持门槛渐进收敛，不做跨多点的激进上调。
