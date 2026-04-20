# quark_strm Web

`web/` 是 `quark_strm` 的前端应用，基于 `Vue 3 + Vite + TypeScript + Element Plus + Pinia + Vue Router`。

## 开发命令

```sh
npm ci
# or: pnpm install
pnpm run dev
```

```sh
pnpm run lint --fix
pnpm run test:run
pnpm run test:smoke
pnpm run type-check
pnpm run build-only
```

常用附加命令：

```sh
pnpm run test
pnpm run test:coverage
pnpm run test:e2e
pnpm run preview
```

## 包管理约定

- `web/package-lock.json` 是当前 CI/干净安装的锁文件真相源；要严格复现 workflow，使用 `npm ci`。
- 本地日常开发与手工验证默认使用 `pnpm run ...` 调脚本。
- Playwright 自动拉起前端 dev server 时，当前仍按 [`playwright.config.ts`](./playwright.config.ts) 执行 `npm run dev -- --host ... --port ...`，这属于测试启动实现细节，不等于仓库已经完成 pnpm 锁文件迁移。

## E2E 运行约定

- `pnpm run test:e2e` 会默认先检查并自动拉起后端 `uvicorn app.main:app` 与前端 `npm run dev`；本地若同端口已有服务则直接复用，CI 则总是拉起新进程。
- Playwright 默认访问 `http://127.0.0.1:18099`，可用 `PLAYWRIGHT_BASE_URL` 覆盖；前端 dev server 会跟随这个地址启动，避免与常见本地 `3000` 端口冲突。
- Playwright 自动启动时，Vite dev proxy 默认转发到 `http://127.0.0.1:18000`，可用 `VITE_API_PROXY_TARGET` 或 `PLAYWRIGHT_API_TARGET` 覆盖；后端 `uvicorn` 会跟随该目标地址启动，避免与常见本地 `8000` 端口冲突。
- Playwright 本地默认使用 `2` 个 worker 且关闭 `fullyParallel`，避免压穿后端限流；可用 `PLAYWRIGHT_WORKERS` 和 `PLAYWRIGHT_FULLY_PARALLEL=true` 覆盖。
- 如果后端启用了认证且还没初始化管理员，`web/e2e/global-setup.ts` 会尝试调用 `/api/auth/init-admin`。自动启动后端时默认注入 `ADMIN_PASSWORD=admin`，也可显式覆盖。

示例：

```sh
pnpm run test:e2e
PLAYWRIGHT_BASE_URL=http://127.0.0.1:3001 VITE_API_PROXY_TARGET=http://127.0.0.1:18000 ADMIN_PASSWORD=admin pnpm run test:e2e
```

## 当前结构

前端已从“按页面/API 散落”逐步收口为“按业务域组织”的结构。新代码默认放到 `src/features/`，旧路径仅保留兼容包装。

```text
web/
├── src/
│   ├── api/           # 共享 API client + 旧 API 兼容导出
│   ├── assets/        # 静态资源
│   ├── components/    # 跨域共享组件 + 少量兼容包装
│   ├── composables/   # 通用组合式逻辑
│   ├── features/      # 业务域真实实现
│   ├── plugins/       # 插件装配
│   ├── router/        # 路由
│   ├── stores/        # 全局 store + 少量兼容包装
│   ├── utils/         # 通用工具
│   ├── views/         # 旧视图兼容入口
│   ├── App.vue
│   └── main.ts
├── package.json
├── vite.config.ts
├── vitest.config.ts
└── README.md
```

## 已收口的业务域

当前 `src/features/` 目录：

- `app-shell`
- `auth`
- `category-strategy`
- `config`
- `dashboard`
- `emby`
- `file-manager`
- `notifications`
- `proxy`
- `quark`
- `rename`
- `scrape`
- `search`
- `smart-rename`
- `tasks`
- `webdav`

每个业务域内部通常按下面的方式组织：

```text
src/features/<domain>/
├── api/
├── components/
├── stores/
├── views/
├── index.ts
└── module-aliases.spec.ts
```

不是每个域都会同时拥有 `components/`、`stores/` 或 `views/`，按实际需要保留。

## 兼容策略

为避免一次性改动路由、测试和外部导入：

- `src/views/*` 旧页面路径保留薄包装。
- `src/api/*` 旧 API 路径保留兼容导出。
- 少量 `src/components/*`、`src/stores/*` 旧路径也保留兼容包装。
- `module-aliases.spec.ts` 用于锁定“旧路径仍指向 feature 实现”。

当前约定：

- 新功能优先写到 `src/features/<domain>/`。
- feature 内部优先引用本域实现或共享模块。
- 不继续让 feature 内部反向依赖旧 `src/views/*`、`src/api/*` 包装层。

## 目录使用约定

### `src/api/`

- `index.ts` 是统一 API client。
- 其他文件分两类：
  - 仍是共享 API 封装。
  - 已降级为兼容导出层。

### `src/views/`

- 主要承担路由兼容入口。
- 真实页面实现优先位于对应 `features/*/views/`。

### `src/components/`

- 放跨域复用组件。
- 如果某组件强绑定某个业务域，优先放入该域的 `components/`。

### `src/stores/`

- 放真正的全局 store。
- 仅当历史路径兼容有需要时，才保留包装层。

## 当前验证基线

前端收口阶段以这三条命令作为基本回归：

```sh
pnpm run test:run
pnpm run type-check
pnpm run build-only
```

其中 `pnpm run test:smoke` 是更快的启动契约门禁，覆盖 app bootstrap、登录页回退和受保护壳层渲染，适合在改动路由、鉴权恢复、应用壳层时先跑一遍。

如果修改了路由、鉴权恢复、应用启动、兼容包装或 feature 导入路径，提交前至少跑完：

```sh
pnpm run test:smoke
pnpm run test:run
pnpm run type-check
pnpm run build-only
```

## Node 环境

`package.json` 当前要求：

- `node ^20.19.0 || >=22.12.0`

## 备注

- `ui` 相关打包产物仍然是当前体积大头，后续若继续优化，优先看 Element Plus 样式和共享 UI chunk。
- 文档最后同步日期：`2026-04-20`
