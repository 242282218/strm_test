# 当前状态基线

**最后校验**: 2026-04-25  
**对应计划**: [`docs/plans/2026-04-20-codex-project-audit-optimization-plan.md`](../plans/2026-04-20-codex-project-audit-optimization-plan.md)  
**适用范围**: `quark_strm/`

## 1. 唯一入口现状

### 后端入口

- `app/main.py` 是 FastAPI 启动入口，应用装配和路由注册落在 `app/config/application.py`。
- `app/config/application.py` 仍显式拆成两层公共路由：
  - `register_legacy_routers()`：注册 legacy/support 路由，如 `quark`、`strm`、`proxy`、`emby`、`scrape`、`tasks`、`file_manager`、`rename`、`notification`、`system_config`。
  - `register_v1_and_support_routers()`：注册 `/api/v1` 聚合器，以及 `monitoring`、`prometheus`、`auth`、`security`、`emby_gateway` 等支持路由。
- `app/api/v1/__init__.py` 是当前对外 canonical contract 层，但不是完全独立的 v1-only 实现树：
  - `quark`、`strm`、`proxy`、`emby`、`tasks` 通过 `_register_canonical_routes()` 重新拼出 canonical v1 path。
  - `scrape`、`monitoring` 仍直接复用现有 router。

### 前端入口

- `web/src/router/index.ts` 已直接从 `@/features/*/views/*` 引入页面实现，router 不再依赖 `web/src/views/*` 包装层。
- 根级兼容包装仍保留在 `web/src/views/*`、`web/src/api/*`、`web/src/components/*`、`web/src/stores/*`。
- 兼容层清单与退役规则见 [`docs/development/compatibility-inventory.md`](../development/compatibility-inventory.md)。

### CI 与验证入口

- `.github/workflows/pytest.yml` 与 `.github/workflows/docker-deploy-test.yml` 统一使用 `vars.QUARK_STRM_COVERAGE_FAIL_UNDER || '66'` 作为 coverage 真相源。
- `docker-deploy-test.yml` 的前端门禁顺序固定为 `npm ci` -> `npm run lint` -> `npm run type-check` -> `npm run test:smoke` -> `npm run test:run` -> `npm run build-only`。
- `docs/operations/README.md`、`docs/development/README.md` 与 `web/README.md` 已显式区分两层约定：
  - `web/package-lock.json` + `npm ci` 是当前 CI/干净安装真相源。
  - `pnpm run ...` 是本地日常开发与人工回归的默认脚本入口。
- Playwright 自动启动前端 dev server 时，仍按 `web/playwright.config.ts` 执行 `npm run dev -- --host ... --port ...`；这是当前测试启动实现细节，不等于前端安装层已完成 pnpm 锁文件迁移。

## 2. 兼容层边界

- 视图包装：19
- API 包装：15
- 组件包装：3
- Store 包装：2

当前规则：

1. 新功能默认落在 `web/src/features/<domain>/`。
2. feature 内部禁止反向依赖根级 `src/views/*`、`src/api/*`、`src/components/*`、`src/stores/*` 包装层。
3. 删除 wrapper 前，先更新清单和对应 contract test。

## 3. 生产代码热点

### 后端热点（`app/`）

| 路径 | 行数 | 说明 |
| --- | ---: | --- |
| `app/api/emby.py` | 1153 | Emby 路由仍是最大的单体 API 模块 |
| `app/api/quark.py` | 1055 | 夸克入口仍聚合多类能力 |
| `app/services/media/scrape.py` | 968 | 刮削流程与媒体领域逻辑耦合度高 |
| `app/core/cache_manager.py` | 934 | 核心缓存协调入口仍偏重 |
| `app/api/monitoring.py` | 892 | 监控 API 体量已接近配置热点 |
| `app/config/settings.py` | 862 | 配置 schema 仍集中在单文件 |
| `app/services/media/smart_rename.py` | 850 | 智能重命名服务职责偏多 |
| `app/api/scrape.py` | 820 | 刮削 API 仍较重 |
| `app/api/proxy.py` | 772 | 代理路由仍是后端入口热点 |
| `app/services/security_audit_service.py` | 753 | 安全审计服务已形成新的大模块 |

### 前端热点（`web/src/`）

| 路径 | 行数 | 说明 |
| --- | ---: | --- |
| `web/src/features/rename/views/RenameView.vue` | 1326 | 视图、状态、编辑与执行流程仍混在一个 SFC |
| `web/src/features/proxy/views/ProxyServiceView.vue` | 1152 | 代理配置与视图逻辑仍偏重 |
| `web/src/features/scrape/views/ScrapePathsView.vue` | 1052 | 刮削路径工作台仍是重页面 |
| `web/src/features/dashboard/views/DashboardView.vue` | 1021 | Dashboard 已拆一轮但页面仍重 |
| `web/src/features/config/views/ConfigView.vue` | 1014 | Config 工作台仍是高风险脏切片 |
| `web/src/features/tasks/views/TasksView.vue` | 995 | 任务中心页面复杂度仍高 |
| `web/src/features/scrape/views/ScrapeRecordsView.vue` | 843 | 刮削记录页面仍未明显降体量 |
| `web/src/features/notifications/views/NotificationHistoryView.vue` | 830 | 通知历史页面仍较大 |
| `web/src/features/notifications/views/NotificationsView.vue` | 760 | 通知配置页仍集中多职责 |
| `web/src/features/smart-rename/views/SmartRenameView.vue` | 667 | 智能重命名页面仍值得继续拆分 |

### 测试热点（`tests/`）

| 路径 | 行数 | 说明 |
| --- | ---: | --- |
| `tests/test_emby_proxy_routing.py` | 3431 | Emby 路由回归面极大，改动成本高 |
| `tests/test_emby_gateway.py` | 2020 | Gateway 契约已形成大型保护网 |
| `tests/test_db.py` | 675 | 数据库真相源收敛时需优先关注 |
| `tests/test_dependencies.py` | 611 | 依赖注入边界测试面在持续扩大 |
| `tests/test_db_pool.py` | 550 | 数据库连接池回归面仍不小 |
| `tests/test_lru_cache.py` | 546 | 缓存基础设施测试规模已接近数据库热点 |
| `tests/test_strm_service.py` | 540 | STRM 服务回归面与 API 热点并行增长 |
| `tests/test_auth_middleware.py` | 535 | 认证中间件契约测试已形成较大保护网 |
| `tests/test_notification_service.py` | 523 | 通知服务行为覆盖开始进入大型测试模块 |
| `tests/test_strm_api.py` | 519 | STRM API 已去掉无效数据库兼容层假设，但仍是接口层回归锚点 |

## 4. 当前已确认约束

- `web/src/features/config/*` 当前已有大量未提交修改，本轮不直接深入该切片。
- `app/api/v1` 已是对外 canonical path 层，但内部仍依赖 legacy router 复用，不能误判为“已经彻底完成 API 分层”。
- 进入 Phase 3 前，先看 [`core-truth-source-boundaries.md`](./core-truth-source-boundaries.md)；当前 `config/db/exception` 仍应按“`db.py` 主入口 + `database.py` 兼容层 + `db_utils.py` 工具层 / `error_codes.py` 错误码 / `exceptions.py` 领域异常 / `exception_handler.py` HTTP 响应层”理解。
- `app/api/strm.py` 与 `app/api/dashboard.py` 都已不再依赖 `Database` 兼容层 caller；当前 `app/` 层显式 `Database(...)` 调用已清零，并由 `tests/test_db_path_contract.py` 锁定。
- `app/api/tmdb.py` 已不再直接 import `ConfigManager`；TMDB API key 读取统一走 `get_config_service()`，并由 `tests/test_tmdb_api.py` + `tests/test_db_path_contract.py` 锁定 canonical `tmdb.api_key` 优先、legacy `api_keys.tmdb_api_key` 回退和 API 层 import 护栏。
- `app/api/stable_stream.py` 也已移除 `get_config()` 全局实例；Quark cookie 改为请求时通过 `get_config_service()` 读取，并由 `tests/test_stable_stream_route.py` + `tests/test_db_path_contract.py` 锁定。
- `app/api/emby_gateway.py` 的 PlaybackInfo hook 也已移除 `get_config()` cookie 读取；专用 Emby 网关现在直接复用 `app_config.quark.cookie`，并由 `tests/test_emby_gateway.py` + `tests/test_db_path_contract.py` 锁定。
- `app/core/dependencies.py` 的 `get_quark_cookie()`、`get_only_video_flag()`、`get_root_id()` 也已移除 `get_config()` 全局实例；当前 Quark 依赖 helper 统一走 `get_config_service()`，并由 `tests/test_dependencies.py` + `tests/test_db_path_contract.py` 锁定。
- `app/api/proxy.py` 已移除 `get_config()` 全局实例；代理流、302、转码和缓存入口的 Quark cookie 统一通过 `get_config_service()` facade 读取，并由 `tests/test_emby_proxy_routing.py` + `tests/test_proxy_stream_contract.py` + `tests/test_db_path_contract.py` 锁定。
- `app/api/emby.py` 也已移除 `get_config()` 全局实例；本地 PlaybackInfo / item / stream / master 入口的 Quark cookie 改为通过 `get_config_service()` facade 读取，并由 `tests/test_emby_proxy_routing.py` + `tests/test_db_path_contract.py` 锁定。
- `app/api/quark.py` 也已移除 `get_config()` 全局实例；转码、配置与同步入口统一在请求期通过 `get_config_service()` 读取 `AppConfig.quark`，API 层 `config_manager` getter caller 已清零，并由 `tests/test_quark_api.py` + `tests/test_db_path_contract.py` 锁定。
- `app/services/token_monitor.py`、`app/services/webdav_fallback.py`、`app/core/path_security.py` 与 `app/services/ai_connectivity_service.py` 已移除 `config_manager` compatibility import：Quark cookie、WebDAV fallback 配置、允许目录补充读取和 AI provider map 统一通过 `get_config_service()` / `AppConfig.ai.providers` 读取，同时保留最小 helper 作为测试 patch 点，并由对应模块测试 + `tests/test_db_path_contract.py` 锁定。
- `app/services/link_resolver.py` 与 `app/services/storage/quark.py` 也已移除 `config_manager` compatibility import：AList runtime 配置和 Quark cookie 统一通过 `get_config_service()` facade 读取，并保留模块级 helper 作为测试 patch 点，由 `tests/test_link_resolver.py`、`tests/test_storage_quark_provider.py` 与 `tests/test_db_path_contract.py` 锁定。
- `app/services/emby_proxy_service.py` 也已移除未使用的 `get_config()` compatibility import / 全局实例；当前 Emby 代理、PlaybackInfo、媒体映射与回退逻辑不再依赖 `config_manager` 的模块级副作用，并由 `tests/test_emby_proxy_service.py`、`tests/test_stable_playback_hook.py` 与 `tests/test_db_path_contract.py` 锁定。
- `app/services/unified_ai_service.py` 已移除 `config_manager` compatibility import；统一 AI provider 列表改为通过 `get_config_service()` / `AppConfig.ai.get_enabled_providers()` 读取，`app/services/ai_parser_service.py` 也补齐了 `api_key` / `has_available_provider` / timeout 转发兼容契约，并由 `tests/test_unified_ai_service.py` + `tests/test_db_path_contract.py` 锁定。
- service/core 层还保留 5 个 `config_manager` compatibility caller：`app/services/integrations/emby.py`、`app/services/media/organize.py`、`app/services/media/rename.py`、`app/services/media/smart_rename.py`、`app/services/media/strm_generator.py`；当前只是 inventory 已锁定，还没进入逐模块清理。
- `tests/test_db_path_contract.py` 现在同时锁定 API 层不得回退到 `config_manager`、`path_security` / `token_monitor` / `webdav_fallback` / `ai_connectivity_service` / `link_resolver` / `storage/quark` / `emby_proxy_service` / `unified_ai_service` 不得回退，以及上述 5 个 service/core inventory，避免在未跟踪脏切片之外继续无声扩散。
- 当前最安全的继续推进方式仍是：先固化文档、清单和 contract test，再从上述 inventory 中挑干净切片逐个收口，而不是直接跨脏切片硬推。
