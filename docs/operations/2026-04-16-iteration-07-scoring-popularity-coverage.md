# 2026-04-16 Iteration 07: Scoring Popularity Coverage

## 当前状态判断
- `pytest --cov-fail-under=40` 全量通过：`604 passed, 2 skipped`。
- 总覆盖率从 `43.72%` 提升到 `43.74%`，提升幅度小但方向正确。
- 评分子模块中 `PopularityCalculator` 原先仅部分分支被覆盖，存在边界回归风险。

## 对标项目可借鉴点
- 成熟推荐/检索项目会优先为“评分函数”补齐单调性、边界值、上限截断测试，因为这类逻辑改动频繁且影响排序结果。
- 对纯计算模块采用“轻量单测优先”可以低成本抬高回归确定性，不依赖外部服务。

## 差距清单（按 P0/P1/P2/P3）
- P1: `PopularityCalculator` 缺少非正数与上限分支测试，热度算法改动后容易出现静默回归。
- P2: 评分体系其他模块（`quality`/`confidence`/`engine`）仍有较大覆盖缺口，影响后续抬升覆盖率门槛空间。

## 本轮要做的优化项
- 新增 `PopularityCalculator` 的分支单测，覆盖：
  - 非正数输入返回 0；
  - 对数增长区间；
  - 上限截断到 1.0。
- 保持现有业务代码不变，仅补验证。

## 具体修改方案
- 文件：`quark_strm/tests/test_scoring_popularity.py`
  - `test_calculate_returns_zero_for_non_positive_views`
  - `test_calculate_uses_logarithmic_growth_before_cap`
  - `test_calculate_caps_score_for_very_large_views`

## 验证方案
- `python -m pytest -q -o addopts='--tb=short -v' tests/test_scoring_popularity.py tests/test_pytest_workflow_coverage_gate.py tests/test_ci_workflow.py`
- `python -m pytest -q -o addopts='-v --tb=short --cov=app.services.scoring.popularity --cov-report=term-missing' tests/test_scoring_popularity.py`
- `python -m pytest -q -o addopts='-v --tb=short --strict-markers --cov=app --cov-fail-under=40'`
- 结果：全部通过；`app.services.scoring.popularity` 达到 `100%`，总体覆盖率 `43.74%`。

## 本轮风险
- 总覆盖率提升有限，短期内无法仅靠小模块补测继续大幅抬升门槛。
- 若后续对 `ScoringEngine` 做行为调整，当前仅热度子模块有保护，综合评分仍有回归窗口。

## 下一轮建议
1. 补 `app/services/scoring/engine.py` 的动态权重与低置信度旁路逻辑测试（高收益、文件体量小）。
2. 补 `app/services/scoring/quality.py` 的关键路径最小测试，优先把 `2%` 覆盖提升到可读区间。
3. 当覆盖率稳定达到 `44.5%+` 时，将 CI 门槛从 `40` 继续提升到 `42`。
