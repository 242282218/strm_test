# AI 投产硬化执行文档

**日期**: 2026-04-27
**适用范围**: `quark_strm/`
**输入报告**: [`../operations/2026-04-27-production-readiness-analysis.md`](../operations/2026-04-27-production-readiness-analysis.md)
**目标**: 让项目从“可运行/可内测”推进到“可稳定投入使用”
**执行方式**: 支持多 agent 并行，但每个 agent 必须有明确 ownership path，不得互相覆盖

## 0. 给 AI agent 的总指令

你在 `D:\PROJECT_ZZZZZZZZZ\smart_media\quark_strm` 仓库内工作。先读本文件、`docs/architecture/current-state.md`、`docs/development/codex-working-agreement.md`、`docs/architecture/core-truth-source-boundaries.md`。当前工作树有大量未提交改动，默认视为用户或其他 agent 的工作，不得回滚、格式化或重写无关文件。

执行顺序固定为：

1. 先确认现状和风险，不猜。
2. 每轮只做一个主题。
3. 每轮必须补测试或更新现有契约测试。
4. 每轮必须运行最小充分验证。
5. 没有验证结果，不算完成。

不要做：

- 不要同时改 API、前端、部署、安全、数据库多个主题。
- 不要为单次使用代码创建大型抽象。
- 不要在未隔离测试目录的情况下执行真实夸克重命名、删除或批量转存。
- 不要把 legacy path 当成新功能入口。
- 不要把 `scripts/continuous_optimize.py` 当成 CI 真相源。

## 1. 当前推荐方案与取舍

### 方案 A: 保守投产硬化（推荐）

做法：

- 先稳定单机单 worker 生产路径。
- 安全、数据库、部署、CI、任务可靠性先闭环。
- 之后再做 API v1 独立化和插件化。

优点：

- 风险低，能每阶段独立验证。
- 适合当前 dirty worktree。
- 不会破坏现有功能链路。

缺点：

- 目录不会立刻“变漂亮”。
- 需要多个阶段逐步推进。

### 方案 B: 大重构式产品化

做法：

- 一次性重组 API、service、worker、frontend、docs。
- 同时引入插件化和新任务系统。

优点：

- 完成后结构更清爽。

缺点：

- 当前兼容层和测试面太大，回归成本高。
- 多人/多 agent 并行极易冲突。
- 任何一处失败都会拖住整轮投产。

结论：默认执行方案 A。只有 Phase 0-4 全部通过后，才考虑局部方案 B。

## 2. 多 agent 分工模型

如需并行，按以下边界分配。每个 worker 都必须在最终输出列出自己修改的文件和验证命令。

| Agent | Ownership path | 可以做 | 禁止做 |
| --- | --- | --- | --- |
| Ops/Security | `Dockerfile`、`docker-compose.yml`、`.env.example`、`config.example.yaml`、`docs/operations/*`、安全相关测试 | 生产安全基线、单 worker、Compose、反代文档、部署测试 | 修改业务 API 语义 |
| Backend/Core | `app/core/*`、`app/config/*`、`app/services/config_service.py`、对应 tests | 配置/数据库/异常边界、migration、readiness | 修改前端和页面 |
| Task/Runtime | `app/api/tasks.py`、`app/services/platform/*`、`app/models/task.py`、任务 tests | 持久任务队列、取消、重试、恢复、心跳 | 改 Quark/Emby 业务细节 |
| API Contract | `app/api/v1/*`、`app/config/application.py`、`docs/api/*`、API tests | v1 canonical、legacy freeze、OpenAPI 去重 | 大规模重写业务 service |
| Frontend | `web/src/features/*`、`web/src/api/*`、`web/e2e/*` | 前端测试、页面拆分、API 类型收敛 | 修改后端实现 |
| QA/Docs | `tests/*`、`web/e2e/*`、`docs/testing/*`、`docs/qa/*` | 测试矩阵、验收报告、runbook | 不直接改业务逻辑，除非修测试夹具 |

并行规则：

- 同一文件只能归一个 agent。
- 两个 agent 都需要同一文件时，先拆顺序，不并行写。
- 后端和前端可以并行，但需要 API contract 文档作为边界。
- 每轮最多 3 个并行 agent，避免合并成本超过收益。

## 3. 全局成功标准

项目达到“稳步投入使用”至少满足以下条件：

1. 私网单机部署可从干净目录启动，`/ready` 稳定通过。
2. 生产环境缺少安全密钥时无法进入 ready。
3. Docker 默认单 worker，或多 worker 的外部状态依赖已经落地。
4. 前端交付方式明确，并被 Docker/部署测试覆盖。
5. 数据库有 schema version 和可重复 migration。
6. 长任务支持重启恢复、取消、重试、心跳。
7. `/api/v1` 是新增公开接口唯一入口，legacy 只兼容。
8. CI 至少阻断：后端 lint/type/test/coverage，前端 lint/type/test/build，Docker deploy smoke。
9. 真实验收覆盖：Quark 浏览、STRM 生成、Emby/Jellyfin 入库、302/代理播放、WebDAV fallback、智能重命名预览、回滚、Emby 刷新。

## 4. Phase 0: 基线冻结

### 目标

确认当前仓库真实状态，避免 AI 在旧文档和脏工作树上误判。

### 允许修改

- `docs/architecture/current-state.md`
- `docs/development/codex-working-agreement.md`
- `docs/qa/*`
- `tests/test_*contract*.py`

### 任务

1. 记录当前 git 根和 dirty 状态：

```powershell
git rev-parse --show-toplevel
git status --short
```

2. 生成代码热点快照：

```powershell
Get-ChildItem -Recurse app -Include *.py |
  ForEach-Object { [pscustomobject]@{Path=$_.FullName.Substring((Get-Location).Path.Length+1);Lines=(Get-Content $_.FullName | Measure-Object -Line).Lines} } |
  Sort-Object Lines -Descending |
  Select-Object -First 20

Get-ChildItem -Recurse web/src -Include *.vue,*.ts |
  Where-Object { $_.FullName -notmatch '\.spec\.ts$' } |
  ForEach-Object { [pscustomobject]@{Path=$_.FullName.Substring((Get-Location).Path.Length+1);Lines=(Get-Content $_.FullName | Measure-Object -Line).Lines} } |
  Sort-Object Lines -Descending |
  Select-Object -First 20
```

3. 校对 CI 真相源：
   - `quark_strm/.github/workflows/*.yml`
   - 外层 `.github/workflows/*.yml` 若存在但不属于当前 Git repo，必须在文档中明确“不是当前仓库提交对象”。

### 测试

```powershell
python -m pytest tests/test_baseline_docs_contract.py tests/test_file_index_contract.py -q
python -m pytest tests/test_ci_workflow.py tests/test_pytest_workflow_coverage_gate.py -q
```

### 通过条件

- 文档里的入口、workflow、热点表与当前文件一致。
- 测试不引用不存在的 workflow 作为唯一真相源。
- 明确本轮不处理的 dirty 文件区域。

## 5. Phase 1: 生产安全基线

### 目标

生产环境不能因为默认配置或遗漏密钥而无认证运行。

### 推荐实现

1. 在配置层定义生产环境判断：
   - `ENVIRONMENT=production`
   - 或 `SMART_MEDIA_ENV=production`
2. 生产环境启动时强制校验：
   - `security.require_api_key=true`
   - `security.api_key` 或 `SMART_MEDIA_SECURITY_API_KEY` 非空
   - `security.jwt_secret_key` 或 `SMART_MEDIA_JWT_SECRET_KEY` 非空
   - CORS 不允许 `allow_origins: ["*"]`
3. readiness 暴露安全配置问题：
   - 生产安全缺失时 `/ready` 返回 503
   - `/health` 中有明确 `startup_warnings`
4. `.env.example` 和 `config.example.yaml` 区分开发/生产：
   - 示例可以便于开发，但生产 runbook 必须明确覆盖。

### 推荐测试

新增或扩展：

- `tests/test_env_contracts.py`
- `tests/test_security_api.py`
- `tests/test_deployment_contract.py`
- `tests/test_main_entrypoint.py`

测试用例：

1. production + 空 API key -> readiness 不通过。
2. production + CORS `*` + allow credentials -> 配置校验失败。
3. production + 完整安全环境变量 -> readiness 通过。
4. development + 默认配置 -> 保持当前开发体验。
5. `/config` 等敏感配置端点必须需要认证。

### 验证命令

```powershell
python -m pytest tests/test_env_contracts.py tests/test_security_api.py tests/test_deployment_contract.py tests/test_main_entrypoint.py -q
```

### 通过条件

- 生产安全缺失不能静默放行。
- 文档、配置模板、测试三者一致。

## 6. Phase 2: 部署拓扑闭环

### 目标

明确“如何部署才是被支持的生产形态”。

### 推荐实现

第一阶段推荐单 worker：

- `Dockerfile` 默认 `WEB_CONCURRENCY=1`
- `CMD` 使用 `--workers 1`
- `docs/operations/README.md` 写清楚：SQLite + 进程内任务 + 内存缓存 + WebSocket 当前只支持单 worker 生产路径。

前端交付二选一：

1. **Nginx 托管 SPA（推荐第一阶段）**
   - Compose 增加 `frontend` 或文档明确外部 Nginx。
   - `web/dist` 由 Nginx 服务。
   - FastAPI 只负责 API / proxy。
2. **FastAPI 内置静态托管**
   - `app/main.py` 或 `app/config/application.py` 挂载 `StaticFiles`。
   - 支持 SPA fallback 到 `index.html`。
   - 确保 catch-all Emby gateway 不遮蔽前端路径。

不要两种方案混着做。第一阶段建议 Nginx/独立前端，减少 Emby gateway 路由冲突。

### 推荐测试

后端/部署：

- `tests/test_deployment_contract.py`
- 新增 `tests/test_frontend_delivery_contract.py`

E2E/Docker：

- compose config
- docker build
- docker compose up
- `/ready`
- `/health`
- 前端首页或 Nginx 静态首页

### 验证命令

```powershell
python -m pytest tests/test_deployment_contract.py -q
docker compose config
docker build -t quark-strm:test .
```

如果本地 Docker 可用，再执行：

```powershell
docker compose up --pull never -d
curl -fsS http://127.0.0.1:8000/ready
curl -fsS http://127.0.0.1:8000/health
docker compose down -v --remove-orphans
```

### 通过条件

- README/operations 中不再暗示“单容器一定提供 SPA”，除非代码确实挂载。
- Docker 默认 worker 与状态模型一致。
- compose smoke 可以覆盖真实部署入口。

## 7. Phase 3: 数据库 migration 与备份恢复

### 目标

数据库升级可审计、可回放、可恢复。

### 推荐实现路径

优先方案：Alembic。

- 新增 `alembic.ini`、`app/migrations/alembic/*`。
- 当前模型生成 baseline migration。
- 启动时不自动危险迁移，部署命令显式执行 migration。
- CI 验证 migration 能在空数据库上跑通。

保守方案：SQLite `PRAGMA user_version`。

- 建 `app/migrations/runner.py`。
- 每个 migration 一个编号和 `apply()`。
- 启动前或启动阶段只做向前迁移。
- 记录失败并阻断 readiness。

### 推荐测试

新增：

- `tests/test_migration_runner.py`
- `tests/test_db_schema_contract.py`

测试用例：

1. 空 DB -> 当前 schema version。
2. 旧 version -> 逐步迁移到当前 version。
3. migration 失败 -> DB 不标记为新 version。
4. schema version 与模型关键表一致。
5. 备份命令不会覆盖原 DB。

### 验证命令

```powershell
python -m pytest tests/test_db.py tests/test_db_pool.py tests/test_db_path_contract.py tests/test_migration_runner.py tests/test_db_schema_contract.py -q
```

### 通过条件

- 不再只有 `create_all()` 承担升级。
- 每次 schema 变化都有 migration 和测试。
- docs/operations 有备份、恢复、迁移失败处理流程。

## 8. Phase 4: 持久任务执行模型

### 目标

STRM 扫描、刮削、重命名、Emby 刷新等长任务在重启、失败、取消后可恢复。

### 推荐实现

1. 扩展任务状态机：
   - `pending`
   - `leased`
   - `running`
   - `cancel_requested`
   - `retry_scheduled`
   - `completed`
   - `partial_success`
   - `failed`
   - `cancelled`
2. 数据库字段：
   - `lease_owner`
   - `lease_until`
   - `heartbeat_at`
   - `attempt`
   - `max_attempts`
   - `idempotency_key`
   - `resume_cursor`
3. 执行模型：
   - API 只创建任务，不直接用 FastAPI `BackgroundTasks` 承担长任务。
   - worker loop 从 DB 获取 lease。
   - worker 定期 heartbeat。
   - 启动时把超时 running 任务恢复为 pending 或 retry_scheduled。
4. 幂等策略：
   - STRM 生成按 remote fid + output path 去重。
   - 重命名必须先 preview，再 execute；execute 记录操作批次，可 rollback。

### 推荐测试

扩展：

- `tests/test_task_queue_platform.py`
- `tests/test_task_runner_platform.py`
- `tests/test_task_scheduler_platform.py`
- `tests/test_cloud_drive_tasks_websocket.py`

新增用例：

1. worker 获取 lease 后其他 worker 不能重复执行。
2. heartbeat 超时后任务可恢复。
3. cancel_requested 能在安全点停止。
4. retry 使用指数退避且不超过 max_attempts。
5. worker crash 模拟后任务不会永久 running。
6. WebSocket 进度从 DB 状态恢复，而不是只依赖内存。

### 验证命令

```powershell
python -m pytest tests/test_task_queue_platform.py tests/test_task_runner_platform.py tests/test_task_scheduler_platform.py tests/test_cloud_drive_tasks_websocket.py -q
```

### 通过条件

- 任务重启恢复有测试。
- 长任务不依赖请求生命周期。
- 多 worker 前置条件清楚：如果没有 Redis/broadcast，仍只支持单 worker。

## 9. Phase 5: API v1 独立契约

### 目标

新增公开接口只进入 `/api/v1`，legacy 路径只兼容，不再长出新能力。

### 推荐实现

1. 建立 `app/api/v1/endpoints/<domain>.py`。
2. v1 endpoint 显式声明，不再从 legacy router 自动复制。
3. legacy router 标记 `include_in_schema=False` 或 deprecated。
4. `docs/api/README.md` 维护 canonical/legacy 映射和退役状态。
5. 前端 API client 逐步切到 `/api/v1`。

### 推荐迁移顺序

1. `tasks`：体量相对小，先试点。
2. `strm`：核心链路，但测试覆盖较好。
3. `quark`：大模块，分批迁移。
4. `emby/proxy`：最后迁移，风险最高。

### 推荐测试

扩展：

- `tests/test_api_v1_routes.py`
- `tests/test_api_docs_contract.py`
- `tests/test_main_entrypoint.py`

测试用例：

1. 新 v1 endpoint 出现在 OpenAPI。
2. legacy endpoint 不作为新主路径出现在文档。
3. 同一 operation 不重复出现在 canonical 和 legacy。
4. 前端使用的 endpoint 有映射测试。

### 验证命令

```powershell
python -m pytest tests/test_api_v1_routes.py tests/test_api_docs_contract.py tests/test_main_entrypoint.py -q
```

### 通过条件

- 新接口入口一句话能说清。
- OpenAPI 不重复暴露同一能力。
- legacy freeze 有测试保护。

## 10. Phase 6: 外部依赖韧性

### 目标

Quark、Emby、TMDB、AI provider 波动时，系统降级而不是拖垮主流程。

### 推荐实现

1. 标准错误分类：
   - auth_expired
   - rate_limited
   - upstream_timeout
   - upstream_5xx
   - invalid_response
   - quota_exceeded
2. 每个外部客户端统一超时、重试、退避、熔断。
3. Quark cookie 失效可被监控和 UI 明确提示。
4. AI provider fallback 可观测，失败原因写入任务日志。
5. Emby 刷新失败不应丢失，需要进入 retry queue。

### 推荐测试

扩展：

- `tests/test_quark_api_client.py`
- `tests/test_emby_api_client.py`
- `tests/test_tmdb_api.py`
- `tests/test_unified_ai_service.py`
- `tests/test_retry_policy.py`
- `tests/test_http_pool.py`

测试用例：

1. Quark 401 -> auth_expired，不盲目重试。
2. 429 -> 带 retry-after 的退避。
3. 5xx -> 有上限重试。
4. AI provider A 失败 -> fallback 到 B。
5. Emby refresh 失败 -> 任务记录 retry_scheduled。

### 验证命令

```powershell
python -m pytest tests/test_quark_api_client.py tests/test_emby_api_client.py tests/test_tmdb_api.py tests/test_unified_ai_service.py tests/test_retry_policy.py tests/test_http_pool.py -q
```

### 通过条件

- 外部失败有分类、有日志、有指标。
- 不把所有错误都变成 500 或字符串 detail。

## 11. Phase 7: 前端投产体验和测试

### 目标

关键页面可稳定完成核心工作流，前端测试进入门禁。

### 推荐实现

1. CI 前端 gate 增加：
   - `npm run test:run`
   - `npm run build`
   - Playwright smoke 或 nightly E2E
2. 高风险页面拆分：
   - `RenameView.vue`
   - `ProxyServiceView.vue`
   - `ScrapePathsView.vue`
   - `ConfigView.vue`
   - `TasksView.vue`
3. API 类型收敛：
   - 同一 endpoint 只保留一个 canonical TS 类型。
   - root `web/src/api/*` 只做兼容 re-export。
4. 用户态错误可读：
   - Quark cookie 失效。
   - TMDB key 缺失。
   - AI provider 不可用。
   - Emby 刷新失败。

### 推荐测试

前端单测：

```powershell
cd web
npm run lint
npm run type-check
npm run test:run
npm run build
```

Playwright smoke：

```powershell
cd web
npm run test:e2e -- --project chromium e2e/login.spec.ts e2e/dashboard.spec.ts e2e/tasks.spec.ts
```

核心 E2E：

```powershell
cd web
npm run test:e2e -- --project chromium e2e/strm-e2e.spec.ts e2e/smart-rename.spec.ts e2e/proxy-service.spec.ts
```

### 通过条件

- 前端单测进入主 CI。
- 至少登录、Dashboard、任务、STRM、智能重命名、代理配置有 smoke。
- 页面拆分后业务动作可单测，不只依赖大 E2E。

## 12. Phase 8: 监控、告警、备份、运行手册

### 目标

运行问题可观测，数据可恢复。

### 推荐实现

1. Prometheus 指标：
   - request latency / status
   - task status count
   - external dependency errors
   - Quark auth status
   - cache hit rate
   - DB lock / write queue depth
2. 告警规则：
   - `/ready` 持续失败
   - 任务失败率超阈值
   - Quark auth expired
   - Emby refresh 连续失败
   - SQLite 写锁/慢写入
   - 磁盘空间低
3. 备份：
   - 停写或 checkpoint 后备份 SQLite。
   - 备份 `config.yaml`、`.env` 模板说明、`strm/`。
   - 恢复演练命令。

### 推荐测试

新增或扩展：

- `tests/test_prometheus_metrics.py`
- `tests/test_monitoring_api.py`
- `tests/test_deployment_contract.py`
- `tests/test_backup_runbook_contract.py`

验证命令：

```powershell
python -m pytest tests/test_prometheus_metrics.py tests/test_monitoring_api.py tests/test_deployment_contract.py tests/test_backup_runbook_contract.py -q
```

### 通过条件

- 告警资产真实存在，不只是文档 TODO。
- 备份恢复流程有 contract test 检查关键命令和路径。

## 13. Phase 9: 真实链路验收

### 目标

用真实但隔离的数据证明项目可投产。

### 前置条件

- 创建夸克测试目录，只放少量可重命名/可删除样本。
- 使用测试 Emby/Jellyfin 媒体库，不使用正式媒体库。
- 备份 `config.yaml` 和数据库。
- 设置：
  - `SMART_MEDIA_QUARK_COOKIE`
  - `SMART_MEDIA_TMDB_API_KEY`
  - `SMART_MEDIA_EMBY_URL`
  - `SMART_MEDIA_EMBY_API_KEY`
  - `SMART_MEDIA_SECURITY_API_KEY`
  - `SMART_MEDIA_JWT_SECRET_KEY`

### 验收用例

| ID | 用例 | 自动化程度 | 通过标准 |
| --- | --- | --- | --- |
| ACC-01 | Docker 启动 | 自动 | compose up 后 `/ready` 200 |
| ACC-02 | 登录 | E2E | 登录成功，Cookie 生效 |
| ACC-03 | Quark 浏览 | E2E/API | 测试目录可列出 |
| ACC-04 | STRM 生成 | API/E2E | 本地 `strm/` 生成目标文件 |
| ACC-05 | Emby/Jellyfin 入库 | 半自动 | 媒体库扫描后看到条目 |
| ACC-06 | 302 播放 | 半自动/API | STRM URL 返回可播放 302 或直链 |
| ACC-07 | 代理流 fallback | 半自动/API | 禁用直链优先时 Range 请求可返回 |
| ACC-08 | WebDAV fallback | 半自动 | 模拟直链失败后 fallback 生效 |
| ACC-09 | 智能重命名 preview | E2E/API | preview 有新文件名、置信度、TMDB 信息 |
| ACC-10 | 执行重命名 | 人工确认 | 只对测试目录样本执行，成功后可 rollback |
| ACC-11 | Emby 刷新 | API | refresh 成功或失败进入可观察任务状态 |
| ACC-12 | 重启恢复 | 自动/半自动 | 服务重启后任务和配置状态一致 |

### 验收命令

```powershell
python -m pytest tests -q --tb=short --cov=app --cov-report=term-missing --cov-fail-under=66
```

```powershell
cd web
npm ci
npm run lint
npm run type-check
npm run test:run
npm run build
```

```powershell
docker compose config
docker build -t quark-strm:test .
docker compose up --pull never -d
curl -fsS http://127.0.0.1:8000/ready
curl -fsS http://127.0.0.1:8000/health
docker compose down -v --remove-orphans
```

### 验收报告模板

保存到 `docs/qa/YYYY-MM-DD-production-acceptance-report.md`：

```markdown
# Production Acceptance Report

- Date:
- Commit:
- Environment:
- Operator:
- Config source:
- Test Quark folder:
- Test media server:

## Automated Gates

| Gate | Command | Result | Notes |
| --- | --- | --- | --- |
| Backend | `python -m pytest ...` | pass/fail | |
| Frontend | `npm run test:run` | pass/fail | |
| Docker | `docker compose up` | pass/fail | |
| Security | `security-scan` | pass/fail | |

## Live Acceptance

| Case | Result | Evidence |
| --- | --- | --- |
| ACC-01 | pass/fail | |
| ACC-02 | pass/fail | |

## Blockers

## Residual Risks

## Go / No-Go
```

## 14. CI/CD 最终门禁建议

主 CI：

```text
backend-quality:
  ruff check
  ruff format --check
  mypy app

backend-test:
  pytest tests --cov=app --cov-fail-under=66

frontend:
  npm ci
  npm run lint
  npm run type-check
  npm run test:run
  npm run build

docker:
  docker build
```

发布 gate：

```text
docker-deploy-test:
  docker compose config
  docker compose up
  curl /ready
  curl /health
  frontend smoke

security:
  trivy fs critical/high blocks
  trivy image critical/high blocks
  codeql/semgrep blocks
  gitleaks blocks
  pip-audit policy explicit
```

Nightly：

```text
playwright full e2e
dependency scan
backup/restore dry run
continuous optimize observe-only
```

## 15. 使用持续优化脚本的方式

只在已有 gate 清晰后使用：

```powershell
python scripts/continuous_optimize.py --skip-agent-optimize --max-iterations 1
```

用于查看模块失败面，不写代码。

允许 agent 优化时，必须限制模块：

```powershell
python scripts/continuous_optimize.py --module backend-task-dashboard-config --max-iterations 1 --max-parallel-agents 1
```

停止：

```powershell
New-Item -ItemType File target/continuous/STOP_CONTINUOUS_LOOP
```

要求：

- 每次只跑一个或少量模块。
- 先看 `target/continuous/latest.md`。
- 不允许把脚本生成的无关改动直接合入。

## 16. 单轮 AI 执行模板

每个 agent 接任务时按以下格式写入 prompt：

```text
你在 quark_strm 仓库中工作。
主题: <只写一个主题>
Ownership: <允许修改的文件/目录>
Out of scope: <禁止修改的文件/目录>
背景文档:
- docs/development/2026-04-27-ai-production-hardening-execution.md
- docs/architecture/current-state.md
- docs/development/codex-working-agreement.md

任务:
1. 先读取相关代码和测试。
2. 实现最小正确修改。
3. 补或更新测试。
4. 运行指定验证命令。
5. 最终汇报修改文件、验证结果、残余风险。

禁止:
- 不要回滚用户已有改动。
- 不要修改 ownership 外文件。
- 不要跳过测试。
```

## 17. 每阶段 Definition of Done

每个 Phase 必须同时满足：

1. 代码、配置、文档、测试中至少有一项可验证产物。
2. 改动只属于当前 Phase 主题。
3. 最小验证命令已执行并记录结果。
4. 失败时给出阻塞原因和下一步，不把失败伪装成完成。
5. 真实外部操作只对隔离测试目录执行。

## 18. 推荐执行顺序总表

| 顺序 | Phase | 负责人 | 预计风险 | 最小验证 |
| ---: | --- | --- | --- | --- |
| 1 | Phase 0 基线冻结 | QA/Docs | 低 | docs/CI contract tests |
| 2 | Phase 1 生产安全 | Ops/Security | 中 | security/env/deployment tests |
| 3 | Phase 2 部署闭环 | Ops/Security | 中 | docker build + compose config |
| 4 | Phase 3 DB migration | Backend/Core | 高 | db/migration tests |
| 5 | Phase 4 持久任务 | Task/Runtime | 高 | task queue/runner tests |
| 6 | Phase 5 API v1 | API Contract | 高 | api docs/v1 tests |
| 7 | Phase 6 外部依赖韧性 | Backend/Core | 中高 | quark/emby/tmdb/ai tests |
| 8 | Phase 7 前端体验 | Frontend | 中高 | lint/type/vitest/e2e |
| 9 | Phase 8 监控备份 | Ops/Security | 中 | monitoring/backup contract |
| 10 | Phase 9 真实验收 | QA/Docs | 高 | acceptance report |

## 19. 停手条件

出现以下任一情况必须停止当前自动优化，先重新对齐：

1. 需要真实删除、移动或批量重命名用户媒体文件。
2. 验证要求使用正式夸克目录而非测试目录。
3. 修改范围跨越 20 个以上文件且包含后端、前端、部署三层。
4. 同一文件被多个 agent 同时修改。
5. 测试失败原因不明且涉及数据损坏、认证绕过或播放链路不可用。
6. 需要提升权限或执行破坏性 git 操作。

## 20. 下一步建议

从 Phase 1 开始，不要先做插件化或大页面重构。第一轮最小可交付建议：

1. 生产环境安全配置缺失时 readiness 失败。
2. Docker 默认单 worker。
3. 运维文档明确前端托管方式。
4. 增加对应 contract tests。
5. 跑安全/部署最小验证。

完成这一轮后，项目才进入可控投产硬化轨道。
