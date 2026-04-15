# 2026-04-16 Iteration 16: Coverage Gate to 44

## 当前状态判断
- 在 `confidence` 补测后，总覆盖率稳定在 `45.16%`，已连续高于当前门槛 `43`。
- 现有门槛与实际质量区间仍有空档，回归告警灵敏度可继续收紧。
- 本轮目标是保持“小步抬升”策略，将门槛提升至 `44` 并验证稳定性。

## 对标项目可借鉴点
- 成熟项目在覆盖率治理中普遍采用“门槛递增 + 自动防回退断言”机制，避免门槛被意外放松。
- 上调门槛时必须配套全量回归证据，确保不是局部测试覆盖造成的假稳定。

## 差距清单（按 P0/P1/P2/P3）
- P1: 门槛 `43` 低于稳定覆盖率区间，质量下滑预警仍不够及时。
- P2: 门槛缓冲仅约 `1.16%`，后续新增低覆盖模块仍会带来 CI 波动风险。

## 本轮要做的优化项
- 将 `pytest` workflow 默认覆盖率门槛从 `43` 上调到 `44`。
- 同步更新守护测试断言到 `>=44`，确保门槛不会被回退。

## 具体修改方案
- 文件：`quark_strm/.github/workflows/pytest.yml`
  - `COVERAGE_FAIL_UNDER` 从 `"43"` 调整为 `"44"`。
- 文件：`quark_strm/tests/test_pytest_workflow_coverage_gate.py`
  - 测试名更新为 `test_pytest_workflow_coverage_threshold_not_below_44`；
  - 门槛断言更新为 `>=44`。

## 验证方案
- `python -m pytest -q -o addopts='--tb=short -v' tests/test_pytest_workflow_coverage_gate.py tests/test_ci_workflow.py`
- `python -m pytest -q -o addopts='-v --tb=short --strict-markers --cov=app --cov-fail-under=44'`
- 结果：全部通过；全量结果 `651 passed, 2 skipped`，总覆盖率 `45.16%`。

## 本轮风险
- 门槛缓冲仍较小，后续新增低覆盖代码更容易触发 CI 失败。
- 该风险可接受，需通过“功能改动同步补测”持续消化。

## 下一轮建议
1. 优先补 `app/services/scoring/tags.py` 与 `app/services/scoring/freshness.py` 分支，扩大评分链路覆盖缓冲。
2. 继续补 `app/services/security_audit_service.py` 中告警发送相关残余分支（如 `_send_security_alert`）。
3. 覆盖率稳定达到 `46%` 附近后，再评估门槛 `44 -> 45`。
