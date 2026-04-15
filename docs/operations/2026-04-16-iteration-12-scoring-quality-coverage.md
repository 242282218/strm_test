# 2026-04-16 Iteration 12: Scoring Quality Coverage

## 当前状态判断
- 评分链路是搜索排序核心路径，但 `app/services/scoring/quality.py` 之前覆盖率极低。
- 本轮补测后，`quality.py` 覆盖率提升到 `96.00%`。
- 全量覆盖率同步提升到 `44.70%`，为后续门槛继续上调提供缓冲。

## 对标项目可借鉴点
- 成熟排序系统会优先验证“评分函数”的分支与边界，确保规则调整后排序行为可预测。
- 对纯函数评分模块采用小而密集的单测，能低成本提升回归可靠性。

## 差距清单（按 P0/P1/P2/P3）
- P1: 评分引擎 `engine` 与标签提取 `tags` 仍有明显覆盖缺口，跨模块协同回归风险仍在。
- P2: 安全告警发送路径 `_send_security_alert` 仍需独立补测，避免告警链路静默失败。

## 本轮要做的优化项
- 为 `QualityCalculator` 增加最小但关键的分支测试：
  - 空输入基线；
  - 4k/1080p 冲突惩罚；
  - 高质量标签上限截断；
  - `cn_sub` 字幕分支。

## 具体修改方案
- 文件：`quark_strm/tests/test_scoring_quality.py`
  - `test_calculate_returns_zero_without_quality_tags`
  - `test_calculate_applies_conflict_penalty_for_4k_and_1080p`
  - `test_calculate_caps_score_to_one_for_dense_high_quality_tags`
  - `test_calculate_uses_cn_sub_when_fx_sub_missing`

## 验证方案
- `python -m pytest -q -o addopts='-v --tb=short --cov=app.services.scoring.quality --cov-report=term-missing' tests/test_scoring_quality.py`
- `python -m pytest -q -o addopts='--tb=short -v' tests/test_scoring_quality.py tests/test_scoring_popularity.py`
- `python -m pytest -q -o addopts='-v --tb=short --strict-markers --cov=app --cov-fail-under=42'`
- 结果：全部通过；`quality.py` 覆盖率 `96.00%`，全量覆盖率 `44.70%`。

## 本轮风险
- 评分引擎整体逻辑仍依赖 `confidence`/`tags`/`freshness` 协同，当前仅补齐了 `quality` 子模块。
- 后续规则调整若跨多个评分子模块，仍需补充集成级断言防止权重联动回归。

## 下一轮建议
1. 补 `app/services/scoring/engine.py` 的动态权重与低置信度旁路分支测试。
2. 补 `app/services/security_audit_service.py` 的 `_send_security_alert` 发送路径单测。
3. 覆盖率稳定在 `44.5%+` 后继续收敛 CI 门槛到 `43`（本轮后已具备条件）。
