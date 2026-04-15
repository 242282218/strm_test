# 2026-04-16 Iteration 08: Security API Coverage Expansion

## 当前状态判断
- 安全接口是高风险入口，但此前 `app/api/security.py` 存在未覆盖分支（过滤参数解析、404 分支、元数据接口）。
- 本轮补测后，全量回归 `609 passed, 2 skipped`，总覆盖率从 `43.74%` 提升到 `43.86%`。
- `app/api/security.py` 覆盖率由 `66.42%` 提升到 `86.13%`。

## 对标项目可借鉴点
- 成熟后端项目通常优先为安全相关 API 补“输入解析 + 错误分支 + 元数据接口”测试，确保策略改动不会静默失效。
- 对高风险接口使用轻量依赖替身（mock service/dependency override）能在低成本下稳定覆盖关键逻辑。

## 差距清单（按 P0/P1/P2/P3）
- P1: 安全审计 service 层覆盖率仍偏低（`app/services/security_audit_service.py`），API 侧虽已提升但核心业务路径仍有盲区。
- P2: 评分子系统（`quality`/`engine`）仍是后续覆盖率抬升主要阻力。

## 本轮要做的优化项
- 新增安全 API 分支测试，覆盖：
  - `events` 过滤参数的有效/无效值处理；
  - 事件不存在时的 404 行为；
  - 枚举元数据接口返回完整性。

## 具体修改方案
- 文件：`quark_strm/tests/test_security_api_filtering.py`
  - `test_events_endpoint_parses_valid_filters_to_enum`
  - `test_events_endpoint_ignores_invalid_filters`
  - `test_get_security_event_returns_404_when_missing`
  - `test_mark_false_positive_returns_404_when_missing`
  - `test_enum_metadata_endpoints_return_values`

## 验证方案
- `python -m pytest -q -o addopts='--tb=short -v' tests/test_security_api_filtering.py tests/test_security_api.py`
- `python -m pytest -q -o addopts='-v --tb=short --strict-markers --cov=app --cov-fail-under=40'`
- 结果：全部通过；`app/api/security.py` 覆盖率显著提升，总体覆盖率 `43.86%`，继续满足门槛 `40`。

## 本轮风险
- 当前测试主要验证 API 层分支，安全审计 service 的复杂规则与聚合统计路径仍有未覆盖分支。
- 覆盖率提升依赖“高收益文件优先”，若后续新增低覆盖大模块，整体增幅仍可能被摊薄。

## 下一轮建议
1. 继续补 `app/services/security_audit_service.py` 的关键路径测试（查询过滤、统计摘要、状态流转）。
2. 针对 `app/services/scoring/quality.py` 增加最小可验证测试，提升评分链路确定性。
3. 覆盖率稳定在 `44%+` 后，评估将 CI 门槛从 `40` 提升到 `42`。
