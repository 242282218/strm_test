# 前端兼容层清单

**最后校验**: 2026-04-20  
**适用范围**: `web/src/views/*`、`web/src/api/*`、`web/src/components/*`、`web/src/stores/*`

## 状态定义

- `wrapper-active`: 仍为路由、测试或历史导入提供兼容入口；允许保留，不允许继续加业务逻辑。
- `wrapper-deprecated`: 只为剩余历史调用兜底；禁止新增引用，迁移完成后删除。
- `remove-after:<milestone>`: 记录删除前置条件，避免“知道该删但没人敢删”。

## Canonical import 规则

1. 新增页面、API、store、组件默认直接放进 `web/src/features/<domain>/` 或真正的共享目录。
2. feature 内部禁止反向导入根级 wrapper。
3. 根级 wrapper 只能保留转发，不承载类型分叉、状态或业务逻辑。
4. wrapper 数量变化时，必须同步更新本清单和文档 contract test。

## 当前数量

- 视图包装：19
- API 包装：15
- 组件包装：3
- Store 包装：2

## 视图包装（`web/src/views/*`）

| Wrapper | Canonical target | 状态 | 删除条件 |
| --- | --- | --- | --- |
| `web/src/views/CategoryStrategyView.vue` | `@/features/category-strategy/views/CategoryStrategyView.vue` | `wrapper-active` | `remove-after: router/tests/external imports 全部迁移` |
| `web/src/views/ConfigView.vue` | `@/features/config/views/ConfigView.vue` | `wrapper-active` | `remove-after: router/tests/external imports 全部迁移` |
| `web/src/views/DashboardView.vue` | `@/features/dashboard/views/DashboardView.vue` | `wrapper-active` | `remove-after: router/tests/external imports 全部迁移` |
| `web/src/views/EmbyMonitorView.vue` | `@/features/emby/views/EmbyMonitorView.vue` | `wrapper-active` | `remove-after: router/tests/external imports 全部迁移` |
| `web/src/views/FileManagerView.vue` | `@/features/file-manager/views/FileManagerView.vue` | `wrapper-active` | `remove-after: router/tests/external imports 全部迁移` |
| `web/src/views/FilesView.vue` | `@/features/quark/views/FilesView.vue` | `wrapper-active` | `remove-after: router/tests/external imports 全部迁移` |
| `web/src/views/LayoutView.vue` | `@/features/app-shell/views/LayoutView.vue` | `wrapper-active` | `remove-after: router/tests/external imports 全部迁移` |
| `web/src/views/LoginView.vue` | `@/features/auth/views/LoginView.vue` | `wrapper-active` | `remove-after: router/tests/external imports 全部迁移` |
| `web/src/views/NotFoundView.vue` | `@/features/app-shell/views/NotFoundView.vue` | `wrapper-active` | `remove-after: router/tests/external imports 全部迁移` |
| `web/src/views/NotificationHistoryView.vue` | `@/features/notifications/views/NotificationHistoryView.vue` | `wrapper-active` | `remove-after: router/tests/external imports 全部迁移` |
| `web/src/views/NotificationsView.vue` | `@/features/notifications/views/NotificationsView.vue` | `wrapper-active` | `remove-after: router/tests/external imports 全部迁移` |
| `web/src/views/ProxyServiceView.vue` | `@/features/proxy/views/ProxyServiceView.vue` | `wrapper-active` | `remove-after: router/tests/external imports 全部迁移` |
| `web/src/views/RenameView.vue` | `@/features/rename/views/RenameView.vue` | `wrapper-active` | `remove-after: router/tests/external imports 全部迁移` |
| `web/src/views/ScrapePathsView.vue` | `@/features/scrape/views/ScrapePathsView.vue` | `wrapper-active` | `remove-after: router/tests/external imports 全部迁移` |
| `web/src/views/ScrapeRecordsView.vue` | `@/features/scrape/views/ScrapeRecordsView.vue` | `wrapper-active` | `remove-after: router/tests/external imports 全部迁移` |
| `web/src/views/SearchView.vue` | `@/features/search/views/SearchView.vue` | `wrapper-active` | `remove-after: router/tests/external imports 全部迁移` |
| `web/src/views/SmartRenameView.vue` | `@/features/smart-rename/views/SmartRenameView.vue` | `wrapper-active` | `remove-after: router/tests/external imports 全部迁移` |
| `web/src/views/TasksView.vue` | `@/features/tasks/views/TasksView.vue` | `wrapper-active` | `remove-after: router/tests/external imports 全部迁移` |
| `web/src/views/WebDAVView.vue` | `@/features/webdav/views/WebDAVView.vue` | `wrapper-active` | `remove-after: router/tests/external imports 全部迁移` |

## API 包装（`web/src/api/*`）

| Wrapper | Canonical target | 状态 | 删除条件 |
| --- | --- | --- | --- |
| `web/src/api/categoryStrategy.ts` | `@/features/category-strategy/api/categoryStrategy` | `wrapper-active` | `remove-after: 历史导入迁移到 feature 路径` |
| `web/src/api/dashboard.ts` | `@/features/dashboard/api/dashboard` | `wrapper-active` | `remove-after: 历史导入迁移到 feature 路径` |
| `web/src/api/emby.ts` | `@/features/emby/api/emby` | `wrapper-active` | `remove-after: 历史导入迁移到 feature 路径` |
| `web/src/api/embyMonitor.ts` | `@/features/emby/api/monitor` | `wrapper-active` | `remove-after: 历史导入迁移到 feature 路径` |
| `web/src/api/file-manager.ts` | `@/features/file-manager/api/file-manager` | `wrapper-active` | `remove-after: 历史导入迁移到 feature 路径` |
| `web/src/api/fileManager.ts` | `@/features/file-manager/api/fileManager` | `wrapper-deprecated` | `remove-after: camelCase 导入全部删除，仅保留 file-manager canonical API` |
| `web/src/api/notification.ts` | `@/features/notifications/api/notification` | `wrapper-active` | `remove-after: 历史导入迁移到 feature 路径` |
| `web/src/api/proxy.ts` | `@/features/proxy/api/proxy` | `wrapper-active` | `remove-after: 历史导入迁移到 feature 路径` |
| `web/src/api/quark.ts` | `@/features/quark/api/quark` | `wrapper-active` | `remove-after: 历史导入迁移到 feature 路径` |
| `web/src/api/rename.ts` | `@/features/rename/api/rename` | `wrapper-active` | `remove-after: 历史导入迁移到 feature 路径` |
| `web/src/api/scrape.ts` | `@/features/scrape/api/scrape` | `wrapper-active` | `remove-after: 历史导入迁移到 feature 路径` |
| `web/src/api/search.ts` | `@/features/search/api/search` | `wrapper-active` | `remove-after: 历史导入迁移到 feature 路径` |
| `web/src/api/smartRename.ts` | `@/features/smart-rename/api/smartRename` | `wrapper-active` | `remove-after: 历史导入迁移到 feature 路径` |
| `web/src/api/systemConfig.ts` | `@/features/config/api/systemConfig` | `wrapper-active` | `remove-after: 历史导入迁移到 feature 路径` |
| `web/src/api/tasks.ts` | `@/features/tasks/api/tasks` | `wrapper-active` | `remove-after: 历史导入迁移到 feature 路径` |

## 组件包装（`web/src/components/*`）

| Wrapper | Canonical target | 状态 | 删除条件 |
| --- | --- | --- | --- |
| `web/src/components/CreateTaskDialog.vue` | `@/features/tasks/components/CreateTaskDialog.vue` | `wrapper-active` | `remove-after: 历史页面和测试改走 feature/shared 入口` |
| `web/src/components/EmbyConfigCard.vue` | `@/features/emby/components/EmbyConfigCard.vue` | `wrapper-active` | `remove-after: 历史页面和测试改走 feature/shared 入口` |
| `web/src/components/QuarkFileBrowser.vue` | `@/features/quark/components/QuarkFileBrowser.vue` | `wrapper-active` | `remove-after: 历史页面和测试改走 feature/shared 入口` |

## Store 包装（`web/src/stores/*`）

| Wrapper | Canonical target | 状态 | 删除条件 |
| --- | --- | --- | --- |
| `web/src/stores/file-manager.ts` | `@/features/file-manager/stores/file-manager` | `wrapper-active` | `remove-after: 历史导入迁移到 feature store` |
| `web/src/stores/search.ts` | `@/features/search/store/search` | `wrapper-active` | `remove-after: 历史导入迁移到 feature store` |

## 验证锚点

- `web/src/router/index.ts` 已直接引用 feature view，不再走 `web/src/views/*`。
- 已迁移业务域通常通过 `module-aliases.spec.ts` 锁定 wrapper 仍正确指向 feature 实现。
- `web/src/api/fileManager.ts` 仅作为 camelCase 兼容别名；同一 `/files/*` 接口的 canonical 类型定义已回收到 `web/src/features/file-manager/api/file-manager.ts`。
