# Smart Media 投产可行性与同类项目分析报告

**日期**: 2026-04-27
**范围**: `D:\PROJECT_ZZZZZZZZZ\smart_media\quark_strm`
**项目根**: `git rev-parse --show-toplevel` 指向 `quark_strm/`，外层 `smart_media/` 不是当前 Git 仓库
**结论级别**: 当前适合单机试运行和受控内测；不建议直接作为多用户、公网、长期无人值守生产系统投入使用

## 1. 执行摘要

Smart Media / `quark_strm` 的核心定位不是传统 NAS 下载自动化，也不是通用网盘文件管理，而是“夸克网盘内容 -> STRM 文件 -> Emby/Jellyfin 可播放媒体库”的垂直链路。项目已经具备 FastAPI 后端、Vue 管理端、SQLite 数据存储、Docker/Compose、监控入口、较大规模自动化测试和持续优化脚本，基础资产并不薄。

但投产风险也很集中：API 仍处于 legacy 与 `/api/v1` 双轨并行，任务执行和配置 watcher 依赖进程内状态，Docker 默认多 worker 会放大状态分裂，数据库缺少正式 schema version / migration 链，生产默认安全配置仍可被配置为无认证，前端构建产物被复制进镜像但当前 FastAPI 没有明确挂载 SPA 静态文件。测试资产多，但 CI 中前端单测/E2E、安全扫描阻断策略、部署级验收还没有形成统一硬门禁。

推荐路线不是重写，而是先做“投产硬化”：单 worker 明确化、安全强制化、数据库迁移化、前端交付明确化、CI 门禁闭环化、任务执行持久化。完成这些后，再进入插件化、多云盘 provider、API v1 独立实现和前端大页面拆分。

## 2. 本次研究方法

本报告基于以下证据形成：

- 本地代码和文档只读分析：`app/`、`web/`、`tests/`、`docs/`、`Dockerfile`、`docker-compose.yml`、`.github/workflows/`。
- 三个并行 agent 结果：代码架构、测试/CI、同类 GitHub 项目调研。
- GitHub 一手来源调研：
  - [Cp0204/SmartStrm](https://github.com/Cp0204/SmartStrm)
  - [Cp0204/Quark-Auto-Save](https://github.com/Cp0204/Quark-Auto-Save)
  - [jxxghp/MoviePilot](https://github.com/jxxghp/MoviePilot)
  - [AlistGo/alist](https://github.com/AlistGo/alist)
  - [jiangrui1994/CloudSaver](https://github.com/jiangrui1994/CloudSaver)
  - [EstrellaXD/Auto_Bangumi](https://github.com/EstrellaXD/Auto_Bangumi)
  - [Sonarr/Sonarr](https://github.com/Sonarr/Sonarr)
  - [Radarr/Radarr](https://github.com/Radarr/Radarr)
  - [Cloudbox/autoscan](https://github.com/Cloudbox/autoscan)
  - [rclone/rclone](https://github.com/rclone/rclone)
  - [cloudreve/Cloudreve](https://github.com/cloudreve/Cloudreve)
  - [jellyfin/jellyfin](https://github.com/jellyfin/jellyfin)

## 3. 当前项目画像

### 3.1 代码规模快照

| 指标 | 当前值 | 说明 |
| --- | ---: | --- |
| 后端 Python 文件 | 190 | `app/` 下业务、基础设施、模型、API 均较完整 |
| 后端测试文件 | 115 | `tests/test_*.py` 数量多，已有契约测试基础 |
| 前端 Vitest spec | 60 | `web/src/**/*.spec.ts` 覆盖路由、store、feature 片段 |
| 前端 Playwright spec | 20 | `web/e2e/*.spec.ts` 已有端到端测试入口 |
| Python 最大文件 | 979 行 | `app/api/emby.py`，其次是 `app/api/quark.py`、`app/services/media/scrape.py` |
| 前端最大文件 | 1183 行 | `web/src/features/rename/views/RenameView.vue` |
| 测试最大文件 | 2871 行 | `tests/test_emby_proxy_routing.py`，说明 Emby/代理链路回归面大 |

### 3.2 核心业务流

1. 前端 Vue 应用进入登录、Dashboard、任务、搜索、刮削、重命名、Emby、代理、配置等页面。
2. 前端 Axios 客户端访问后端 `/api`，浏览器登录态依赖 HttpOnly Cookie，非 GET 请求携带 CSRF token。
3. 后端通过 Quark API 获取目录、文件、下载/转码链接。
4. STRM 生成器扫描夸克目录，把远端媒体文件写成本地 `.strm`。
5. Emby/Jellyfin 扫描 `.strm` 后，播放请求进入 Smart Media 的代理或 302 链路。
6. 播放链路根据配置选择直链、代理流、转码或 WebDAV fallback。
7. 刮削/重命名通过 TMDB、AI provider 和 Emby 命名规则把文件结构标准化。
8. 任务、通知、监控、缓存、配置热更新支撑长流程运维。

### 3.3 主要入口

| 层 | 当前入口 | 状态 |
| --- | --- | --- |
| FastAPI app | `app/main.py` | 创建 app、健康探针、中间件、路由注册 |
| 路由装配 | `app/config/application.py` | 同时注册 legacy 与 v1/support 路由 |
| v1 聚合 | `app/api/v1/__init__.py` | 通过复制已有 router route 暴露 canonical v1 path，不是独立实现树 |
| 配置 schema | `app/config/settings.py` | `AppConfig` 仍是配置 schema 聚合入口 |
| 运行时配置 | `app/services/config_service.py` | 单例、读写、watcher、回滚、通知都在一个类里 |
| 数据库 | `app/core/db.py` | SQLAlchemy engine/session 主入口，SQLite WAL/PRAGMA 已配置 |
| 前端入口 | `web/src/main.ts`、`web/src/router/index.ts` | 路由已转向 feature 目录 |
| 部署 | `Dockerfile`、`docker-compose.yml` | 镜像构建和 Compose 运行已具备 |

## 4. 与同类项目对比

| 项目 | 定位 | 可借鉴点 | 与 Smart Media 的关系 |
| --- | --- | --- | --- |
| SmartStrm | 媒体库 STRM 文件生成工具，强调多驱动、定时任务、联动触发、302 播放、插件系统、TMDB 识别 | 云盘到媒体库的产品化路径、插件系统、联动触发、302 直链体验 | 最接近的直接竞品/参考。Smart Media 的 Emby 代理链路更深，但 SmartStrm 在多驱动、插件和产品闭环上更成熟 |
| Quark-Auto-Save | 夸克签到、自动转存、命名整理、推送、刷新媒体库 | 资源订阅、自动转存、定时刷新、避免过高频率导致账号风控 | Smart Media 可借鉴其“资源入口和追更”能力，但不应把转存逻辑硬塞进 STRM 核心 |
| CloudSaver | 网盘资源搜索与转存，支持多源搜索、移动端适配、Docker 部署 | 资源发现、转存 UI、私有化安全提醒 | 可补齐 Smart Media 的“内容来源”前置环节 |
| MoviePilot | 自动化媒体管理，FastAPI + Vue3，Docker，插件生态 | 插件隔离、订阅到入库闭环、配置体验 | 可借鉴插件生态和自动化流程，但 Smart Media 应保持夸克 STRM / 播放链路差异化 |
| AList | 多存储文件列表程序，支持多种云存储和 WebDAV | provider 抽象、WebDAV 兼容、多存储聚合 | Smart Media 不应重做完整 AList，但 provider 边界和 WebDAV 兼容值得学习 |
| AutoBangumi | RSS 全自动追番整理，媒体库友好命名 | 番剧季集模型、订阅刷新、低干预自动化 | 对动漫/剧集识别和季集偏移很有参考价值 |
| Sonarr/Radarr | 成熟剧集/电影自动化，RSS/索引器、下载器、质量配置、重命名、失败重试 | 质量 profile、命名模板、手动匹配、失败重试、队列透明度 | 不处理夸克 STRM，但任务状态机和媒体命名产品体验是标杆 |
| Autoscan | 文件变化/下载器事件触发 Plex/Emby/Jellyfin 局部扫描 | 扫描队列、防抖、去重、多媒体服务器目标 | 可把 Emby 刷新从“顺手调用”升级为可靠子系统 |
| rclone / Cloudreve | 通用云存储同步/文件管理，多 provider | 存储 provider、传输、挂载/下载模型 | 适合作为存储抽象参考，不是媒体自动化竞品 |
| Jellyfin | 媒体服务器 | STRM 消费端之一，验证播放兼容性必须覆盖 | Smart Media 应以 Jellyfin/Emby 客户端真实播放作为投产验收 |

### 4.1 差异化判断

Smart Media 最有价值的差异化是“夸克网盘 + STRM + Emby/Jellyfin 播放代理 + WebDAV fallback + AI/TMDB 重命名”的交叉能力。它不需要在第一阶段追赶 Sonarr/Radarr 的下载器生态，也不需要复制 AList 的完整多云盘文件管理。正确方向是先把这条垂直链路做到可恢复、可观测、可验证，再扩展 provider 和插件。

## 5. 投产成熟度评估

| 维度 | 当前成熟度 | 主要证据 | 投产判断 |
| --- | --- | --- | --- |
| 核心功能 | 中高 | STRM、Quark、Emby、代理、重命名、任务、通知、监控均有模块 | 可内测，但需真实链路验收 |
| 代码结构 | 中 | feature 化、config facade、db 主入口已有，但大文件和双轨 API 仍明显 | 需要继续收敛入口 |
| 部署 | 中 | Docker/Compose/healthcheck 已有 | 单机可跑，多 worker 状态一致性未闭环 |
| 安全 | 中低 | 认证、CSRF、限流、日志脱敏都有，但示例配置可关闭认证 | 生产必须强制安全 baseline |
| 数据库 | 中低 | SQLite WAL 和连接池已有，缺少正式 migration/version | 长期投产必须补迁移和备份恢复 |
| 任务可靠性 | 中低 | 有 DB task 和 runner，但执行仍依赖 FastAPI BackgroundTasks / 进程内调度 | 长任务需要持久 worker 模型 |
| 前端交付 | 中低 | web build 已进镜像，但 FastAPI 未见 SPA 静态挂载 | 需要明确 Nginx 或内置静态托管 |
| 测试/CI | 中 | 测试多、覆盖率门槛有；前端单测/E2E未完全进入主 CI | 需形成投产 gate |
| 可观测性 | 中 | Prometheus、监控 API、Grafana 资产已有 | 告警规则和运行手册不足 |

### 5.1 当前可接受的使用边界

可接受：

- 单用户或小范围家庭/NAS 环境。
- 单节点、单 worker、私网访问。
- 使用测试目录先跑 Quark/Emby/STRM/播放链路。
- 有人工看护和备份的受控内测。

不建议：

- 直接公网裸露。
- 多用户共享敏感 Cookie。
- 多 worker 或多实例直接共享 SQLite 和内存状态。
- 无备份、无监控告警、无迁移版本的长期无人值守运行。

## 6. 根因级风险

### R1. API 双轨并行会持续制造契约债

`app/config/application.py` 同时注册 legacy 路由和 v1/support 路由；`app/api/v1/__init__.py` 通过裁剪/复制 legacy router 的 route 形成 canonical path。短期能兼容旧客户端，长期会让鉴权、OpenAPI、SDK、前端类型、监控指标都出现“双主路径”。

投产影响：

- 新功能不知道该写 legacy 还是 v1。
- 对外 API 文档难以保证唯一。
- 兼容层无法安全退役。

必须动作：

- 冻结 legacy 新增能力。
- 定义 `/api/v1` 为唯一新增公共接口入口。
- 对未迁移模块建立迁移清单、测试和移除条件。

### R2. Docker 默认多 worker 与进程内状态冲突

`Dockerfile` 默认 `WEB_CONCURRENCY=2` 且 `uvicorn --workers 2`。但项目当前有配置 watcher、内存 cache、WebSocket manager、FastAPI BackgroundTasks、APScheduler/asyncio 调度器、SQLite 写队列等进程内状态。

投产影响：

- 配置热更新只命中某个 worker。
- WebSocket 推送只到连接所在进程。
- 后台任务和内存缓存状态分裂。
- SQLite 并发写入风险上升。

必须动作：

- 第一阶段生产镜像明确默认单 worker。
- 如果要多 worker，先把队列、缓存、WebSocket broadcast、配置通知外置到 Redis/消息队列。

### R3. 数据库缺少正式迁移链

启动路径使用 `Base.metadata.create_all()`，同时仓库内存在若干零散 migration 脚本。`create_all()` 只能补表，不能可靠处理字段修改、索引演进、数据迁移、回滚、schema version。

投产影响：

- 老数据库升级不可审计。
- 新版本字段缺失或类型变化不容易自动发现。
- 回滚和灾难恢复没有确定流程。

必须动作：

- 引入 Alembic，或先用 SQLite `PRAGMA user_version` 建最小迁移框架。
- 所有模型变更必须有 migration 和回归测试。

### R4. 安全默认值不能直接投产

`config.example.yaml` 中 `security.require_api_key: false`。项目有认证中间件、CSRF、安全头、限流，但生产基线没有被统一强制。

投产影响：

- 错误配置会导致敏感接口暴露。
- Quark Cookie、TMDB Key、Emby Key 等敏感凭据风险高。
- Grafana 默认密码、CORS 通配符、HTTP 明文都可能成为真实风险。

必须动作：

- 生产环境必须要求 `SMART_MEDIA_SECURITY_API_KEY`、`SMART_MEDIA_JWT_SECRET_KEY`。
- 生产 CORS 不允许 `*`。
- Cookie 设置 Secure/SameSite，入口统一走 HTTPS 反代。
- Grafana 默认密码必须在 `.env` 中覆盖。

### R5. 前端交付方式不闭环

镜像构建阶段复制 `web/dist` 到 `/app/web/dist`，但 FastAPI 装配中没有看到 `StaticFiles` 或 SPA fallback。运维文档提到可用 Nginx 托管前端。

投产影响：

- 单容器可能只有 API，没有 Web 管理端。
- 用户按 README 访问服务时会产生体验断层。

必须动作：

- 二选一：明确 Nginx/独立静态服务为生产拓扑，或在 FastAPI 中正式挂载 SPA。
- Docker health/smoke 覆盖前端首页，而不是只覆盖 `/health` 和 `/` API。

### R6. 长任务需要持久化执行模型

当前任务 API 通过 `BackgroundTasks.add_task(TaskRunner.run_task, id)` 启动后台执行，另有进程内 scheduler。对短任务可用，对 STRM 扫描、刮削、批量重命名、Emby 刷新这种长任务风险较高。

投产影响：

- 进程重启后任务状态可能停留在 running/planning。
- 取消、重试、恢复、幂等不够硬。
- 多 worker 会造成任务执行归属不清。

必须动作：

- 建立 DB-backed queue 或 Redis/RQ/Celery/Arq 这类 worker 模型。
- 任务状态机必须支持 pending/running/cancel_requested/cancelled/retry_scheduled/completed/failed。
- 每个任务有幂等键、锁、心跳和重启恢复。

## 7. 投产前必须完成的工作

### P0: 不完成就不应投产

1. **生产安全基线**
   - 强制生产环境 `security.require_api_key=true`。
   - 缺少 `SMART_MEDIA_SECURITY_API_KEY` 或 `SMART_MEDIA_JWT_SECRET_KEY` 时拒绝启动或 readiness 失败。
   - CORS 白名单化，移除生产 `*`。
   - Grafana 密码、JWT secret、Quark cookie、Emby/TMDB key 全部走 `.env` / secret manager。

2. **单节点部署闭环**
   - Docker 默认 worker 调整为 1，或文档明确“多 worker 不支持”。
   - 明确前端是 Nginx 托管还是 FastAPI 内置静态托管。
   - Compose healthcheck 覆盖 `/ready`，部署 smoke 覆盖 API docs、前端首页、登录状态。

3. **数据库迁移与备份**
   - 建立 schema version。
   - 首个 migration 覆盖当前表结构。
   - 加备份、恢复、WAL checkpoint、恢复演练文档和脚本。

4. **CI 投产门禁**
   - 后端 Ruff、format、MyPy、pytest coverage 必须阻断。
   - 前端 lint、type-check、Vitest、build 必须阻断。
   - 至少一组 Playwright smoke 进入 PR gate 或 nightly gate。
   - Docker build + compose up + `/ready` + frontend smoke 进入发布 gate。
   - High/Critical 安全扫描需要明确阻断策略。

5. **真实链路验收**
   - 使用专门测试目录，不使用真实大库。
   - 覆盖 Quark 浏览、STRM 生成、Emby/Jellyfin 入库、播放 302/代理 fallback、智能重命名预览、重命名回滚、Emby 刷新。

### P1: 稳定运行必须补齐

1. API v1 独立契约与 legacy 退役计划。
2. 任务持久化 worker、重试、取消、恢复、心跳。
3. Quark/Emby/TMDB/AI 外部依赖的错误分类、限流、熔断、退避重试。
4. Prometheus 告警规则、Grafana dashboard、运行 runbook。
5. 配置服务拆分：load/save/watch/rollback/notify 分离。
6. 高风险大文件拆分：`app/api/emby.py`、`app/api/quark.py`、`RenameView.vue`、`ProxyServiceView.vue` 等。

### P2: 产品化和扩展能力

1. 存储 provider 插件化：Quark、AList/WebDAV、本地存储先收敛接口。
2. 媒体服务器适配层：Emby/Jellyfin/Plex 刷新、扫描、Webhook 独立化。
3. 命名模板、质量 profile、手动匹配体验参考 Sonarr/Radarr。
4. 资源入口参考 Quark-Auto-Save / CloudSaver，作为独立模块接入，不污染 STRM 核心。

## 8. 推荐投产路线

### 阶段 A: 单机受控内测

目标：能在私网单机稳定跑完整链路。

通过标准：

- 单 worker。
- 认证强制开启。
- Docker compose 启动后 `/ready` 通过。
- 前端可访问。
- 测试目录生成 STRM 并可播放。
- 重启后任务状态、配置和数据库一致。

### 阶段 B: 家庭/NAS Beta

目标：可由维护者长期运行，具备恢复能力。

通过标准：

- migration/version 机制落地。
- 自动备份和恢复演练通过。
- Playwright smoke 和 Docker deploy gate 通过。
- 告警和日志能定位外部依赖失败。
- 长任务失败可重试，取消有效。

### 阶段 C: 稳定生产

目标：长期无人值守，支持版本升级。

通过标准：

- 发布前 CI/CD 全绿。
- 安全扫描 High/Critical 策略明确。
- 数据库升级/回滚可审计。
- API v1 作为唯一新增公共契约。
- provider/任务/媒体服务器集成边界清晰。

## 9. 结论

Smart Media 不是“不能投产”，而是“不能按当前默认配置直接投产”。项目核心方向是成立的，且与 SmartStrm、Quark-Auto-Save、AList、Sonarr/Radarr 等项目相比有明确差异化：它把国内云盘 STRM、Emby/Jellyfin 播放代理、AI/TMDB 重命名和运维控制台聚到一条链路上。

要让它稳步投入使用，优先级必须从“继续加功能”切到“投产硬化和验证闭环”。下一份执行文档 [`../development/2026-04-27-ai-production-hardening-execution.md`](../development/2026-04-27-ai-production-hardening-execution.md) 已把这些工作拆成可由 AI agent 分阶段执行、每阶段带测试命令和验收标准的任务清单。
