# 2026-04-16 Iteration 01: Lifespan Hardening

## 当前状态判断
- 后端关键链路测试通过: `main entrypoint`、`v1 路由`、`dependencies`。
- 发现并修复的高优先级问题: FastAPI lifespan 使用 async generator 触发 Starlette 弃用告警，且启动失败时 watcher/container 清理不完整。
- 修复后，关键测试仅剩三方依赖告警 `python_multipart`，未再出现 lifespan 弃用告警。

## 对标项目可借鉴点
- FastAPI 官方推荐使用 `@asynccontextmanager` 管理应用生命周期，而非 async generator lifespan。
- 成熟服务模板通常将 startup/shutdown 的资源释放做成对称逻辑，确保 startup 任意阶段失败也会执行清理。
- 在回归层面，主流项目会为生命周期错误路径补专门测试，避免只测 happy path。

## 差距清单（按 P0/P1/P2/P3）
- P0: 生命周期实现与官方推荐模式不一致，框架升级时存在兼容性风险。
- P0: startup 失败路径未完整回收资源，可能导致 watcher 或服务容器残留。
- P1: 测试默认参数强制覆盖率门槛，日常只跑子集时容易误判失败，影响开发效率。
- P2: 代码库存在较多 Ruff 风格债务，影响可维护性和审查效率。
- P3: 文档中缺少按轮次沉淀的优化记录模板。

## 本轮要做的优化项
- 将 lifecycle 改造为 `asynccontextmanager`。
- 补齐 startup 异常路径清理。
- 新增生命周期回归测试，覆盖正常与异常路径。
- 清理本轮测试暴露的两处 Pydantic V2 弃用写法。

## 具体修改方案
- `app/config/lifecycle.py`
  - 新增 `_cleanup_lifespan_resources(...)`，统一 watcher/container 清理。
  - `lifespan(...)` 改为 `@asynccontextmanager`，启动异常和正常退出均执行清理。
  - `create_lifespan_context(...)` 改为 `@asynccontextmanager` 包装，避免 async-generator lifespan。
- `tests/test_lifecycle.py`
  - 新增 `test_lifespan_releases_resources_and_avoids_deprecation_warning`。
  - 新增 `test_lifespan_stops_watcher_when_startup_fails`。
- `app/schemas/auth.py`、`app/api/security.py`
  - 从 class `Config` 迁移到 `ConfigDict(from_attributes=True)`。

## 验证方案
- 执行命令:
  - `python -m pytest -q -o addopts='--tb=short -v' tests/test_lifecycle.py tests/test_main_entrypoint.py tests/test_api_v1_routes.py tests/test_dependencies.py`
- 验证结果:
  - `38 passed, 2 skipped`。
  - lifespan 弃用告警已消失。

## 本轮风险
- 本轮未处理全量 Ruff 风格债务，仍需后续分批清理。
- 覆盖率策略（`pytest.ini` 的 `--cov-fail-under=70`）与当前测试执行方式仍存在摩擦。

## 下一轮建议
1. 将覆盖率门槛从本地默认执行中解耦（保留 CI 强约束），避免日常子集测试被门槛噪音阻断。
2. 针对 `app/config/application.py` 的导入和路由注册逻辑做小范围重构，降低 lint 风险并提升可读性。
3. 选择一个高频 API 模块做 Pydantic V2 兼容清理模板，再批量推广。
