# 项目文件索引

本文档记录 quark_strm 项目中所有主要文件和目录的功能与用途。

**最后更新**: 2026-04-20

---

## 📁 项目根目录

```
quark_strm/
├── app/                    # 核心应用代码
├── config.yaml             # 主配置文件
├── cache/                  # 本地缓存与临时数据库
├── docs/                   # 项目文档
├── output/                 # 手工验证与诊断输出
├── scripts/                # 工具脚本
├── target/                 # 持续优化脚本与覆盖率产物
├── tmp_wheel/              # 本地 wheel 打包临时目录
├── web/                    # 前端应用
├── data/                   # 数据存储
├── logs/                   # 日志文件
├── strm/                   # STRM 文件存储
├── tmp/                    # 临时文件
├── tests/                  # 测试代码
├── requirements.txt        # Python 依赖
├── Dockerfile              # Docker 镜像配置
└── docker-compose.yml      # Docker Compose 配置
```

---

## 🔧 核心应用 (`app/`)

### API 层 (`app/api/`)

**用途**: 定义 HTTP API 路由和端点

#### 当前 API 文件（根级别）
- `cloud_drive.py` - 云盘管理 API
- `dashboard.py` - 仪表板数据 API
- `emby.py` - Emby 集成 API
- `monitoring.py` - 监控数据 API
- `notification.py` - 通知服务 API
- `proxy.py` - 代理服务 API
- `quark.py` - 夸克云盘 API
- `quark_sdk.py` - 夸克 SDK API
- `rename.py` - 重命名服务 API
- `scrape.py` - 刮削服务 API
- `search.py` - 搜索服务 API
- `smart_rename.py` - 智能重命名 API
- `strm.py` - STRM 文件管理 API
- `strm_validator.py` - STRM 验证 API
- `system_config.py` - 系统配置 API
- `tasks.py` - 任务管理 API
- `tmdb.py` - TMDB 集成 API
- `transfer.py` - 转存服务 API

#### v1 API（新版本）
- `v1/` - 版本化 API 目录
  - 当前对外 canonical contract 层，负责聚合 `/api/v1/*` 公共路径

**说明**:
- 根级别 `app/api/*.py` 仍保留 legacy/support 路由。
- `app/api/v1/__init__.py` 已是对外 canonical path 入口，但内部仍复用部分现有 router，而不是完全独立的 v1-only 实现树。
- 目前已 versioned 的模块以 `quark`、`strm`、`proxy`、`emby`、`tasks`、`scrape`、`monitor` 为主；其他模块是否迁移到 v1，需要先明确契约后再新增接口。

---

### 业务逻辑层 (`app/services/`)

**用途**: 实现核心业务逻辑

#### AI 服务
- `ai_parser_service.py` - AI 解析服务，用于智能识别媒体信息

#### 缓存服务
- `cache_service.py` - 缓存管理服务
- `cache_statistics.py` - 缓存统计分析
- `cache_warmer.py` - 缓存预热服务
- `link_cache.py` - 链接缓存服务
- `redis_cache.py` - Redis 缓存实现

#### 云盘服务
- `cloud_drive_service.py` - 云盘管理服务

#### 配置服务
- `config_service.py` - 配置管理服务

#### 定时任务
- `cron_service.py` - 定时任务调度服务

#### Emby 集成
- `emby_api_client.py` - Emby API 客户端
- `emby_naming_service.py` - Emby 命名规范服务
- `emby_proxy_service.py` - Emby 代理服务
- `emby_service.py` - Emby 集成服务
- `playbackinfo_hook.py` - 播放信息钩子

#### 媒体处理
- `media_organize_service.py` - 媒体整理服务
- `nfo_generator.py` - NFO 文件生成器

#### 通知服务
- `notification_service.py` - 通知服务管理
- `notification/` - 通知处理器子模块

#### 代理服务
- `proxy_service.py` - 代理服务管理

#### 夸克云盘
- `quark_api_client.py` - 夸克 API 客户端 v1
- `quark_api_client_v2.py` - 夸克 API 客户端 v2（推荐）
- `quark_sdk_service.py` - 夸克 SDK 服务
- `quark_service.py` - 夸克服务管理
- `quark_size_fetcher.py` - 文件大小获取服务

#### 重命名服务
- `rename_service.py` - 重命名服务
- `smart_rename_service.py` - 智能重命名服务

#### 评分服务
- `scoring/` - 评分服务子模块

#### 刮削服务
- `scrape_service.py` - 刮削服务，从 TMDB 获取元数据

#### 搜索服务
- `search_service.py` - 资源搜索服务

#### STRM 服务
- `strm_generator.py` - STRM 文件生成器
- `strm_service.py` - STRM 服务管理
- `strm_validator.py` - STRM 文件验证器

#### 任务管理
- `task_queue_service.py` - 任务队列服务
- `task_runner.py` - 任务执行器
- `task_scheduler.py` - 任务调度器

#### TMDB 服务
- `tmdb_service.py` - TMDB API 服务

#### 转存服务
- `transfer_service.py` - 文件转存服务

#### WebDAV 服务
- `webdav/` - WebDAV 集成子模块

---

### 核心组件 (`app/core/`)

**用途**: 提供核心基础设施组件

- `config_manager.py` - 运行时配置读取与访问入口
- `database.py` - 轻量数据库包装与路径解析
- `db.py` - SQLAlchemy engine/session 主入口
- `db_utils.py` - 数据库辅助工具
- `dependencies.py` - 依赖注入
- `encryption.py` - 加密解密功能
- `exception_handler.py` - FastAPI 异常处理器
- `exceptions.py` - 领域异常定义
- `logging.py` - 日志配置
- `lru_cache.py` - 轻量 LRU 缓存实现
- `cache_manager.py` - 多级缓存协调入口
- `metrics_collector.py` - 监控与指标采集
- `response.py` - API 响应格式化
- `retry.py` - 重试机制
- `security.py` - 安全相关功能
- `url_validator.py` - 外部 URL 校验与 SSRF 边界
- `validators.py` - 数据验证器
- `websocket_manager.py` - WebSocket 连接管理

---

### 数据模型 (`app/models/`)

**用途**: 定义数据库表结构（SQLAlchemy ORM）

- `base.py` - 基础模型类
- `cloud_drive.py` - 云盘数据模型
- `emby.py` - Emby 数据模型
- `quark.py` - 夸克数据模型
- `scrape.py` - 刮削数据模型
- `strm.py` - STRM 数据模型
- `task.py` - 任务数据模型

---

### 数据验证 (`app/schemas/`)

**用途**: 定义 API 请求/响应的数据验证模式（Pydantic）

- `base.py` - 基础 Schema
- `cloud_drive.py` - 云盘 Schema
- `task.py` - 任务 Schema

---

### 工具函数 (`app/utils/`)

**用途**: 通用工具函数

---

### 配置模块 (`app/config/`)

**用途**: 应用配置类定义

- `settings.py` - 配置类定义

---

## 📚 文档 (`docs/`)

### 目录结构
- `README.md` - 文档索引
- `FILE_INDEX.md` - 本文件，项目文件索引
- `structure_organization_report.md` - 结构整理报告

### 子目录
- `guides/` - 使用指南
- `architecture/` - 架构文档
  - `README.md` - 架构总览入口
  - `current-state.md` - 当前后端/前端入口、CI 真相源与大文件热点基线
  - `core-truth-source-boundaries.md` - `config/db/exception` 当前职责边界与 Phase 3 进入说明
- `development/` - 开发文档
  - `README.md` - 开发文档入口
  - `codex-working-agreement.md` - Codex 固定执行入口、范围边界与最小验证基线
  - `compatibility-inventory.md` - 前端 wrapper 清单、状态与退役条件
  - `development_plan.md` - 开发方案
  - `history.md` - 历史指令记录
  - `test_report.md` - 测试报告
- `operations/` - 运维文档
- `api/` - API 文档
- `plans/` - 审查结论、阶段计划与执行路线
  - `2026-04-20-codex-project-audit-optimization-plan.md` - 2026-04-20 审查优化总计划

---

## 🔧 脚本工具 (`scripts/`)

### 主要脚本
- `organize_structure.py` - 项目结构整理脚本

### 子目录
- `verification/` - 验证脚本
  - `comprehensive_verification_report.py` - 综合验证报告
  - `verify_smart_rename_mapping.py` - 智能重命名映射验证
  - `verify_ui_completeness.py` - UI 完整性验证
- `utils/` - 工具脚本

---

## 🌐 前端应用 (`web/`)

**技术栈**: Vue 3 + Vite + Element Plus

### 当前结构要点

- `src/features/` - 业务域真实实现
  - 当前包含：`app-shell`、`auth`、`category-strategy`、`config`、`dashboard`、`emby`、`file-manager`、`notifications`、`proxy`、`quark`、`rename`、`scrape`、`search`、`smart-rename`、`tasks`、`webdav`
- `src/views/` - 历史页面路径兼容入口
- `src/api/` - 共享 API client 与历史 API 兼容导出
- `src/components/` - 跨域共享组件与少量兼容包装
- `src/stores/` - 全局 store 与少量兼容包装

### 组织原则

- 新增前端业务代码优先进入 `src/features/<domain>/`
- 旧 `src/views/*`、`src/api/*` 路径保留薄包装，避免一次性打断路由、测试和外部导入
- 每个已迁移业务域一般会带有 `module-aliases.spec.ts`，用于验证旧路径仍映射到新实现

详见 `web/README.md`

---

## 🗄️ 数据目录

### `data/`
**用途**: 应用数据存储
- 数据库文件
- 用户上传文件
- 缓存数据

### `logs/`
**用途**: 日志文件存储
- 应用日志
- 错误日志
- 访问日志
- 整理操作日志

### `strm/`
**用途**: STRM 文件存储
- 生成的 STRM 文件
- 按媒体类型组织

### `tmp/`
**用途**: 临时文件存储
- 临时下载文件
- 处理中的文件

---

## 🧪 测试 (`tests/`)

**用途**: 单元测试和集成测试

---

## ⚙️ 配置文件

### 根目录配置
- `config.yaml` - 主配置文件
  - API 密钥
  - 服务配置
  - 代理设置

### Python 配置
- `requirements.txt` - Python 依赖包列表
- `pyproject.toml` - 项目元数据和构建配置

### Docker 配置
- `Dockerfile` - Docker 镜像构建配置
- `docker-compose.yml` - Docker Compose 服务编排

---

## 📝 命名规范

### API 文件
- 使用**小写下划线**命名：`cloud_drive.py`
- 功能相关文件使用统一前缀：`quark_*.py`

### Service 文件
- 使用**小写下划线**命名
- 带 `_service` 后缀：`cache_service.py`
- 特殊功能使用描述性后缀：`_client`, `_generator`, `_validator`

### 文档文件
- 使用**小写下划线**命名：`development_plan.md`
- 英文命名优先

---

## 🔄 版本说明

### API 版本
- **根级别 API**: 旧版本，保留用于向后兼容
- **v1 API**: 新版本，推荐使用

### Service 版本
- **v2 后缀**: 最新版本（如 `quark_api_client_v2.py`）
- **无后缀**: 旧版本或稳定版本

---

## 📌 注意事项

1. **配置文件**: 修改 `config.yaml` 后需重启服务
2. **数据库**: 位于 `quark_strm.db`，使用 SQLite
3. **日志**: 默认输出到 `logs/` 目录
4. **环境变量**: 可通过 `.env` 文件配置（参考 `.env.example`）

---

**维护者**: DevOps Agent  
**最后更新**: 2026-04-20
