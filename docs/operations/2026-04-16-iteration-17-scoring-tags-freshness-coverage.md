# 2026-04-16 Iteration 17: Scoring Tags/Freshness Coverage

## 当前状态判断
- 评分链路中 `tags` 与 `freshness` 之前缺少独立单测，规则回归信号不足。
- 本轮补测后，两模块核心分支已被显式覆盖并通过模块级验证。
- 全量回归结果提升为 `658 passed, 2 skipped`，总覆盖率从 `45.16%` 提升到 `45.25%`（门槛 `44` 通过）。

## 对标项目可借鉴点
- 成熟排序系统会确保“特征提取 + 时间衰减”均有确定性测试，避免排序抖动无法定位。
- 对正则标签提取需覆盖多语种与符号变体，对时间衰减需使用固定时钟保证测试可重复。

## 差距清单（按 P0/P1/P2/P3）
- P1: 虽已补齐 `tags/freshness`，但覆盖率距下一门槛候选 `45` 缓冲仍有限。
- P2: 安全审计告警发送路径等高风险分支仍有补测空间。

## 本轮要做的优化项
- 新增 `TagExtractor` 分支测试：无匹配、多标签匹配、中文标签匹配、符号变体匹配。
- 新增 `FreshnessCalculator` 分支测试：空值/异常回退、过去时间指数衰减、未来时间上限。

## 具体修改方案
- 文件：`quark_strm/tests/test_scoring_tags.py`
  - 新增 4 个测试，覆盖 `TAG_PATTERNS` 主要匹配路径。
- 文件：`quark_strm/tests/test_scoring_freshness.py`
  - 新增 3 个测试，使用 monkeypatch 固定 `datetime.now` 保证可重复。

## 验证方案
- `python -m pytest -q -o addopts='--tb=short -v' tests/test_scoring_tags.py tests/test_scoring_freshness.py`
- `python -m pytest -q -o addopts='-v --tb=short --cov=app.services.scoring.tags --cov-report=term-missing' tests/test_scoring_tags.py`
- `python -m pytest -q -o addopts='-v --tb=short --cov=app.services.scoring.freshness --cov-report=term-missing' tests/test_scoring_freshness.py`
- `python -m pytest -q -o addopts='-v --tb=short --strict-markers --cov=app --cov-fail-under=44'`
- 结果：全部通过；全量 `658 passed, 2 skipped`，总覆盖率 `45.25%`。

## 本轮风险
- 覆盖率增长有限，尚不足以安全上调到 `45` 门槛。
- 若后续新增低覆盖模块，门槛缓冲仍可能被快速消耗。

## 下一轮建议
1. 补 `app/services/security_audit_service.py` 的告警发送残余分支，争取将总覆盖推至 `45.5%+`。
2. 达到稳定阈值后再评估门槛 `44 -> 45`，并同步守护测试断言。
3. 持续优先补“高风险决策层”而非低价值表层分支。
