# 使用指南

**最后同步**: 2026-04-20  
**对应代码目录**: `app/main.py`、`web/package.json`、`web/playwright.config.ts`、`docs/guides/`

## 当前推荐入口

- [`startup_guide.md`](./startup_guide.md) - 本地开发环境启动、端口约定、最小验证和常见问题
- [`strm_playback_quickstart.md`](./strm_playback_quickstart.md) - 跑通 `网盘 -> STRM -> Emby/VLC` 的最短链路，支持 `redirect` / `webdav`

## 使用边界

- 安装与脚本真相源先看 [`../development/README.md`](../development/README.md) 和 [`../../web/README.md`](../../web/README.md)：
  - `npm ci` + `web/package-lock.json` 是当前 CI / 干净安装契约。
  - `pnpm run ...` 是当前本地日常执行入口。
- 部署、运行目录和容器约定不在本目录维护，统一看 [`../operations/README.md`](../operations/README.md)。
- API canonical path、探针和公开端点说明统一看 [`../api/README.md`](../api/README.md)。
