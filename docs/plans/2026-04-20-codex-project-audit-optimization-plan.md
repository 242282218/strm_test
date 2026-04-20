# quark_strm 全面审查与优化执行文档（面向 Codex）

- 日期：2026-04-20
- 适用范围：`D:\PROJECT_ZZZZZZZZZ\smart_media\quark_strm`
- 目标读者：Codex、维护者、后续重构执行者
- 文档性质：审查结论 + 优化路线图 + 分阶段验收标准
- 执行原则：只做可验证修改；优先收敛真相源；先修结构性问题，再做局部性能与体验优化

---

## 1. 结论摘要

项目已经具备可运行的后端、前端、测试、Docker 与 CI 基础，也明显处于一次大规模重构中段。现在最大的问题不是“没有能力”，而是“真相源不唯一、兼容层过厚、质量门禁不一致、文档漂移严重”。这会导致 Codex 或人类维护者在继续迭代时不断重复做三件事：

1. 先猜哪一层才是真实现。
2. 再猜旧路径是不是还能删。
3. 最后才敢改功能。

如果不先处理这些结构问题，继续堆功能会让维护成本非线性上升。

当前推荐路线不是重写，而是执行“保守收敛式优化”：

1. 先统一仓库卫生、CI 门禁和文档真相源。
2. 再收敛 API 契约、前后端兼容层和基础设施入口。
3. 最后拆大文件、降耦合、补充自动化约束。

---

## 执行进度快照（2026-04-21 更新）

### 已完成的低风险收敛

- CI/workflow 门禁已统一到 `vars.QUARK_STRM_COVERAGE_FAIL_UNDER`（默认回退 `66`），并去掉会把 lint/type-check 结果静默放过的 `|| true`。
- 本地运行产物目录边界已固定到 `cache/`、`output/`、`target/`、`tmp_wheel/`、`web/playwright-report/`、`web/test-results/` 等约定路径，并由 `.gitignore` 与部署文档共同锁定。
- `app/api/v1` 当前已通过 `docs/api/README.md` 明确为对外 canonical path 层，并补上 versioned/legacy 映射表，避免继续把 v1 误判成“已完全独立实现”。
- 前端 `file-manager` 的双 API 类型定义已收口到 canonical `file-manager.ts`，`fileManager.ts` 仅保留 camelCase 兼容包装。
- Phase 0 基线文档已经落地到 `docs/architecture/current-state.md`、`docs/development/compatibility-inventory.md`、`docs/development/codex-working-agreement.md`，并有 contract test 锁定入口和清单。
- 开发/前端 README 已回写命令真相源：`web/package-lock.json` + `npm ci` 是当前 CI/干净安装真相源，本地日常脚本入口默认 `pnpm run ...`；Playwright 自动拉起前端 dev server 仍按 `web/playwright.config.ts` 执行 `npm run dev`。
- `scripts/continuous_optimize.py` 的默认输入旋钮、报告输出落点、skip 规则与 `STOP_CONTINUOUS_LOOP` 停止语义，已回写到 `docs/development/codex-working-agreement.md` 并由 `tests/test_continuous_optimize_contract.py` 锁定。
- 监控入口已收口到 `docs/monitoring/README.md`，明确当前真实已落地资产是仓库根 `prometheus.yml` 与 `docs/monitoring/grafana-dashboard.json`，不再把 `prometheus-rules.yml` / `alerting/alertmanager.yml` 误写成现有文件。
- `docs/architecture/README.md`、`docs/guides/README.md` 与 `docs/guides/startup_guide.md` 已补齐最后同步、对应代码目录、执行入口和前端命令真相源，不再保留静态总述式目录索引漂移。
- `app/api/strm.py` 与 `app/api/dashboard.py` 已移除对 `Database(resolve_db_path())` 兼容层 caller 的依赖，`resolve_db_path` 调用方也已回收到 `app.core.db`；当前 `app/` 层显式 `Database(...)` caller 已清零，并由 `tests/test_db_path_contract.py` 阻止重新引入 `app.core.database` import。
- `app/api/tmdb.py` 已移除对 `ConfigManager` 的运行态直连，TMDB API key 统一通过 `get_config_service()` 读取，并由 `tests/test_tmdb_api.py` + `tests/test_db_path_contract.py` 锁定 canonical `tmdb.api_key` 优先、legacy `api_keys.tmdb_api_key` 回退与 API 层 import 护栏。
- `app/api/stable_stream.py` 已移除 `get_config()` 全局实例，Quark cookie 改为请求时通过 `get_config_service()` 读取，并由 `tests/test_stable_stream_route.py` + `tests/test_db_path_contract.py` 锁定稳定播放入口的配置读取与 module-specific import 护栏。
- `app/api/emby_gateway.py` 的 PlaybackInfo hook 已移除 `get_config()` cookie 读取，专用 Emby 网关改为直接复用 `app_config.quark.cookie`，并由 `tests/test_emby_gateway.py` + `tests/test_db_path_contract.py` 锁定网关回放入口与 module-specific import 护栏。
- `app/core/dependencies.py` 的 Quark 依赖 helper（`get_quark_cookie()` / `get_only_video_flag()` / `get_root_id()`）已移除 `get_config()` 全局实例，统一通过 `get_config_service()` 读取运行态配置，并由 `tests/test_dependencies.py` + `tests/test_db_path_contract.py` 锁定依赖层行为与 module-specific import 护栏。
- `app/api/proxy.py` 已移除 `get_config()` 全局实例；代理流、302、转码和缓存入口的 Quark cookie 统一通过 `get_config_service()` facade 读取，并由 `tests/test_emby_proxy_routing.py` + `tests/test_proxy_stream_contract.py` + `tests/test_db_path_contract.py` 锁定运行态配置读取与 module-specific import 护栏。
- `app/api/emby.py` 已移除 `get_config()` 全局实例；本地 PlaybackInfo / item / stream / master 入口的 Quark cookie 统一通过 `get_config_service()` facade 读取，并由 `tests/test_emby_proxy_routing.py` + `tests/test_db_path_contract.py` 锁定运行态配置读取与 module-specific import 护栏。

### 当前剩余边界

- `web/src/features/config/*` 仍是已有大量未提交修改的脏切片，除非是极小 blast radius 的真相源修正，否则不要继续深改。
- `app/api/v1/*` 虽然已经是 public canonical path 层，但内部仍复用部分 legacy router；不能把当前状态误写成“v1-only 实现树已完成”。
- `app/api/quark.py` 仍保留 `get_config()` 兼容读取；当前只能说 API 层已基本收口运行态配置 caller，不能误写成 `config_manager` 已彻底退出 API 层。
- `app/services/token_monitor.py`、`app/services/webdav_fallback.py`、`app/core/path_security.py` 与 `app/services/ai_connectivity_service.py` 已移除 `config_manager` compatibility import；Quark cookie、WebDAV fallback 配置、允许目录补充读取与 AI provider map 统一通过 `get_config_service()` / `AppConfig.ai.providers` 读取，同时保留最小 helper 作为测试 patch 点，并由对应模块测试 + `tests/test_db_path_contract.py` 锁定。
- service/core 层仍保留 9 个 `config_manager` compatibility caller：`app/services/emby_proxy_service.py`、`app/services/integrations/emby.py`、`app/services/link_resolver.py`、`app/services/media/organize.py`、`app/services/media/rename.py`、`app/services/media/smart_rename.py`、`app/services/media/strm_generator.py`、`app/services/storage/quark.py`、`app/services/unified_ai_service.py`；当前新增的是 inventory contract，尚未进入逐模块清理。
- 前端安装层仍未完成 `pnpm-lock.yaml` 迁移；当前正确表述是“CI 装依赖用 `npm ci`，本地脚本执行默认 `pnpm run ...`”，而不是简单把所有地方都替换成 `pnpm install --frozen-lockfile`。
- 监控目录当前还没有 `prometheus-rules.yml` 与 `alerting/alertmanager.yml`；后续若补告警能力，应先提交真实资产文件，再更新索引与 contract test。

### 当前执行入口

- [`docs/architecture/current-state.md`](../architecture/current-state.md)：当前后端/前端/CI 基线和热点分布。
- [`docs/architecture/core-truth-source-boundaries.md`](../architecture/core-truth-source-boundaries.md)：`config/db/exception` 当前职责边界和 Phase 3 进入说明。
- [`docs/api/README.md`](../api/README.md)：API canonical/compatibility path、认证与公共探针的当前真相源。
- [`docs/operations/README.md`](../operations/README.md)：部署命令、运行目录边界与本地产物约定的当前真相源。
- [`docs/monitoring/README.md`](../monitoring/README.md)：Prometheus 指标入口、抓取配置示例与 Grafana 资产入口。
- [`docs/development/compatibility-inventory.md`](../development/compatibility-inventory.md)：前端 wrapper 清单、状态与退役条件。
- [`docs/development/codex-working-agreement.md`](../development/codex-working-agreement.md)：当前 truth-source、避让区域、最小验证基线与持续优化脚本 contract。

### Phase / Iteration 状态总览

下文 Phase 与 Iteration 正文保留原始路线图，当前完成状态以上方快照与本节为准。

| 区块 | 当前状态 | 说明 |
| --- | --- | --- |
| Phase 0 | 已完成 | `current-state.md`、`compatibility-inventory.md`、`codex-working-agreement.md` 与对应 contract 已落地。 |
| Phase 1 | 已完成 | CI 门禁、coverage 真相源、运行产物边界与 `.gitignore` 已收敛。 |
| Phase 2 | 部分完成 | canonical path 映射表已补齐，但 `app/api/v1/*` 仍未完全摆脱 legacy 实现复用。 |
| Phase 3 | 部分完成 | `config/db/exception` 边界文档、`resolve_db_path()` contract、app 层 compatibility-caller 清理、TMDB / stable-stream / Emby gateway API 与 `core/dependencies.py` 运行态 caller 收口、`token_monitor` / `webdav_fallback` / `path_security` / `ai_connectivity_service` caller 收口与 import guard 已补；剩余 service/core `config_manager` compatibility inventory 也已锁定，但基础设施代码尚未进入实质拆分。 |
| Phase 4 | 部分完成 | wrapper 清单、`file-manager` 双类型定义与导入护栏已收敛，但 `config` / `rename` 大页面拆分未开始。 |
| Phase 5 | 已完成 | `docs/README.md`、`docs/api/README.md`、`docs/operations/README.md`、`docs/architecture/README.md`、`docs/guides/*.md`、`docs/FILE_INDEX.md` 与文档 contract 已刷新。 |
| Phase 6 | 已完成 | 热点、wrapper、重复 endpoint 类型、入口链接漂移，以及 `scripts/continuous_optimize.py` 的输入输出/skip 规则都已有 contract。 |
| Iteration 1 | 已完成 | 已完成 CI 门禁与 `.gitignore` 收敛。 |
| Iteration 2 | 已完成到映射表层 | 已完成 API canonical path 设计与映射表，尚未进入 v1-only 实现树。 |
| Iteration 3 | 已完成到边界文档 / caller 收敛层 | 已完成 `config/db/exception` 入口边界文档化、STRM API 的无效 `Database` 兼容层实例化清理，以及 TMDB / stable-stream / Emby gateway API 与依赖层 Quark helper 的配置兼容 caller 收口；尚未进入基础设施重构。 |
| Iteration 4 | 部分完成 | 已完成 `file-manager` 子项，`config` / `rename` 拆分仍待后续在干净切片推进。 |
| Iteration 5 | 已完成 | 核心索引、入口文档、`architecture/guides` 目录索引与 contract test 已落地。 |
| Iteration 6 | 已完成 | 持续优化护栏已覆盖热点、wrapper、重复类型、链接漂移，以及持续优化脚本输入输出/skip 语义。 |

### 首批执行清单状态

1. `[已完成]` 收敛 `.github/workflows/ci.yml` 和 `quark_strm/.github/workflows/*.yml` 的质量门禁。
2. `[已完成]` 补齐 `quark_strm/.gitignore`，清除运行产物噪音来源。
3. `[已完成]` 产出 API canonical path 映射表。
4. `[已完成]` 清理前端 `file-manager` 双 API 类型定义。
5. `[未开始]` 拆 `ConfigView.vue` 的状态/动作层。
6. `[已完成]` 刷新 `docs/FILE_INDEX.md` 与 `docs/operations/README.md`。

### 当前推荐后续顺序

1. 文档主入口与 guides / architecture 目录索引已基本收口；后续只要继续改 truth source，就同步更新对应 contract test，避免重新漂移。
2. 若进入代码层，优先看 Phase 3 的 `config/db/exception` 真相源收敛，并从已锁定的 service/core compatibility inventory 中选干净切片逐个收口，而不是继续扩散 wrapper 或新增 legacy 入口。
3. 前端大页面拆分仍以 `config` 之外的干净切片为主，等待 `web/src/features/config/*` 脏改动边界变清晰后再处理。

---

## 2. 本次审查依据

本结论基于以下真实代码与配置，不是猜测：

### 2.1 入口与路由

- `app/main.py`
- `app/config/application.py`
- `app/api/v1/__init__.py`

### 2.2 配置与基础设施

- `app/config/settings.py`
- `app/services/config_service.py`
- `app/core/db.py`
- `app/core/` 目录整体

### 2.3 前端结构

- `web/src/router/index.ts`
- `web/src/features/config/views/ConfigView.vue`
- `web/src/features/rename/views/RenameView.vue`
- `web/src/api/*`
- `web/src/features/*`
- `web/src/views/*`

### 2.4 质量门禁与文档

- `.github/workflows/ci.yml`
- `quark_strm/.github/workflows/pytest.yml`
- `quark_strm/.github/workflows/docker-deploy-test.yml`
- `docs/FILE_INDEX.md`
- `docs/operations/README.md`
- `web/README.md`

### 2.5 审查范围与排除项

本次“全面审查”按真实仓库边界执行，不把工作区容器和基准仓库误当成业务代码：

- 真正业务仓库根目录：`quark_strm/`
- 重点审查范围：
  - `app/`
  - `web/`
  - `tests/`
  - `docs/`
  - `.github/workflows/`
  - `pyproject.toml`
  - `pytest.ini`
  - `.gitignore`
- 明确排除或降权处理：
  - 工作区外层目录
  - `.codexpotter/benchmarks/*`
  - `.venv/`
  - `.mypy_cache/`、`.pytest_cache/`、`.ruff_cache/`
  - `cache/`、`output/`、`target/`、`tmp_wheel/`
  - `.coverage*`
  - 数据库与日志运行产物

这条边界很重要。否则 Codex 在递归扫描时会把 benchmark、虚拟环境、缓存和样本数据误判成项目复杂度，导致错误结论。

### 2.6 本次复核的实测基线

以下结论不是只看文档得出，而是基于 2026-04-20 在当前工作树中直接执行的最小充分验证：

#### 后端契约与入口基线

执行命令：

```powershell
.venv\Scripts\python.exe -m pytest tests/test_baseline_docs_contract.py tests/test_file_index_contract.py tests/test_api_docs_contract.py tests/test_api_v1_routes.py tests/test_main_entrypoint.py -q
```

结果：

- `53 passed`
- 总耗时约 `18.34s`

说明：

- 文档入口、API 文档、`/api/v1` 契约和 `app/main.py` 当前是自洽的。
- 这证明项目已经有一层“结构化保护网”，不是纯人工维护。
- 也正因为这层保护网已经存在，后续优化更适合做“收敛真相源”，而不是推倒重来。

#### 前端基线

执行命令：

```powershell
pnpm run type-check
pnpm run test:smoke -- --reporter=dot
```

结果：

- `vue-tsc --build` 通过
- smoke tests：`1 passed file / 2 passed tests`

说明：

- 前端当前不是“已经坏掉”，而是“仍可工作，但结构债明显”。
- 这类项目最忌讳因为页面还能跑，就忽略真实复杂度和兼容层数量。

### 2.7 结构量化快照

为了避免“感觉上很复杂”这种模糊结论，这里给出当前量化快照：

| 指标 | 当前值 | 含义 |
| --- | ---: | --- |
| `app/api/*.py` | 26 | 根级 API 模块数量偏多，且 legacy/support/v1 并存 |
| `app/api/v1/*.py` | 1 | `v1` 当前更像聚合层，而不是完整实现树 |
| `app/services/**/*.py` | 86 | 业务层体量大，适合继续按领域收敛 |
| `app/core/*.py` | 41 | 基础设施入口多，容易形成真相源分裂 |
| `tests/test_*.py` | 108 | 已有较大保护网，适合保守重构 |
| `web/src/views/*` wrapper | 19 | 根级视图兼容层仍偏多 |
| `web/src/features/*` 业务域 | 16 | feature 化方向是对的，但收口未完成 |
| 代码中命中 `兼容` | 80 | 兼容逻辑占比高 |
| 代码中命中 `Legacy` | 115 | legacy 债是当前主旋律之一 |

附加判断：

1. 当前最大问题不是测试缺失，而是“兼容层过多且入口分散”。
2. 当前最需要优化的不是再补一个功能，而是降低 Codex 决策成本。
3. 当前最值得保留的资产是已有 contract test，而不是旧目录名。

---

## 3. 关键发现

### F1. API 契约存在双轨并行，`v1` 还不是独立真相源

证据：

- `app/config/application.py:80-84` 同时注册 legacy 路由和 v1/support 路由。
- `app/api/v1/__init__.py:90-105` 不是定义独立的 v1 实现，而是把 legacy router 再包装一次，并保留 `/api` 别名。
- `docs/FILE_INDEX.md:56-60` 仍把 `v1` 描述为“重构后的 API 端点”，这和当前真实实现不完全一致。

影响：

- 同一业务可能存在多组公共路径，外部调用方和测试很难确定 canonical path。
- Codex 很难判断改动应该落到 legacy 还是 v1。
- 未来做 OpenAPI、SDK、权限、限流和监控分层时会重复劳动。

结论：

- 需要先定义“谁是唯一对外契约”，否则后续所有 API 修改都带兼容债。

### F2. 基础层职责碎片化，配置/数据库/异常相关真相源过多

证据：

- `app/config/settings.py` 总长约 700 行，`AppConfig` 从 `app/config/settings.py:504` 才开始，单文件承载了大量领域配置模型。
- `app/core/` 同时存在 `database.py`、`db.py`、`db_utils.py`、`db_loader.py`、`db_monitor.py`、`db_pool_monitor.py`、`db_write_queue.py`。
- 同层还同时存在 `error_handler.py`、`exception_handler.py`、`exceptions.py`、`error_codes.py`。
- `app/services/config_service.py` 自带单例、文件保存、回滚、watcher、回调通知等多职责。

影响：

- 新人或 Codex 修改数据库/配置/异常逻辑时，很难一次选对入口。
- 模块边界不清，容易出现“修了 A，B 还在绕开 A”的情况。
- 任何跨模块重构都会因为隐式耦合而放大 blast radius。

结论：

- 基础层需要先完成“单一入口 + 明确子职责”收敛，而不是继续平铺新文件。

### F3. 前端 feature 化在推进，但兼容层和重复契约仍未收口

证据：

- `web/src/views/*.vue` 当前大多只是指向 `features/*/views/*` 的薄包装。
- `web/src/api/rename.ts:1` 只是转发到 `features/rename/api/rename.ts`。
- `web/src/api/file-manager.ts:1` 与 `web/src/api/fileManager.ts:1` 分别指向两个不同的 feature API 文件。
- `web/src/features/file-manager/api/file-manager.ts:1-58` 与 `web/src/features/file-manager/api/fileManager.ts:1-52` 对同一 `/files/*` 接口定义了两套不同响应模型。
- `web/README.md:46-47` 说明“旧路径仅保留兼容包装”，但当前兼容层还没有明确淘汰边界。

影响：

- 同一接口在不同页面/测试里可能被不同类型定义消费，形成静态类型假象。
- 兼容包装过多时，Codex 改一处很容易漏另一处。
- feature 化的收益被兼容层稀释，目录更漂亮，但真实复杂度没有下降。

结论：

- 需要建立“兼容层清单 + canonical import 约束 + 退役时间表”。

### F4. 前端页面和配置工作台仍然过重，UI 结构拆分未完成

证据：

- `web/src/features/rename/views/RenameView.vue` 约 1183 行，视图、状态、筛选、编辑、执行流程混在一个 SFC 中。
- `web/src/features/config/views/ConfigView.vue` 约 904 行，并在 `:200-220` 向 `AsyncConfigGroupSectionRenderer` 传入大量 prop。
- `ConfigView` 同时处理分组导航、账号设置、密码修改、主题切换、配置装载和表单保存。

影响：

- 这类页面很难做精确回归测试，只能做大而脆的页面测试。
- 单页面改动容易引发无关区域回归。
- Codex 在做局部变更时需要加载超大上下文，效率和正确率都会下降。

结论：

- 需要把“页面容器 / view-model / 表单片段 / 业务动作”拆开，至少做到业务动作和渲染结构分离。

### F5. CI 存在多套门禁定义，而且严格程度不一致

证据：

- 根目录 `.github/workflows/ci.yml:80` 对 `mypy` 使用 `|| true`。
- 根目录 `.github/workflows/ci.yml:170` 与 `:173` 对前端 `oxlint` / `eslint` 使用 `|| true`。
- 根目录 `.github/workflows/ci.yml:118-123` 运行 coverage，但没有 `--cov-fail-under`。
- `quark_strm/.github/workflows/pytest.yml:24-27` 把 `COVERAGE_FAIL_UNDER` 设为 `66`。
- `quark_strm/.github/workflows/docker-deploy-test.yml:112-124` 又把测试覆盖门槛写成 `70`。

影响：

- “本地过了”和“某个 workflow 过了”不等于整体质量门禁真的通过。
- 同一个 PR 可能被不同 workflow 用不同标准判断。
- Codex 很难判断哪一套 CI 才是 authoritative。

结论：

- 必须先收敛成单一质量策略，再谈继续提覆盖率或扩大自动化。

### F6. 文档真相源已经漂移，部分说明落后于代码

证据：

- `docs/FILE_INDEX.md:5` 最后更新时间仍是 `2026-03-16`。
- `docs/FILE_INDEX.md:56-60` 对 v1 的描述已经滞后。
- `docs/FILE_INDEX.md:150-162` 列出的 core 文件名与当前真实目录不一致，例如文档写 `config.py`、`cache.py`、`metrics.py`、`websocket.py`，而当前目录实际已经演化为 `config_manager.py`、`cache_manager.py`、`metrics_collector.py`、`websocket_manager.py` 等。
- `docs/operations/README.md:93-94` 仍使用 `npm install` / `npm run build`，而用户级开发规范已经明确更偏向 `pnpm`；项目层面也缺少统一说明。

影响：

- 文档会误导后续修改位置与验证命令。
- Codex 参考文档时容易走到旧路径或旧约定。

结论：

- 文档不能继续手工散点维护，至少要有“核心索引自动校验”或“固定同步责任点”。

### F7. 仓库本地运行产物对搜索和审查有明显干扰

证据：

- 当前工作树中存在 `.coverage.*`、数据库文件、`cache/`、`target/`、前端 `dist/`、`playwright-report/` 等运行产物。
- `quark_strm/.gitignore:58-75` 尚未覆盖所有实际会出现的本地产物，例如 `.coverage.*`、`cache/`、`output/`、`tmp_wheel/`、`.claude/` 等。

影响：

- 本地搜索结果被运行时产物污染。
- Codex 在递归扫描时容易读到无关文件。
- CI 之外的开发环境更难保持可重复。

结论：

- 应补齐 ignore 策略，并明确运行产物目录边界。

---

## 4. 优化目标

本轮优化不追求“一次性重写”，只追求以下五个结果：

1. Codex 能快速判断每个领域的唯一入口。
2. 新旧 API、前端兼容层、文档索引有明确收敛路径。
3. CI 对关键质量问题不再“看见但放过”。
4. 最大页面和最大基础模块开始拆分，单文件风险下降。
5. 每一步都有明确验收标准，做到可停、可回滚、可继续。

---

## 5. 两种可选治理路线

### 方案 A：保守收敛式优化（推荐）

做法：

1. 先不动业务行为。
2. 先统一入口、门禁、文档、兼容层清单。
3. 再分阶段拆文件、删兼容层、收敛路径。

优点：

- 风险低。
- 每一步都容易验证。
- 更适合当前 dirty worktree 和持续开发状态。

缺点：

- 需要几轮迭代才能看到目录大幅变“漂亮”。

### 方案 B：一次性大重构

做法：

1. 直接重组 backend/frontend 目录。
2. 统一 API、服务和前端 feature 结构。
3. 通过大批量移动完成收口。

优点：

- 目录可能更快变整洁。

缺点：

- 当前仓库兼容层太多，爆炸半径大。
- dirty worktree 下极易与现有修改冲突。
- 验证成本过高，回滚成本也高。

结论：

- 默认采用方案 A。

---

## 6. 推荐执行顺序

### Phase 0：建立基线与冻结约束

目标：

- 在真正重构前，先把“现状是什么”固定下来。

任务：

1. 生成当前目录和契约快照：
   - 后端路由清单
   - 前端兼容包装清单
   - CI/workflow 清单
   - 文档索引漂移清单
2. 记录当前大文件 Top N：
   - Python Top 20
   - Vue/TS Top 20
3. 明确本轮不做的事：
   - 不改协议语义
   - 不引入新框架
   - 不先做性能微调

建议产物：

- `docs/architecture/current-state.md`
- `docs/development/compatibility-inventory.md`

建议验证：

```powershell
pytest tests/test_ci_workflow.py tests/test_pytest_workflow_coverage_gate.py -q
cd web; npm run type-check
```

验收标准：

- 仓库内存在一份最新“当前状态”文档。
- 兼容层和 canonical path 有初始清单。
- 后续任何重构任务都能引用这份基线，不再重复人工盘点。

### Phase 1：收敛质量门禁与仓库卫生

目标：

- 让“通过 CI”重新等于“核心质量门禁通过”。

任务：

1. 收敛 workflow 责任：
   - 根目录 `.github/workflows/ci.yml` 作为全仓 authoritative pipeline。
   - `quark_strm/.github/workflows/*.yml` 要么保留为本地子流水线，要么明确标注为补充任务，不允许重复定义核心质量标准。
2. 去掉放行项：
   - 去掉 `.github/workflows/ci.yml` 中 `mypy`、`oxlint`、`eslint` 的 `|| true`。
3. 统一覆盖率门槛：
   - 所有 Python workflow 使用同一个 `COVERAGE_FAIL_UNDER` 来源。
   - 覆盖率阈值不允许在多个 workflow 手写分叉。
4. 补齐 `.gitignore`：
   - `.coverage*`
   - `cache/`
   - `output/`
   - `tmp_wheel/`
   - `.claude/`
   - 如确实只用于本地，也要覆盖 `playwright-report/`、`test-results/` 等漏网产物
5. 约束运行产物目录：
   - 明确数据库、日志、缓存、临时目录的固定位置。

建议修改文件：

- `.github/workflows/ci.yml`
- `quark_strm/.github/workflows/pytest.yml`
- `quark_strm/.github/workflows/docker-deploy-test.yml`
- `quark_strm/.gitignore`
- `docs/operations/README.md`

建议验证：

```powershell
pytest tests/test_ci_workflow.py tests/test_pytest_workflow_coverage_gate.py -q
git -C quark_strm status --short
```

验收标准：

- 所有 lint/type-check 不再被 `|| true` 放过。
- 所有 coverage workflow 只存在一个门槛真相源。
- 新 clone 后执行一次本地测试，不会产生大量未忽略产物。
- `git -C quark_strm status --short` 中不再出现固定模式的运行时垃圾文件。

### Phase 2：定义 API 唯一契约并收敛 legacy/v1

目标：

- 让 Codex 能一眼判断“新接口应该写在哪一层”。

任务：

1. 明确规则：
   - `app/api/v1/*` 是否为唯一对外契约。
   - legacy 路由是否仅保留兼容，不允许新增能力。
2. 建立映射表：
   - 旧路径
   - 新路径
   - 是否还在被前端/外部依赖
   - 计划删除时间
3. 将 `v1` 从“镜像包装层”升级为真正的契约层：
   - 不再直接复制 legacy router 定义。
   - 每个 v1 端点由 v1 自己声明。
4. legacy 路由集中到清晰位置：
   - 例如 `app/api/legacy/`
   - 每个 legacy 模块带废弃说明和终止条件
5. 更新 OpenAPI 与测试：
   - 只让 canonical 路由默认出现在文档中。

建议修改文件：

- `app/config/application.py`
- `app/api/v1/__init__.py`
- `app/api/legacy/*` 或新的兼容层目录
- `tests/test_api_v1_routes.py`
- `docs/api/README.md`

建议验证：

```powershell
pytest tests/test_api_v1_routes.py tests/test_api_docs_contract.py tests/test_main_entrypoint.py -q
pytest tests/test_api_v1_routes.py tests/test_api_docs_contract.py tests/test_main_entrypoint.py -q
```

额外检查：

- 打开 `/openapi.json`，确认 canonical route 不重复。

验收标准：

- 新功能默认只允许落在 canonical API 目录。
- legacy 与 v1 的职责在文档中能一句话说清。
- OpenAPI 中不存在重复或语义重叠的公开路径组。
- 路由注册代码不再同时把同一能力暴露为多套“主路径”。

### Phase 3：收敛基础设施真相源

目标：

- 配置、数据库、异常、安全、缓存各有唯一主入口。

任务：

1. 拆 `app/config/settings.py`：
   - 按领域拆为 `app/config/schema/*.py`
   - `AppConfig` 保留聚合职责
2. 收敛数据库入口：
   - 明确 `db.py` 是唯一会话/engine 入口，还是 `database.py` 才是
   - 其他文件退化为 helpers 或被删除
3. 收敛异常处理：
   - 明确 `exceptions.py` 只放领域异常
   - `exception_handler.py` 只放 FastAPI 处理器
   - `error_codes.py` 只放错误码映射
4. 收敛配置服务：
   - `ConfigService` 仅保留配置读写协调
   - watcher、回滚、通知等能力可拆到内部模块或组合对象
5. 建立基础层边界文档：
   - 哪些模块允许直接 import
   - 哪些模块只能通过 facade 访问

建议修改文件：

- `app/config/settings.py`
- `app/config/`
- `app/core/db*.py`
- `app/core/exception*.py`
- `app/services/config_service.py`
- `docs/architecture/README.md`

建议验证：

```powershell
pytest tests/test_db.py tests/test_db_pool.py tests/test_db_write_queue.py tests/test_system_config_api.py -q
pytest tests/test_exception_handler.py tests/test_exceptions.py tests/test_encryption.py -q
```

验收标准：

- 数据库相关模块能画出清晰依赖图，且只有一个 engine/session 主入口。
- 配置 schema 不再集中在一个超大文件中。
- 异常体系的职责边界清晰，不再需要在多个模块间猜入口。
- 至少前 10 个基础模块中，不再出现明显功能重叠命名。

### Phase 4：完成前端 feature 收口

目标：

- 所有 feature 都有明确的真实实现路径，兼容层只做薄包装且有退役计划。

任务：

1. 建兼容层清单：
   - `src/views/*`
   - `src/api/*`
   - `src/components/*`
   - `src/stores/*`
2. 为每个兼容包装标注状态：
   - `wrapper-active`
   - `wrapper-deprecated`
   - `remove-after:<date or milestone>`
3. 消除重复 API 契约：
   - `file-manager.ts` / `fileManager.ts` 二选一
   - 相同 endpoint 只保留一套类型定义
4. 统一导入策略：
   - feature 内部禁止反向依赖旧包装目录
   - ESLint 或 Vitest contract test 锁定此规则
5. 缩减超大页面：
   - `RenameView.vue`
   - `ConfigView.vue`
   - 其他 700+ 行页面
6. 采用页面容器 + view-model + 片段组件结构：
   - 页面容器只负责路由和页面装配
   - view-model 管状态和异步动作
   - 片段组件负责表单/列表/摘要区块

建议修改文件：

- `web/src/api/*`
- `web/src/features/*`
- `web/src/views/*`
- `web/src/components/*`
- `web/src/router/index.ts`
- `web/README.md`

建议验证：

```powershell
cd web
npm run lint
npm run type-check
npm run test:run
npm run build-only
```

若改路由或兼容层：

```powershell
cd web
npm run test:smoke
```

验收标准：

- 每个 endpoint 只存在一套 canonical TS 类型定义。
- feature 内部不再依赖旧 `src/views/*`、`src/api/*` 包装路径。
- `RenameView.vue`、`ConfigView.vue` 等超大页面完成第一轮拆分。
- 包装层数量有可量化下降，并有剩余名单。

### Phase 5：文档真相源收敛

目标：

- 文档不再作为历史残留，而是作为执行入口。

任务：

1. 重写以下核心索引：
   - `docs/FILE_INDEX.md`
   - `docs/README.md`
   - `docs/architecture/README.md`
   - `docs/operations/README.md`
2. 给每类文档增加“最后校验日期”和“对应代码目录”。
3. 为 Codex 新增固定入口文档：
   - 当前文档作为总计划
   - 再补一份 `docs/development/codex-working-agreement.md`
4. 若条件允许，增加轻量文档契约测试：
   - 校验目录是否存在
   - 校验关键文件名是否仍匹配
   - 校验 README 中的命令与 `package.json` / workflow 一致

建议验证：

```powershell
pytest tests/test_service_module_aliases.py tests/test_deployment_contract.py tests/test_pyproject_packaging_contract.py -q
```

验收标准：

- 文档能指导新成员或 Codex 找到真实入口，而不是过时入口。
- 核心索引文档有维护时间戳和责任边界。
- 项目关键命令与 README、workflow、package script 保持一致。

### Phase 6：建立持续优化护栏

目标：

- 优化不是一次性活动，而是可以持续执行。

任务：

1. 将“最大文件 Top N”加入周常检查或脚本。
2. 将“兼容层数量”加入阶段指标。
3. 将“重复 endpoint 类型定义”加入 contract test。
4. 将“文档索引漂移”加入 contract test。
5. 若继续使用 `scripts/continuous_optimize.py`，需先补清晰输入输出和 skip 规则。

验收标准：

- 新增结构性债务会被测试或脚本尽早发现。
- Codex 不需要每轮都重新做大规模人工盘点。

---

## 7. Codex 执行约束

Codex 后续按本计划执行时，必须遵守以下规则：

1. 优先改 canonical path，不要优先改兼容包装层。
2. 删除任何 legacy/wrapper 前，必须先补映射或 contract test。
3. 每次只处理一个主题：
   - CI
   - API
   - config/core
   - frontend feature
   - docs
4. 每次提交都必须能单独验证，不做跨主题混改。
5. 若遇到 dirty worktree 冲突，优先保持用户现有修改，不回滚未知改动。

---

## 8. 推荐迭代拆分

建议拆成 6 个连续可交付迭代：

### Iteration 1

- 目标：收敛 CI 门禁与 `.gitignore`
- 风险：低
- 推荐先做原因：收益高，回归清晰，能先给后续重构建立护栏

### Iteration 2

- 目标：完成 API canonical path 设计和映射表
- 风险：中
- 依赖：Iteration 1

### Iteration 3

- 目标：收敛 `config/db/exception` 真相源
- 风险：中高
- 依赖：Iteration 2

### Iteration 4

- 目标：前端 file-manager、config、rename 三个高耦合 feature 收口
- 风险：中高
- 依赖：Iteration 1

### Iteration 5

- 目标：核心文档刷新并补 contract test
- 风险：低
- 依赖：Iteration 2 ~ 4 输出

### Iteration 6

- 目标：持续优化脚本与指标固化
- 风险：低
- 依赖：Iteration 1 ~ 5

---

## 9. 量化验收矩阵

### A. 结构收敛

- `app/api/v1` 或其他 canonical API 目录被正式定义为唯一新接口入口。
- legacy API 有明确目录、说明和退役策略。
- `app/config/settings.py` 不再承载大部分配置模型定义。
- `web/src/api` 中同一 endpoint 不再存在两套不同类型定义。

### B. 文件复杂度

- 后端 Top 10 大文件中，至少 5 个完成拆分或边界文档化。
- 前端 Top 10 大文件中，至少 5 个完成拆分或 view-model 分离。
- 新增文件遵守“单文件单关注点”。

### C. 质量门禁

- `mypy`、`oxlint`、`eslint` 不再被 `|| true` 放行。
- 所有 Python workflow 的 coverage threshold 只维护一处。
- 本地验证命令与 CI 命令一致度提升，避免“双重标准”。

### D. 文档真相源

- `docs/FILE_INDEX.md`、`docs/README.md`、`docs/operations/README.md` 已更新到当前结构。
- 关键文档全部带最后同步日期。
- 文档中的关键命令可直接在当前仓库执行。

### E. Codex 友好度

- 任一新任务都能在 5 分钟内定位 canonical path。
- 兼容包装是否还能删除，有显式标记而不是猜。
- 针对 API、前端 feature、配置/数据库三类任务，都能找到对应总览文档。

### 9.1 Codex 单迭代执行模板

后续每一轮优化，建议都按下面模板落地，避免“做了一堆，但无法验收”：

| 字段 | 必填内容 |
| --- | --- |
| 目标 | 只写一个主题，例如“收敛 API canonical path” |
| In Scope | 本轮允许修改的目录和文件 |
| Out of Scope | 明确不碰的切片，尤其是脏工作树区域 |
| 真相源 | 本轮唯一 authoritative 文件或目录 |
| 交付物 | 文档、代码、测试、脚本、映射表 |
| 验证命令 | 必须可复制执行 |
| 通过条件 | 结果需要满足的精确标准 |
| 停手条件 | 遇到哪些情况必须暂停并重排计划 |
| 残余风险 | 本轮故意不解决的部分 |

建议交付格式：

```text
Iteration: <name>
Goal: <single theme>
Truth Source: <path>
Files Changed: <paths>
Validation: <commands + summary>
Exit Criteria: <done definition>
Residual Risk: <what remains>
```

### 9.2 单迭代 DoD（Definition of Done）

以下条件同时满足，才能算一轮优化“完成”：

1. 只解决了一个主题，没有把 API、前端、CI、docs 混成一次提交。
2. 有明确真相源，而且文档和代码不互相打架。
3. 至少有一条自动化验证通过，不靠肉眼拍脑袋验收。
4. 若引入 canonical path、wrapper inventory、mapping table，必须写入文档或测试。
5. 能说明“本轮之后 Codex 判断入口是否更容易”，而不是更难。

### 9.3 必须停手并重新对齐的条件

出现以下任一情况时，不应继续按原路线硬推：

1. 需要跨越用户当前脏工作树的大范围冲突。
2. 一个主题的修改文件数超过 `20` 且跨越 `backend + frontend + docs + ci` 多个层次。
3. 需要同时改 legacy 与 canonical 两套实现才能通过验证。
4. 无法在当前仓库中找到 authoritative truth source。
5. 验证只能依赖手工点击，无法形成可重复命令。

### 9.4 Phase 级验收映射

为了让 Codex 不用重新理解“每个阶段成功长什么样”，这里把 Phase 和证据直接绑定：

| Phase | 最少交付物 | 最低验证要求 | 通过标准 |
| --- | --- | --- | --- |
| Phase 0 | `current-state.md` / `compatibility-inventory.md` 更新 | docs contract tests | 入口、wrapper、热点表全部和仓库现状一致 |
| Phase 1 | workflow + `.gitignore` + operations 文档 | CI/workflow contract tests | 门禁无放行项，运行产物边界清晰 |
| Phase 2 | API path 映射表 + API 文档 + 路由测试 | API docs + v1 route tests | 新接口入口规则一句话能说清 |
| Phase 3 | `config/db/exception` 边界文档与代码收敛 | db/exception 相关测试 | 主入口唯一，兼容层职责清楚 |
| Phase 4 | wrapper inventory + 页面拆分 + import 护栏 | frontend lint/type-check/tests | feature 内部不再反向依赖旧 wrapper |
| Phase 5 | docs index / README / FILE_INDEX 更新 | docs contract tests | 文档命令、目录和实际仓库一致 |
| Phase 6 | 持续优化脚本 contract + 指标 | contract tests 或脚本输出 | 新结构债能被及早发现，不靠人工巡检 |

---

## 10. 本文档对应的首批执行清单

如果要从今天开始按最小风险推进，优先顺序如下：

1. 收敛 `.github/workflows/ci.yml` 和 `quark_strm/.github/workflows/*.yml` 的质量门禁。
2. 补齐 `quark_strm/.gitignore`，清除运行产物噪音来源。
3. 产出 API canonical path 映射表。
4. 清理前端 `file-manager` 双 API 类型定义。
5. 拆 `ConfigView.vue` 的状态/动作层。
6. 刷新 `docs/FILE_INDEX.md` 与 `docs/operations/README.md`。

---

## 11. 明确不建议的做法

以下做法会让项目继续恶化，不建议执行：

1. 在 legacy 与 v1 并存状态下继续新增接口。
2. 在 `src/api/*` 和 `features/*/api/*` 同时扩展同一业务。
3. 继续让 CI 对 lint/type-check 使用 `|| true`。
4. 在未建立基线前直接大批量移动目录。
5. 只更新代码不更新索引文档。

---

## 12. 给 Codex 的一句话执行指令

先把“唯一入口、唯一契约、唯一门禁”收敛出来，再拆大文件和删兼容层；每次只做一个主题，并且必须留下可验证的验收结果。
