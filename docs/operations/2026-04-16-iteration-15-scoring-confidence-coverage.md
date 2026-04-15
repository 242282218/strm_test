# 2026-04-16 Iteration 15: Scoring Confidence Coverage

## 当前状态判断
- 评分链路中 `confidence` 之前缺少核心分支保护，变更时易出现“分数漂移但测试未报警”。
- 本轮补测后，`app/services/scoring/confidence.py` 覆盖率达到 `95.24%`。
- 全量回归在门槛 `43` 下稳定通过：`651 passed, 2 skipped`，总覆盖率 `45.16%`。

## 对标项目可借鉴点
- 成熟排序系统会优先覆盖“决策权重输入层”，因为该层直接影响聚合评分稳定性。
- 对文本相似度、意图识别、低质量惩罚等关键分支做显式断言，可显著降低评分回归漏检。

## 差距清单（按 P0/P1/P2/P3）
- P1: 虽然 `confidence` 已补齐，但 `tags/freshness` 等评分子维度仍偏低，整体评分链路仍有局部盲区。
- P2: 覆盖率缓冲有限（45.16 vs gate 43），若后续新增低覆盖代码，门槛回归波动风险仍在。

## 本轮要做的优化项
- 为 `app/services/scoring/confidence.py` 增加核心分支单测，覆盖：
  - 文本相似度全匹配/空 bigram/非 ASCII token；
  - 意图评分负向词、ISO 例外、正向叠加上限；
  - 可信度计算中的低质量惩罚与中间分数字段更新。

## 具体修改方案
- 文件：`quark_strm/tests/test_scoring_confidence.py`
  - 新增 8 个测试用例，覆盖 `_text_similarity`、`_intent_score`、`_plausibility_score` 与 `calculate` 关键路径。
  - 重点断言：低质量文本触发 `confidence == 0.0`，高质量样本保持有界且中间分值可追踪。

## 验证方案
- `python -m pytest -q -o addopts='--tb=short -v' tests/test_scoring_confidence.py`
- `python -m pytest -q -o addopts='-v --tb=short --strict-markers --cov=app --cov-fail-under=43'`
- 结果：全部通过；`confidence.py` 覆盖 `95.24%`，全量总覆盖 `45.16%`。

## 本轮风险
- 评分链路仍有部分低覆盖维度，后续若这些模块发生重构，回归保护强度可能不足。
- 门槛上调空间存在但不大，需保持“小步收敛 + 全量验证”策略。

## 下一轮建议
1. 将 `pytest` workflow 覆盖率门槛从 `43` 提升到 `44`，并同步守护测试。
2. 继续补测评分子维度低覆盖模块（优先 `tags/freshness`）以扩展门槛缓冲。
3. 若覆盖率稳定维持 `45%+`，评估下一步门槛上调节奏（44 -> 45）。
