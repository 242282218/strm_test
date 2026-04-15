# 2026-04-16 Iteration 09: Lifecycle Coverage Expansion

## 当前状态判断
- 应用启动/关闭路径属于高风险区域，但此前 `app/config/lifecycle.py` 仍有大量未覆盖分支。
- 本轮补测后，`app/config/lifecycle.py` 覆盖率提升到 `98.13%`，总覆盖率提升到 `43.95%`。
- 全量门槛回归持续通过：`618 passed, 2 skipped`。

## 对标项目可借鉴点
- 成熟 FastAPI 项目会把 lifecycle 逻辑拆成可单测函数，并覆盖“成功/失败/幂等”三类路径。
- 对启动期依赖（容器、监控、WebDAV）使用 mock 隔离，可以在不引入外部副作用的前提下保障稳定性。

## 差距清单（按 P0/P1/P2/P3）
- P1: 安全审计 service（`app/services/security_audit_service.py`）仍有较大覆盖盲区，安全链路端到端保障不完整。
- P2: 评分质量模块覆盖率仍低，后续抬升整体门槛空间受限。

## 本轮要做的优化项
- 扩展 lifecycle 测试，覆盖初始化、失败兜底、WebDAV 挂载幂等和 initializer 分支。
- 保持生产代码不变，优先补齐验证闭环。

## 具体修改方案
- 文件：`quark_strm/tests/test_lifecycle.py`
  - 新增 `initialize_database` / `initialize_auth_system` 调用验证。
  - 新增 `start_service_container` 启动行为验证。
  - 新增 `configure_emby_cron` 成功与异常吞吐分支验证。
  - 新增 `initialize_monitoring` 成功与失败分支验证。
  - 新增 `mount_webdav` 的禁用、挂载成功、幂等跳过、初始化失败跳过验证。
  - 新增 `create_lifespan_context` 的 initializer 分支验证。

## 验证方案
- `python -m pytest -q -o addopts='-v --tb=short --cov=app.config.lifecycle --cov-report=term-missing' tests/test_lifecycle.py`
- `python -m pytest -q -o addopts='--tb=short -v' tests/test_lifecycle.py tests/test_main_entrypoint.py tests/test_ci_workflow.py`
- `python -m pytest -q -o addopts='-v --tb=short --strict-markers --cov=app --cov-fail-under=40'`
- 结果：全部通过；`app/config/lifecycle.py` 覆盖率 `98.13%`，总体覆盖率 `43.95%`。

## 本轮风险
- 生命周期路径已基本覆盖，但服务容器内部实现仍依赖其他模块测试质量。
- 覆盖率提升主要来自单模块高收益补测，后续继续提升需转向更复杂模块（维护成本更高）。

## 下一轮建议
1. 补 `app/services/security_audit_service.py` 的核心路径测试（查询过滤、统计摘要、状态流转）。
2. 对 `app/services/scoring/quality.py` 做最小可验证单测，降低评分链路盲区。
3. 当覆盖率稳定 `44%+` 后，将 CI 门槛由 `40` 提升到 `42`。
