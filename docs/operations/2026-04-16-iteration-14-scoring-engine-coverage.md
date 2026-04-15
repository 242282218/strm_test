# 2026-04-16 Iteration 14: Scoring Engine Coverage

## 当前状态判断
- 评分子模块覆盖已提升（quality/popularity），但评分总线 `ScoringEngine` 仍缺少关键分支保护。
- 本轮补测后，`app/services/scoring/engine.py` 达到 `100%` 覆盖。
- 全量覆盖率继续提升至 `44.88%`，并稳定通过门槛 `43`。

## 对标项目可借鉴点
- 成熟推荐系统会优先保证“聚合与决策层”覆盖，因为这里决定最终排序输出。
- 对边界阈值（如 alpha、gate）和旁路逻辑（低置信度短路）做显式测试能显著降低回归风险。

## 差距清单（按 P0/P1/P2/P3）
- P1: `security_audit_service._send_security_alert` 仍未单测，告警下发链路可观测性不足。
- P2: 评分链路中 `confidence`、`tags` 模块覆盖仍低，后续复杂规则变更风险仍在。

## 本轮要做的优化项
- 为 `ScoringEngine` 增加边界与主路径单测：
  - `_calculate_alpha` 分段边界；
  - `_calculate_pr_gate` 分段边界；
  - 低置信度旁路；
  - 常规组合打分路径。

## 具体修改方案
- 文件：`quark_strm/tests/test_scoring_engine.py`
  - `test_calculate_alpha_boundaries`
  - `test_calculate_pr_gate_boundaries`
  - `test_score_uses_low_confidence_bypass`
  - `test_score_combines_dimensions_when_confidence_not_low`

## 验证方案
- `python -m pytest -q -o addopts='-v --tb=short --cov=app.services.scoring.engine --cov-report=term-missing' tests/test_scoring_engine.py`
- `python -m pytest -q -o addopts='--tb=short -v' tests/test_scoring_engine.py tests/test_scoring_quality.py tests/test_scoring_popularity.py`
- `python -m pytest -q -o addopts='-v --tb=short --strict-markers --cov=app --cov-fail-under=43'`
- 结果：全部通过；全量结果 `643 passed, 2 skipped`，总覆盖率 `44.88%`。

## 本轮风险
- 评分聚合层已补齐，但上游输入质量（置信度/标签提取）仍可能影响最终排序稳定性。
- 覆盖率缓冲仍有限，持续集成阶段新增低覆盖代码会更容易触发门槛失败。

## 下一轮建议
1. 补 `app/services/security_audit_service.py` 的 `_send_security_alert` 单测（通知发送优先级与容错）。
2. 补 `app/services/scoring/confidence.py` 的核心分支测试。
3. 覆盖率稳定 `45%+` 后，评估将门槛从 `43` 提升到 `44`。
