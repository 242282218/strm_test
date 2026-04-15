# 2026-04-16 Iteration 10: Coverage Gate to 42

## 当前状态判断
- 连续多轮补测后，总覆盖率稳定在 `43.95%`。
- 现有 CI 门槛为 `40` 时已经偏宽，无法及时反映覆盖率回落风险。
- 本轮目标是继续小步收敛门槛，保持“可达且有缓冲”。

## 对标项目可借鉴点
- 成熟项目通常按“可观测稳定区间”逐步抬门槛，而非一次性拉满，避免大面积误报。
- 覆盖率门槛必须有测试守护，否则配置可能在后续迭代中被无意回退。

## 差距清单（按 P0/P1/P2/P3）
- P1: CI 门槛与当前稳定覆盖率存在差距，质量告警灵敏度不足。
- P2: 低覆盖模块仍较多，后续继续抬门槛需要持续补测支撑。

## 本轮要做的优化项
- 将 `pytest.yml` 默认覆盖率门槛从 `40` 提升到 `42`。
- 同步更新门槛守护测试，确保阈值不被悄然下调。

## 具体修改方案
- 文件：`quark_strm/.github/workflows/pytest.yml`
  - `COVERAGE_FAIL_UNDER` 从 `"40"` 调整为 `"42"`。
- 文件：`quark_strm/tests/test_pytest_workflow_coverage_gate.py`
  - 门槛断言由 `>=40` 调整为 `>=42`。

## 验证方案
- `python -m pytest -q -o addopts='--tb=short -v' tests/test_pytest_workflow_coverage_gate.py tests/test_ci_workflow.py`
- `python -m pytest -q -o addopts='-v --tb=short --strict-markers --cov=app --cov-fail-under=42'`
- 结果：全部通过；全量结果 `618 passed, 2 skipped`，总覆盖率 `43.95%`。

## 本轮风险
- 当前覆盖率与新门槛缓冲约 `1.95%`，若新增低覆盖大模块，CI 失败概率会提高。
- 这是预期风险：门槛提升后需要开发阶段同步补测，避免“先写后补”造成反复失败。

## 下一轮建议
1. 补 `app/services/security_audit_service.py` 关键路径测试，提升安全链路覆盖。
2. 补 `app/services/scoring/quality.py` 的最小可验证测试，减少评分链路盲区。
3. 覆盖率稳定 `44.5%+` 后再评估将门槛提升到 `43`。
