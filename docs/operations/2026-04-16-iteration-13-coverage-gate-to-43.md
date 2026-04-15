# 2026-04-16 Iteration 13: Coverage Gate to 43

## 当前状态判断
- 总覆盖率在最近补测后稳定达到 `44.70%`。
- 现有门槛 `42` 已低于当前稳定区间，质量信号仍有松弛空间。
- 本轮目标是继续小步上调门槛，保持 CI 约束与实际质量水平一致。

## 对标项目可借鉴点
- 成熟项目采用“增量门槛 + 自动守护”策略：每次上调 1-2 个点，并配套测试断言防回退。
- 在门槛提升时同步跑全量回归是关键，避免局部通过掩盖整体风险。

## 差距清单（按 P0/P1/P2/P3）
- P1: 门槛 `42` 与当前稳定覆盖率 `44.70%` 存在差距，回落告警不够敏感。
- P2: 低覆盖大模块仍存在，后续继续上调门槛需要持续补测支撑。

## 本轮要做的优化项
- 将 `pytest` workflow 默认覆盖率门槛从 `42` 提升到 `43`。
- 同步更新门槛守护测试下限到 `>=43`。

## 具体修改方案
- 文件：`quark_strm/.github/workflows/pytest.yml`
  - `COVERAGE_FAIL_UNDER` 从 `"42"` 调整为 `"43"`。
- 文件：`quark_strm/tests/test_pytest_workflow_coverage_gate.py`
  - 测试名更新为 `...not_below_43`；
  - 门槛断言更新为 `>=43`。

## 验证方案
- `python -m pytest -q -o addopts='--tb=short -v' tests/test_pytest_workflow_coverage_gate.py tests/test_ci_workflow.py`
- `python -m pytest -q -o addopts='-v --tb=short --strict-markers --cov=app --cov-fail-under=43'`
- 结果：全部通过；全量结果 `639 passed, 2 skipped`，总覆盖率 `44.70%`。

## 本轮风险
- 目前覆盖率缓冲约 `1.70%`，后续大体量低覆盖改动会更容易触发 CI 失败。
- 该风险是可接受的质量约束，需通过“功能提交同步补测”来消化。

## 下一轮建议
1. 补 `app/services/scoring/engine.py` 分支测试，提升评分链路整体覆盖。
2. 补 `app/services/security_audit_service.py` 的 `_send_security_alert` 路径测试。
3. 若覆盖率稳定 `45%+`，评估将门槛从 `43` 进一步提升到 `44`。
