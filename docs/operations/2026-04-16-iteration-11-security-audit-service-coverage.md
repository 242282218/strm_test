# 2026-04-16 Iteration 11: Security Audit Service Coverage

## 当前状态判断
- 安全 API 层覆盖已提升，但 `SecurityAuditService` 仍是核心盲区，直接影响告警分级与审计可信度。
- 本轮补测后，`app/services/security_audit_service.py` 覆盖率从低位提升到 `82.80%`。
- 全量覆盖率提升到 `44.30%`，并继续满足 CI 门槛 `42`。

## 对标项目可借鉴点
- 成熟安全审计实现会优先验证“决策逻辑”而非仅验证路由：分级、阈值、聚合、状态流转、告警调度都是核心。
- service 层采用纯单测（stub db + monkeypatch）能快速提升高风险逻辑可信度，且回归成本低。

## 差距清单（按 P0/P1/P2/P3）
- P1: `security_audit_service` 仍有部分分支未覆盖（通知发送实现、部分记录类方法）。
- P2: 评分质量链路覆盖率依旧偏低（`app/services/scoring/quality.py`），是下一阶段抬门槛阻力。

## 本轮要做的优化项
- 新增 `SecurityAuditService` 单测，覆盖核心决策与状态分支：
  - 分级阈值（登录失败/未授权访问）；
  - 注入检测；
  - 摘要聚合；
  - 事件确认/解决；
  - 告警调度在 loop 与无 loop 场景的行为。

## 具体修改方案
- 文件：`quark_strm/tests/test_security_audit_service.py`
  - 新增 17 个测试，覆盖：
    - 单例与初始化幂等；
    - `detect_injection_attempt`；
    - `check_brute_force`；
    - `record_login_failed` / `record_login_success` / `record_unauthorized_access`；
    - `record_sensitive_config_change`；
    - `get_security_summary`；
    - `acknowledge_event` / `resolve_event`；
    - `_schedule_security_alert` 两条分支。

## 验证方案
- `python -m pytest -q -o addopts='-v --tb=short --cov=app.services.security_audit_service --cov-report=term-missing' tests/test_security_audit_service.py`
- `python -m pytest -q -o addopts='--tb=short -v' tests/test_security_audit_service.py tests/test_security_api.py tests/test_security_api_filtering.py`
- `python -m pytest -q -o addopts='-v --tb=short --strict-markers --cov=app --cov-fail-under=42'`
- 结果：全部通过；全量结果 `635 passed, 2 skipped`，总覆盖率 `44.30%`。

## 本轮风险
- `_send_security_alert` 的通知内容拼装与异常路径仍未单测（涉及外部通知服务依赖）。
- 覆盖率增长主要来自安全链路，其他低覆盖大模块依然会影响后续门槛提升节奏。

## 下一轮建议
1. 补 `app/services/scoring/quality.py` 的最小可验证测试，优先覆盖主要评分分支。
2. 补 `security_audit_service._send_security_alert` 的轻量单测（通过 fake notification service 隔离外部依赖）。
3. 若覆盖率稳定在 `44.5%+`，评估将门槛从 `42` 提升到 `43`。
