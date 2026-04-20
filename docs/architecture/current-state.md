# 当前状态基线

**最后校验**: 2026-04-20  
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
- `docs/operations/README.md` 已切到 `pnpm`，但 `web/README.md` 与 workflow 仍以 npm 命令为主，这是当前确认存在但本轮未处理的文档/执行漂移。

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
| `app/api/emby.py` | 975 | Emby 路由仍是最大的单体 API 模块 |
| `app/api/quark.py` | 895 | 夸克入口仍聚合多类能力 |
| `app/services/media/scrape.py` | 875 | 刮削流程与媒体领域逻辑耦合度高 |
| `app/core/cache_manager.py` | 739 | 核心缓存协调入口仍偏重 |
| `app/api/monitoring.py` | 707 | 监控 API 体量已接近配置热点 |
| `app/config/settings.py` | 700 | 配置 schema 仍集中在单文件 |
| `app/services/media/smart_rename.py` | 699 | 智能重命名服务职责偏多 |
| `app/api/scrape.py` | 673 | 刮削 API 仍较重 |
| `app/services/security_audit_service.py` | 643 | 安全审计服务已形成新的大模块 |
| `app/api/proxy.py` | 640 | 代理路由仍是后端入口热点 |

### 前端热点（`web/src/`）

| 路径 | 行数 | 说明 |
| --- | ---: | --- |
| `web/src/features/rename/views/RenameView.vue` | 1183 | 视图、状态、编辑与执行流程仍混在一个 SFC |
| `web/src/features/proxy/views/ProxyServiceView.vue` | 1029 | 代理配置与视图逻辑仍偏重 |
| `web/src/features/scrape/views/ScrapePathsView.vue` | 931 | 刮削路径工作台仍是重页面 |
| `web/src/features/dashboard/views/DashboardView.vue` | 912 | Dashboard 已拆一轮但页面仍重 |
| `web/src/features/config/views/ConfigView.vue` | 904 | Config 工作台仍是高风险脏切片 |
| `web/src/features/tasks/views/TasksView.vue` | 863 | 任务中心页面复杂度仍高 |
| `web/src/features/scrape/views/ScrapeRecordsView.vue` | 740 | 刮削记录页面仍未明显降体量 |
| `web/src/features/notifications/views/NotificationHistoryView.vue` | 725 | 通知历史页面仍较大 |
| `web/src/features/notifications/views/NotificationsView.vue` | 662 | 通知配置页仍集中多职责 |
| `web/src/features/smart-rename/views/SmartRenameView.vue` | 582 | 智能重命名页面仍值得继续拆分 |

### 测试热点（`tests/`）

| 路径 | 行数 | 说明 |
| --- | ---: | --- |
| `tests/test_emby_proxy_routing.py` | 2841 | Emby 路由回归面极大，改动成本高 |
| `tests/test_emby_gateway.py` | 1734 | Gateway 契约已形成大型保护网 |
| `tests/test_db.py` | 585 | 数据库真相源收敛时需优先关注 |
| `tests/test_db_pool.py` | 517 | 数据库基础设施回归面仍不小 |

## 4. 当前已确认约束

- `web/src/features/config/*` 当前已有大量未提交修改，本轮不直接深入该切片。
- `app/api/v1` 已是对外 canonical path 层，但内部仍依赖 legacy router 复用，不能误判为“已经彻底完成 API 分层”。
- 当前最安全的继续推进方式仍是：先固化文档、清单和 contract test，再进入更深层的拆分或删兼容层。
