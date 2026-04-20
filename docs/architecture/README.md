# 架构文档

**最后同步**: 2026-04-20  
**对应代码目录**: `app/`、`web/src/`、`.github/workflows/`、`docs/architecture/`

## 当前执行入口

- [`current-state.md`](./current-state.md) - 当前后端 / 前端 / CI 真相源、兼容层边界和热点分布
- [`core-truth-source-boundaries.md`](./core-truth-source-boundaries.md) - `config/db/exception` 当前职责边界与 Phase 3 进入说明
- [`../api/README.md`](../api/README.md) - API canonical path、legacy 映射和公开契约入口
- [`../operations/README.md`](../operations/README.md) - 部署命令、运行目录边界和本地产物约定入口
- [`../monitoring/README.md`](../monitoring/README.md) - `/metrics`、Prometheus 抓取配置和 Grafana 资产入口
- [`../development/codex-working-agreement.md`](../development/codex-working-agreement.md) - 给 Codex / 维护者的固定执行边界与最小验证基线

## 当前架构判断

- `app/main.py` + `app/config/application.py` 是后端应用装配真相源；路由如何注册，先看这里。
- `app/api/v1/__init__.py` 已是对外 canonical API 层，但内部仍复用部分 legacy router，不能误判成 v1-only 独立实现树。
- `web/src/router/index.ts` 已直接装配 `web/src/features/*/views/*`，根级 `web/src/views/*`、`web/src/api/*` 等目录仍主要承担兼容包装角色。
- 前端安装 / 验证契约以 `web/package-lock.json`、`web/playwright.config.ts` 和 `.github/workflows/docker-deploy-test.yml` 为准：
  - `npm ci` 是当前 CI / 干净安装真相源。
  - `pnpm run ...` 是当前本地开发与人工回归默认入口。

## 文档分工

| 文档 | 解决的问题 | 适合什么时候看 |
| --- | --- | --- |
| [`current-state.md`](./current-state.md) | 当前入口、热点和兼容层数量到底是什么 | 开始任何审查或重构前 |
| [`core-truth-source-boundaries.md`](./core-truth-source-boundaries.md) | `config/db/exception` 该从哪里下手 | 进入 Phase 3 前 |
| [`../api/README.md`](../api/README.md) | 新接口该落在哪层、旧路径如何映射 | 改 API 契约前 |
| [`../operations/README.md`](../operations/README.md) | 本地 / CI / Docker 命令和运行产物目录边界 | 改部署或执行验证前 |
| [`../monitoring/README.md`](../monitoring/README.md) | 指标、抓取配置和监控资产在哪里 | 改 `/metrics` 或监控配置前 |

## 当前不要误判的点

- 这个 README 只是架构索引，不是静态完整设计规格；涉及现状判断一律以 [`current-state.md`](./current-state.md) 为准。
- `web/src/features/config/*` 当前仍是高风险脏切片，除非是极小 blast radius 的真相源修正，不要直接把这里当作优先优化入口。
- `config/db/exception` 的主入口判断不要靠文件名猜，直接按 [`core-truth-source-boundaries.md`](./core-truth-source-boundaries.md) 的边界说明执行。
